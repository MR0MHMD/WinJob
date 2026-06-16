from django.urls import reverse

from .utils import validate_end_date, validate_start_date
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from influencers.models import InfluencerProfile
from advertisers.models import AdvertiserProfile
from django.contrib.auth import get_user_model
from django_jalali.db import models as jmodels
from django.db import models, IntegrityError
from urllib.parse import urlencode
from django.utils import timezone
from core.models import Category
import uuid
import os

User = get_user_model()


class ContentType(models.Model):
    platform = models.ManyToManyField(
        'plat_form.Platform',
        related_name='content_types',
        verbose_name=_('پلتفرم')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('نام نوع محتوا')
    )
    description = models.TextField(
        _('توضیحات'),
        blank=True
    )
    icon = models.CharField(
        _('آیکون'),
        max_length=100,
        blank=True,
        help_text=_('نام کلاس آیکون (مثلاً: fa-video)')
    )
    slug = models.SlugField(
        verbose_name=_('شناسه')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('فعال')
    )

    class Meta:
        verbose_name = _('نوع محتوا')
        verbose_name_plural = _('انواع محتوا')
        ordering = ['name']

    def __str__(self):
        return f'{self.name}'


class AdType(models.Model):
    platform = models.ForeignKey(
        'plat_form.Platform',
        on_delete=models.CASCADE,
        related_name='ad_types',
        verbose_name=_('پلتفرم')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('نام نوع تبلیغ')
    )
    slug = models.SlugField(
        verbose_name=_('شناسه')
    )

    description = models.TextField(
        _('توضیحات'),
        blank=True
    )

    icon = models.CharField(
        _('آیکون'),
        max_length=50,
        blank=True,
        help_text=_('نام کلاس آیکون (مثلاً: fa-video)')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('فعال')
    )

    class Meta:
        verbose_name = _('نوع تبلیغ')
        verbose_name_plural = _('انواع تبلیغ')
        unique_together = ('platform', 'slug')
        ordering = ['platform', 'name']

    def __str__(self):
        return self.name


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش نویس"
        PENDING = "pending", "در انتظار بررسی"
        APPROVED = "approved", "تایید شده"
        RUNNING = "running", "در حال اجرا"
        COMPLETED = "completed", "تمام شده"
        CANCELLED = "cancelled", "لغو شده"

    platform = models.ForeignKey(
        'plat_form.Platform',
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='پلتفرم'
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='نوع محتوا'
    )

    ad_type = models.ForeignKey(
        AdType,
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='نوع تبلیغ'
    )

    content_service_type = models.ForeignKey(
        'content_team.ContentServiceType',
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name=_("سرویس تولید محتوا"),
        null=True, blank=True
    )

    advertiser = models.ForeignKey(
        AdvertiserProfile,
        on_delete=models.CASCADE,
        related_name="campaigns",
        verbose_name="تبلیغ دهنده"
    )

    name = models.CharField(
        max_length=255,
        verbose_name="نام کمپین"
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات"
    )

    start_date = jmodels.jDateField(
        verbose_name="زمان شروع"
    )

    end_date = jmodels.jDateField(
        verbose_name="زمان پایان"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="وضعیت"
    )

    influencer_coupon = models.ForeignKey(
        "Coupon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="influencer_campaigns",
        verbose_name="کد تخفیف اینفلوئنسر"
    )

    content_team_coupon = models.ForeignKey(
        "Coupon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="content_team_campaigns",
        verbose_name="کد تخفیف تیم محتوا"
    )

    platform_coupon = models.ForeignKey(
        "Coupon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="platform_campaigns",
        verbose_name="کد تخفیف پلتفرم"
    )

    is_free = models.BooleanField(
        default=False,
        verbose_name=_("عام‌المنفعه")
    )

    discount_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مقدار تخفیف"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی"
    )

    approved_at = jmodels.jDateTimeField(
        _('زمان تایید'),
        null=True,
        blank=True,
        help_text=_('زمانی که کمپین از وضعیت pending به approved تغییر کرد')
    )

    class Meta:
        verbose_name = "کمپین"
        verbose_name_plural = "کمپین‌ها"
        ordering = ["-created_at"]

    def duration_days(self):
        return (self.end_date - self.start_date).days

    def clean(self):
        """
        اعتبارسنجی منطق تاریخ‌های کمپین
        """

        if self.start_date:
            validate_start_date(self.start_date)

        if self.start_date and self.end_date:
            validate_end_date(self.start_date, self.end_date)

        if self.ad_type and self.platform:
            if self.ad_type.platform_id != self.platform_id:
                raise ValidationError("نوع تبلیغ با پلتفرم انتخاب شده سازگار نیست.")

        if self.is_free:
            if not hasattr(self, 'content_type') or self.content_type.slug != "ready-content":
                raise ValidationError("در کمپین رایگان، تنها نوع محتوای «محتوای آماده» قابل قبول است.")
            if self.content_service_type:
                raise ValidationError("کمپین رایگان نمی‌تواند شامل سرویس تولید محتوا باشد.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def is_editable(self):
        return self.status in ["draft", "pending"]

    @property
    def can_submit_report(self):
        """
        بررسی آیا زمان ثبت گزارش فرا رسیده است
        """
        from django.utils import timezone
        now = timezone.now()
        return now >= self.start_date

    @property
    def total_clicks(self):
        """تعداد کل کلیک‌های کمپین (شمارش مستقیم)"""

        return CampaignClick.objects.filter(
            tracking_link__campaign_influencer__campaign=self
        ).count()

    def formated_created_at(self):
        from core.admin_utils import format_datetime
        return format_datetime(self.created_at)


class CampaignInfluencer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        ACCEPTED = "accepted", "پذیرفته شد"
        REJECTED = "rejected", "رد شد"
        COMPLETED = "completed", "انجام شد"

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="influencer_bookings",
        verbose_name="کمپین"
    )

    channel = models.ForeignKey(
        "influencers.InfluencerChannel",
        on_delete=models.PROTECT,
        related_name="campaign_bookings",
        verbose_name="کانال اینفلوئنسر"
    )

    service_rate = models.ForeignKey(
        'influencers.InfluencerServiceRate',
        on_delete=models.PROTECT,
        related_name="campaign_services",
        verbose_name="تعرفه سرویس"
    )

    price = models.PositiveBigIntegerField(
        verbose_name="قیمت نهایی"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="وضعیت"
    )

    is_seen = models.BooleanField(_("دیده شده؟"), default=False)

    tracking_code = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="کد ردیابی"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )

    is_paid = models.BooleanField(
        default=False,
        verbose_name="تسویه شده؟"
    )

    paid_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ پرداخت"
    )

    class Meta:
        verbose_name = "رزرو اینفلوئنسر"
        verbose_name_plural = "رزروهای اینفلوئنسر"

    def __str__(self):
        return f"{self.campaign} - {self.channel.channel_name} - {self.channel.platform}"

    def save(self, *args, **kwargs):

        if not self.tracking_code:
            self.tracking_code = uuid.uuid4().hex[:8]
        try:
            super().save(*args, **kwargs)

        except IntegrityError:
            self.tracking_code = uuid.uuid4().hex[:8]
            super().save(*args, **kwargs)

    def has_report(self):
        return True if self.report else False

    def set_completed(self):
        """تغییر وضعیت به انجام شده (پرداخت توسط سیگنال انجام می‌شه)"""
        if self.status != self.Status.COMPLETED:
            self.status = self.Status.COMPLETED
            self.save()

    def uniq_url(self,):
        from django.conf import settings
        if not self.tracking_code:
            return "#"   # یا None
        return f"{settings.SITE_URL}/campaigns/r/{self.tracking_code}"


class CampaignContent(models.Model):
    campaign = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name="content",
        verbose_name=_("کمپین")
    )

    media = models.FileField(
        upload_to="campaign/content_media/",
        verbose_name=_("عکس یا ویدیو")
    )

    caption = models.TextField(
        verbose_name=_("متن کامل تبلیغ")
    )

    link = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("لینک مقصد")
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("توضیحات برای اینفلوئنسر")
    )

    # -------- UTM --------

    utm_enabled = models.BooleanField(
        default=False,
        verbose_name=_("فعال سازی UTM")
    )

    utm_source = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="utm_source"
    )

    utm_medium = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="utm_medium"
    )

    utm_campaign = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="utm_campaign"
    )

    utm_content = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="utm_content"
    )

    utm_term = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="utm_term"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name=_("تاریخ ایجاد")
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name=_("آخرین ویرایش")
    )

    class Meta:
        verbose_name = _("محتوای کمپین")
        verbose_name_plural = _("محتواهای کمپین")

    def __str__(self):
        return f"محتوای کمپین #{self.campaign_id}"

    def get_utm_link(self, campaign_influencer):
        base_url = self.link

        campaign = campaign_influencer.campaign
        channel = campaign_influencer.channel

        utm_params = {
            "utm_source": channel.platform.slug,
            "utm_medium": channel.channel_id,
            "utm_campaign": campaign.id,
            "utm_content": f"influencer_{channel.id}",
        }

        query_string = urlencode(utm_params)

        return f"{base_url}?{query_string}"

    @property
    def is_video(self):
        if not self.media:
            return False

        ext = os.path.splitext(self.media.name)[1].lower()
        return ext in [".mp4", ".mov", ".webm", ".mkv"]


class CampaignTrackingLink(models.Model):
    campaign_influencer = models.OneToOneField(
        CampaignInfluencer,
        on_delete=models.CASCADE,
        related_name="tracking_link"
    )

    clicks = models.PositiveIntegerField(
        default=0
    )

    unique_clicks = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "لینک ردیابی"
        verbose_name_plural = "لینک های ردیابی"

    def __str__(self):
        return f"{self.campaign_influencer.tracking_code}"


class CampaignClick(models.Model):
    tracking_link = models.ForeignKey(
        CampaignTrackingLink,
        on_delete=models.CASCADE,
        related_name="click_logs"
    )

    ip_address = models.GenericIPAddressField()

    user_agent = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "کلیک کمپین"
        verbose_name_plural = "کلیک های کمپین"
        indexes = [
            models.Index(fields=["tracking_link", "ip_address"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.ip_address} - {self.tracking_link}"


class CampaignInvoice(models.Model):
    campaign = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name="invoice",
        verbose_name="کمپین"
    )

    influencer_cost = models.PositiveBigIntegerField(
        verbose_name="هزینه اینفلوئنسر"
    )

    content_cost = models.PositiveBigIntegerField(
        verbose_name="هزینه تولید محتوا"
    )

    commission = models.PositiveBigIntegerField(
        verbose_name="کمیسیون پلتفرم"
    )

    discount_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="تخفیف"
    )

    total_amount = models.PositiveBigIntegerField(
        verbose_name="مبلغ کل"
    )

    payable_amount = models.PositiveBigIntegerField(
        verbose_name="مبلغ قابل پرداخت"
    )

    is_paid = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="پرداخت شده"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )

    class Meta:
        verbose_name = "فاکتور کمپین"
        verbose_name_plural = "فاکتورهای کمپین"

    def payable_amount_display(self):
        return f"{self.payable_amount:,} تومان"


class Coupon(models.Model):
    class Scope(models.TextChoices):
        INFLUENCER = "influencer", "اینفلوئنسر"
        CONTENT_TEAM = "content_team", "تیم محتوا"
        PLATFORM = "platform", "پلتفرم"

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "درصدی"
        FIXED = "fixed", "مبلغ ثابت"

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="کد"
    )

    scope = models.CharField(
        max_length=20,
        choices=Scope.choices,
        verbose_name="نوع تخفیف"
    )

    channel = models.ForeignKey(
        "influencers.InfluencerChannel",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="coupons",
        verbose_name="اینفلوئنسر"
    )

    team = models.ForeignKey(
        'content_team.ContentTeam',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="coupons",
        verbose_name="تیم محتوا"
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        verbose_name="نوع مقدار تخفیف"
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="مقدار"
    )

    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="حداکثر استفاده"
    )

    used_count = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد استفاده"
    )

    expires_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ انقضا"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال"
    )

    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"

    def calculate_discount(self, amount):
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return int(amount * (float(self.value) / 100))

        return int(self.value)

    def is_valid(self):

        if not self.is_active:
            return False

        if self.expires_at and self.expires_at < timezone.now():
            return False

        if self.max_uses and self.used_count >= self.max_uses:
            return False

        return True


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"

    class Method(models.TextChoices):
        GATEWAY = "gateway", "درگاه پرداخت"
        WALLET = "wallet", "کیف پول"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="کاربر"
    )

    invoice = models.ForeignKey(
        CampaignInvoice,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="فاکتور"
    )

    amount = models.DecimalField(
        _('مبلغ'),
        max_digits=12,
        decimal_places=0
    )

    payment_method = models.CharField(
        max_length=20,
        choices=Method.choices,
        verbose_name="روش پرداخت"
    )

    authority = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="authority"
    )

    ref_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ref id"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="وضعیت"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )

    class Meta:
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
