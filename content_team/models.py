from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django_jalali.db import models as jmodels
from django_resized import ResizedImageField
from core.utils import generate_random_slug
from .utils import content_order_file_path
from django.db.models import Sum
from django.db import models
from decimal import Decimal
import mimetypes


class ContentTeam(models.Model):
    """
    مدل تیم تولید محتوا - توسط ادمین ایجاد می‌شود
    """
    name = models.CharField(
        _('نام تیم'),
        max_length=200
    )
    slug = models.SlugField(
        _('شناسه'),
        unique=True,
        allow_unicode=True,
        blank=True,
        default=generate_random_slug
    )

    description = models.TextField(
        _('توضیحات'),
        blank=True
    )
    logo = ResizedImageField(_('لوگو'), upload_to='content_team/logos/',
                             size=[500, 500], scale=1,
                             crop=['middle', 'center'],
                             null=True, blank=True)

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )
    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )
    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('تیم تولید محتوا')
        verbose_name_plural = _('تیم‌های تولید محتوا')
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_total_revenue_percent(self):
        """مجموع درصد سهام اعضای فعال تیم"""
        total = self.members.filter(is_active=True).aggregate(
            total=Sum('revenue_share_percent')
        )['total'] or 0
        return total

    def is_revenue_share_valid(self):
        """آیا مجموع درصدها دقیقاً ۱۰۰ هست؟"""
        return self.get_total_revenue_percent() == 100

    def clean(self):
        """اعتبارسنجی در سطح تیم"""
        super().clean()
        total_percent = self.get_total_revenue_percent()

        if self.members.filter(is_active=True).exists() and total_percent != 100:
            raise ValidationError(
                f'مجموع درصد سهام اعضای فعال تیم باید دقیقاً ۱۰۰ باشد (در حال حاضر: {total_percent}%)'
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_random_slug()
        super().save(*args, **kwargs)

    @property
    def avg_rating(self):
        """میانگین امتیاز تیم"""
        result = self.reviews.aggregate(avg=models.Avg('rating'))
        return round(result['avg'], 1) if result['avg'] else None

    @property
    def completed_orders_count(self):
        """تعداد سفارشات تکمیل شده"""
        return self.orders.filter(status='completed').count()

    @property
    def members_count(self):
        return self.members.filter(is_active=True).count()


class ContentTeamMember(models.Model):
    """
    اعضای تیم تولید محتوا
    """

    class Role(models.TextChoices):
        MANAGER = 'manager', _('مدیر تیم')
        EDITOR = 'editor', _('ادیتور')
        WRITER = 'writer', _('نویسنده')
        DESIGNER = 'designer', _('طراح')
        VIDEOGRAPHER = 'videographer', _('فیلمبردار')
        OTHER = 'other', _('سایر')

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name=_('تیم')
    )

    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE, related_name='team_member',
                                verbose_name=_('کاربر'))

    role = models.CharField(
        _('نقش'),
        max_length=50,
        choices=Role.choices
    )

    revenue_share_percent = models.PositiveSmallIntegerField(
        _('درصد سهم از درآمد'),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('درصدی که این عضو از هر سفارش دریافت می‌کند (۰ تا ۱۰۰)')
    )

    bio = models.TextField(
        _('بیوگرافی'),
        blank=True
    )

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('عضو تیم تولید محتوا')
        verbose_name_plural = _('اعضای تیم تولید محتوا')
        ordering = ['team', 'created_at']

    def __str__(self):
        return f"{self.user} - {self.team.name}"

    def clean(self):
        """اعتبارسنجی در سطح مدل"""
        if self.revenue_share_percent > 100:
            raise ValidationError({
                'revenue_share_percent': 'درصد سهم نمی‌تواند بیشتر از ۱۰۰ باشد.'
            })

        if self.is_active and self.revenue_share_percent > 0:
            other_members_sum = ContentTeamMember.objects.filter(
                team=self.team,
                is_active=True
            ).exclude(pk=self.pk).aggregate(
                total=Sum('revenue_share_percent')
            )['total'] or 0

            if other_members_sum + self.revenue_share_percent > 100:
                raise ValidationError({
                    'revenue_share_percent': f'مجموع درصد سهام اعضای فعال تیم نمی‌تواند از ۱۰۰ بیشتر شود. (در حال حاضر {other_members_sum}% + {self.revenue_share_percent}% = {other_members_sum + self.revenue_share_percent}%)'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def is_manager(self):
        return self.role == self.Role.MANAGER and self.is_active


class ContentServiceType(models.Model):
    """
    انواع خدمات تولید محتوا - توسط ادمین تعریف می‌شود
    مثل: طراحی استوری، تولید ویدیو، موشن گرافیک، عکاسی و...
    """
    ad_type = models.ManyToManyField(
        "campaigns.AdType",
        verbose_name=_('نوع تبلیغ'),
        related_name='content_service_type',
    )

    name = models.CharField(
        _('نام خدمت'),
        max_length=100,
        unique=True
    )
    slug = models.SlugField(
        _('شناسه'),
        unique=True,
        allow_unicode=True
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

    unit = models.CharField(_("واحد"), max_length=20, choices=[("minute", "دقیقه"), ("project", "پروژه")])

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )
    display_order = models.PositiveIntegerField(
        _('ترتیب نمایش'),
        default=0
    )
    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('نوع خدمت تولید محتوا')
        verbose_name_plural = _('انواع خدمات تولید محتوا')
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class ContentServicePlan(models.Model):
    """
    پلن‌های قیمت‌گذاری خدمات تیم‌های تولید محتوا
    هر تیم برای هر خدمت می‌تونه تا ۳ پلن تعریف کنه
    مدیر تیم می‌تونه پلن‌ها رو ایجاد و مدیریت کنه
    """

    team = models.ForeignKey(
        'ContentTeam',
        on_delete=models.CASCADE,
        related_name='service_plans',
        verbose_name=_('تیم')
    )

    service_type = models.ForeignKey(
        'ContentServiceType',
        on_delete=models.CASCADE,
        related_name='plans',
        verbose_name=_('نوع خدمت')
    )

    name = models.CharField(
        _('نام پلن'),
        max_length=200,
        help_text=_('مثلاً: "پلن اقتصادی - دو دوربین" یا "پکیج حرفه‌ای - چهار دوربین"')
    )

    description = models.TextField(
        _('توضیحات پلن'),
        help_text=_('توضیح کامل این پلن شامل چه چیزایی میشه')
    )

    features = models.JSONField(
        _('ویژگی‌ها'),
        default=list,
        blank=True,
        help_text=_('لیست ویژگی‌های این پلن. مثال: ["۲ دوربین 4K", "تدوین حرفه‌ای", "موزیک متن", "تحویل ۳ روزه"]')
    )

    price_per_unit = models.DecimalField(
        _('قیمت به ازای واحد (تومان)'),
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_('قیمت برای هر دقیقه/پروژه')
    )

    estimated_delivery_days = models.PositiveIntegerField(
        _('مدت آماده سازی'),
        default=5,
        validators=[MinValueValidator(1)],
        help_text=_('حداکثر چند روز کاری طول میکشه تا تحویل داده بشه')
    )

    is_active = models.BooleanField(
        _('فعال'),
        default=True,
        help_text=_('آیا این پلن در حال حاضر قابل سفارش هست؟')
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ بروزرسانی'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('پلن خدمت')
        verbose_name_plural = _('پلن‌های خدمات')
        unique_together = [
            ['team', 'service_type', 'name']  # هر تیم برای هر خدمت نمیتونه دو پلن با نام یکسان داشته باشه
        ]
        ordering = ['team', 'service_type', 'price_per_unit']  # مرتب‌سازی بر اساس قیمت از کم به زیاد
        indexes = [
            models.Index(fields=['team', 'service_type', 'is_active']),
            models.Index(fields=['price_per_unit']),
        ]

    def __str__(self):
        return f"{self.team.name} - {self.service_type.name} - {self.name}"

    def clean(self):
        """اعتبارسنجی پلن"""
        super().clean()

        # بررسی تعداد پلن‌های فعال برای این تیم و خدمت
        active_plans_count = ContentServicePlan.objects.filter(
            team=self.team,
            service_type=self.service_type,
            is_active=True
        ).exclude(pk=self.pk).count()

        if self.is_active and not self.pk:  # پلن جدید
            if active_plans_count >= 3:
                raise ValidationError(
                    _('هر تیم برای هر خدمت حداکثر می‌تونه ۳ پلن فعال داشته باشه.')
                )
        elif self.is_active and self.pk:  # ویرایش پلن موجود
            if active_plans_count > 3:
                raise ValidationError(
                    _('نمیشه بیشتر از ۳ پلن فعال برای یک خدمت داشت.')
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def price_display(self):
        """نمایش قیمت به صورت خوانا"""
        if self.price_per_unit is not None:
            return f"{self.price_per_unit:,} تومان"
        return "-"  # یا "نامشخص"

    @property
    def price_per_unit_int(self):
        """قیمت به صورت عدد صحیح برای محاسبات"""
        return int(self.price_per_unit)

    def get_features_list(self):
        """دریافت لیست ویژگی‌ها"""
        if isinstance(self.features, list):
            return self.features
        elif isinstance(self.features, str):
            try:
                import json
                return json.loads(self.features)
            except:
                return [self.features]
        return []


class ContentOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        REVIEW_PENDING = "review_pending", "در انتظار ویراش"
        IN_PROGRESS = "in_progress", "در حال انجام"
        COMPLETED = "completed", "انجام شده"
        CANCELLED = "cancelled", "لغو شده"

    campaign = models.ForeignKey(
        'campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name="content_orders",
        verbose_name="کمپین"
    )

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="تیم تولید محتوا"
    )

    plan = models.ForeignKey(
        ContentServicePlan,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="پلن انتخابی"
    )

    price = models.PositiveBigIntegerField(
        verbose_name="قیمت"
    )

    minutes = models.PositiveSmallIntegerField(
        verbose_name=_('دقیقه'),
        null=True, blank=True
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
        verbose_name = "سفارش تولید محتوا"
        verbose_name_plural = "سفارش‌های تولید محتوا"

    def __str__(self):
        return f' سفارش {self.campaign.name} - {self.campaign.advertiser.user.nickname}'

    def save(self, *args, **kwargs):
        """محاسبه خودکار قیمت قبل از ذخیره"""
        if self.plan and not self.price:
            if self.minutes:
                self.price = int(self.plan.price_per_unit) * self.minutes
            else:
                self.price = int(self.plan.price_per_unit)
        super().save(*args, **kwargs)


class ContentOrderDescription(models.Model):
    """
    بریف ساختارمند سفارش تولید محتوا
    اطلاعات دقیق‌تر از نیاز کاربر برای تیم تولید محتوا
    """

    class ContentGoal(models.TextChoices):
        PRODUCT_INTRO = 'product_intro', _('معرفی محصول یا خدمت')
        BRAND_AWARENESS = 'brand_awareness', _('افزایش آگاهی از برند')
        SALE_CAMPAIGN = 'sale_campaign', _('کمپین فروش یا تخفیف')
        EDUCATIONAL = 'educational', _('محتوای آموزشی')
        ENGAGEMENT = 'engagement', _('افزایش تعامل مخاطب')
        OTHER = 'other', _('سایر')

    class ContentTone(models.TextChoices):
        FORMAL = 'formal', _('رسمی')
        FRIENDLY = 'friendly', _('صمیمی')
        HUMOROUS = 'humorous', _('طنز')
        EMOTIONAL = 'emotional', _('احساسی')
        MOTIVATIONAL = 'motivational', _('انگیزشی')

    order = models.OneToOneField(
        ContentOrder,
        on_delete=models.CASCADE,
        related_name='brief',
        verbose_name=_('سفارش')
    )

    goal = models.CharField(
        _('هدف محتوا'),
        max_length=50,
        choices=ContentGoal.choices,
    )
    goal_description = models.CharField(
        _('توضیح هدف'),
        max_length=200,
        blank=True, null=True,
        help_text=_('اگر "سایر" انتخاب کردید توضیح دهید')
    )

    tone = models.CharField(
        _('لحن محتوا'),
        max_length=30,
        choices=ContentTone.choices,
    )

    brand_name = models.CharField(
        _('نام برند یا محصول'),
        max_length=100,
    )

    hashtags = models.CharField(
        _('هشتگ‌ها'),
        max_length=500,
        blank=True,
        help_text=_('مثلاً: #برند_من #تخفیف')
    )

    reference_links = models.TextField(
        _('لینک‌های مرجع'),
        blank=True,
        help_text=_('لینک نمونه‌کارهای مشابه که دوست دارید')
    )

    target_audience = models.CharField(
        _('مخاطب هدف'),
        max_length=300,
        blank=True,
        help_text=_('مثلاً: زنان ۲۵-۳۵ ساله علاقه‌مند به مد')
    )

    description = models.TextField(
        _('توضیحات کامل'),
        help_text=_('هر اطلاعات دیگری که تیم باید بداند')
    )

    do_not_include = models.TextField(
        _('چه چیزهایی نباشد؟'),
        blank=True,
        help_text=_('مثلاً: رنگ قرمز، افکت‌های بصری خاص، لوگوی رقبا')
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ثبت'),
        auto_now_add=True
    )
    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('توضیح سفارش')
        verbose_name_plural = _('توضیحات سفارش')

    def __str__(self):
        return f"بریف سفارش {self.order.id}"


class ContentOrderFile(models.Model):
    """
    فایل‌های پیوست سفارش تولید محتوا
    کاربر می‌تواند چندین فایل آپلود کند
    """

    class FileType(models.TextChoices):
        IMAGE = 'image', _('تصویر')
        VIDEO = 'video', _('ویدیو')
        AUDIO = 'audio', _('صدا')
        DOCUMENT = 'document', _('سند')
        OTHER = 'other', _('سایر')

    order = models.ForeignKey(
        ContentOrder,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name=_('سفارش')
    )

    file = models.FileField(
        _('فایل'),
        upload_to=content_order_file_path
    )

    file_type = models.CharField(
        _('نوع فایل'),
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER
    )

    original_name = models.CharField(
        _('نام اصلی فایل'),
        max_length=255,
        blank=True
    )

    description = models.CharField(
        _('توضیح فایل'),
        max_length=200,
        blank=True,
        help_text=_('این فایل چیست؟ مثلاً: لوگوی برند')
    )

    file_size = models.PositiveIntegerField(
        _('حجم فایل (بایت)'),
        null=True,
        blank=True
    )

    uploaded_at = jmodels.jDateTimeField(
        _('تاریخ آپلود'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('فایل سفارش')
        verbose_name_plural = _('فایل‌های سفارش')
        ordering = ['uploaded_at']

    def __str__(self):
        return f"فایل {self.original_name} - سفارش {self.order.id}"

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name.split('/')[-1]
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def file_size_display(self):
        """نمایش حجم فایل به صورت خوانا"""
        if not self.file_size:
            return 'نامشخص'
        size = self.file_size
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} گیگابایت"

    @property
    def mime_type(self):
        mime, _ = mimetypes.guess_type(self.file.name)
        return mime or self.file_type


class TeamReview(models.Model):
    """
    نظرات و امتیازات تیم‌های تولید محتوا
    """
    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('تیم')
    )
    order = models.OneToOneField(
        ContentOrder,
        on_delete=models.CASCADE,
        related_name='review',
        verbose_name=_('سفارش')
    )
    advertiser = models.ForeignKey(
        'advertisers.AdvertiserProfile',
        on_delete=models.CASCADE,
        related_name='team_reviews',
        verbose_name=_('تبلیغ‌دهنده')
    )
    rating = models.PositiveSmallIntegerField(
        _('امتیاز'),
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text=_('از 1 تا 5')
    )
    comment = models.TextField(
        _('نظر'),
        blank=True
    )
    created_at = jmodels.jDateTimeField(
        _('تاریخ ثبت'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('نظر درباره تیم')
        verbose_name_plural = _('نظرات درباره تیم‌ها')
        ordering = ['-created_at']

    def __str__(self):
        return f"نظر {self.advertiser.user.nickname} برای {self.team.name} - {self.rating}/5"


class TeamJoinRequest(models.Model):
    """
    مدل درخواست عضویت در تیم تولید محتوا
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار بررسی')
        APPROVED = 'approved', _('تایید شده')
        REJECTED = 'rejected', _('رد شده')

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='team_join_requests',
        verbose_name=_('کاربر درخواست‌دهنده')
    )

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='join_requests',
        verbose_name=_('تیم')
    )

    status = models.CharField(
        _('وضعیت'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ درخواست'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('درخواست عضویت در تیم')
        verbose_name_plural = _('درخواست‌های عضویت در تیم')
        ordering = ['-created_at']
        unique_together = ['team', 'user']

    def __str__(self):
        return f"درخواست {self.user.nickname} برای عضویت در {self.team.name} - {self.get_status_display()}"


class ContentOrderRevision(models.Model):
    """
    درخواست ویرایش سفارش تولید محتوا
    کاربر می‌تواند بعد از تحویل، درخواست ویرایش بدهد
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار بررسی')
        ACCEPTED = 'accepted', _('پذیرفته شده')
        REJECTED = 'rejected', _('رد شده')
        DONE = 'done', _('انجام شد')

    order = models.ForeignKey(
        'ContentOrder',
        on_delete=models.CASCADE,
        related_name='revisions',
        verbose_name=_('سفارش')
    )

    requested_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='content_revisions',
        verbose_name=_('درخواست‌کننده')
    )

    feedback = models.TextField(
        _('توضیحات ویرایش'),
        help_text=_('مشخص کنید چه تغییراتی می‌خواهید')
    )

    status = models.CharField(
        _('وضعیت'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    file = models.FileField(
        _('فایل مرجع'),
        upload_to='revision_files/',
        null=True,
        blank=True,
        help_text=_('فایل مرجع برای ویرایش (اختیاری)')
    )

    file_name = models.CharField(
        _('نام فایل'),
        max_length=255,
        blank=True,
        help_text=_('نام اصلی فایل آپلود شده')
    )

    file_size = models.PositiveIntegerField(
        _('حجم فایل (بایت)'),
        null=True,
        blank=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ درخواست'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ بروزرسانی'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('درخواست ویرایش')
        verbose_name_plural = _('درخواست‌های ویرایش')
        ordering = ['-created_at']

    def __str__(self):
        return f"ویرایش سفارش {self.order.id} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = self.file.name.split('/')[-1]
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def file_size_display(self):
        if not self.file_size:
            return 'نامشخص'
        size = self.file_size
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} گیگابایت"


class ContentDelivery(models.Model):
    """
    تحویل نهایی سفارش توسط تیم تولید محتوا
    """

    class DeliveryStatus(models.TextChoices):
        PENDING = 'pending', _('در انتظار تحویل')
        DELIVERED = 'delivered', _('تحویل داده شد')
        PARTIAL = 'partial', _('تحویل بخشی')
        REVISION_REQUESTED = 'revision_requested', _('ویرایش درخواست شده')
        FINAL_ACCEPTED = 'final_accepted', _('تأیید نهایی')

    order = models.OneToOneField(
        'ContentOrder',
        on_delete=models.CASCADE,
        related_name='delivery',
        verbose_name=_('سفارش')
    )

    status = models.CharField(
        _('وضعیت تحویل'),
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True
    )

    file = models.FileField(
        _('فایل تحویلی'),
        upload_to=content_order_file_path,
        null=True,
        blank=True,
        help_text=_('فایل نهایی تحویل شده توسط تیم')
    )

    file_name = models.CharField(
        _('نام فایل'),
        max_length=255,
        blank=True,
        help_text=_('نام اصلی فایل آپلود شده')
    )

    file_size = models.PositiveIntegerField(
        _('حجم فایل (بایت)'),
        null=True,
        blank=True
    )

    delivered_by = models.ForeignKey(
        ContentTeamMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries',
        verbose_name=_('تحویل‌دهنده')
    )

    delivered_at = jmodels.jDateTimeField(
        _('تاریخ تحویل'),
        null=True,
        blank=True
    )

    notes = models.TextField(
        _('توضیحات تحویل'),
        blank=True,
        help_text=_('توضیحات تکمیلی برای سفارش‌دهنده')
    )

    accepted_at = jmodels.jDateTimeField(
        _('تاریخ تأیید نهایی'),
        null=True,
        blank=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ بروزرسانی'),
        auto_now=True
    )

    version = models.PositiveSmallIntegerField(
        _('نسخه'),
        default=1,
        help_text=_('نسخه تحویل سفارش (۱ برای تحویل اولیه، ۲ برای ویرایش اول، و...)')
    )

    class Meta:
        verbose_name = _('تحویل سفارش')
        verbose_name_plural = _('تحویل‌های سفارش')
        ordering = ['-version', '-delivered_at']
        unique_together = [['order', 'version']]

    def __str__(self):
        return f"تحویل سفارش {self.order.id} - نسخه {self.version} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = self.file.name.split('/')[-1]
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def file_size_display(self):
        if not self.file_size:
            return 'نامشخص'
        size = self.file_size
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} گیگابایت"


class ContentPortfolio(models.Model):
    """
    نمونه کارهای تیم تولید محتوا
    """

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='portfolio_items',
        verbose_name=_('تیم')
    )

    title = models.CharField(
        _('عنوان'),
        max_length=200,
        help_text=_('مثلاً: ویدیوی معرفی محصول ایکس')
    )

    description = models.TextField(
        _('توضیحات'),
        blank=True,
        help_text=_('توضیح درباره این نمونه کار')
    )

    media = ResizedImageField(
        _('تصویر نمونه کار'),
        upload_to='team_portfolio/',
        size=[800, 800],
        scale=1,
        crop=['middle', 'center'],
        null=True,
        blank=True
    )

    video_url = models.URLField(
        _('لینک ویدیو'),
        blank=True,
        help_text=_('لینک آپارات، یوتیوب، ویمئو و...')
    )

    external_link = models.URLField(
        _('لینک خارجی'),
        blank=True,
        help_text=_('لینک به نمونه کار در سایت دیگر')
    )

    service_type = models.ForeignKey(
        ContentServiceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='portfolio_items',
        verbose_name=_('نوع خدمت')
    )

    display_order = models.PositiveSmallIntegerField(
        _('ترتیب نمایش'),
        default=0
    )

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('نمونه کار')
        verbose_name_plural = _('نمونه کارها')
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return f"{self.team.name} - {self.title}"
