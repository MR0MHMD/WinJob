from core.utils.utils import generate_and_save_qr, get_site_logo_path, get_default_qr_colors
from django.utils.translation import gettext_lazy as _
from gamification.mixins import GamificationMixin
from django_jalali.db import models as jmodels
from django_resized import ResizedImageField
from django.db import models, IntegrityError
from django.conf import settings
from django.db.models import Avg
from django.urls import reverse
import uuid


class InfluencerProfile(models.Model):
    user = models.OneToOneField(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='influencer_profile',
        verbose_name=_('کاربر')
    )
    is_active = models.BooleanField(_('فعال'), default=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('پروفایل ناشر')
        verbose_name_plural = _('پروفایل ناشران')
        ordering = ['-created_at']

    @property
    def completed_campaigns(self):
        return self.channels.filter(
            campaign_bookings__status='completed'
        ).count()

    def __str__(self):
        return f"{self.user.nickname or self.user.phone_number} ناشر"


class Channel(GamificationMixin, models.Model):
    STATUS_CHOICES = (
        ('pending', _('در انتظار تایید')),
        ('approved', _('تایید شده')),
        ('rejected', _('رد شده')),
    )

    influencer = models.ForeignKey('InfluencerProfile', on_delete=models.CASCADE,
                                   related_name='channels', verbose_name=_('اینفلوئنسر'))
    platform = models.ForeignKey('core.Platform', on_delete=models.CASCADE,
                                 related_name='influencer_channels', verbose_name=_('پلتفرم'))

    province = models.ForeignKey('core.Province', on_delete=models.CASCADE, related_name="influencers",
                                 verbose_name=_('استان'), null=True, blank=True)
    category = models.ForeignKey('core.Category', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name=_('دسته‌بندی محتوایی'), related_name='influencer_channel')

    channel_id = models.CharField(_('آیدی کانال/پیج'), max_length=100,
                                  help_text=_('مثال: @example یا t.me/example'))
    channel_name = models.CharField(_('نام کانال/پیج'), max_length=100,
                                    help_text=_('مثال: خبرگزاری فارس'))

    avatar = ResizedImageField(
        _('تصویر پروفایل کانال یا پیج'),
        upload_to="influencers/channels_avatar",
        size=[500, 500],
        scale=1,
        crop=['middle', 'center'],
        null=True,
        blank=True
    )

    qr_code = models.ImageField(
        _('QR Code'),
        upload_to='influencers/qr_codes/',
        blank=True,
        null=True,
        help_text=_('QR Code برای اشتراک‌گذاری پروفایل کانال')
    )

    bio = models.TextField(
        _('درباره کانال'),
        max_length=800,
        blank=True,
        null=True,
        help_text=_('توضیحات مختصر درباره کانال، موضوع محتوا، مخاطبان هدف و ...')
    )

    url = models.URLField(_('آدرس کانال'), blank=True, null=True)
    followers_count = models.PositiveIntegerField(_('تعداد فالوور/مشترک'), default=0)
    status = models.CharField(_('وضعیت'), max_length=20, choices=STATUS_CHOICES, default='pending', )
    is_active = models.BooleanField(_('فعال'), default=True)
    verification_code = models.CharField(max_length=6, blank=True, null=True, verbose_name="کد تأیید کانال")
    verification_code_created_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name="زمان ایجاد کد تأیید")
    verification_failed_attempts = models.PositiveSmallIntegerField(default=0,
                                                                    verbose_name="تعداد تلاش‌های ناموفق تأیید")
    rejected_at = jmodels.jDateTimeField(_("زمان رد شدن کانال"), null=True, blank=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('کانال')
        verbose_name_plural = _('کانال ها')
        unique_together = [('influencer', 'platform', 'channel_id')]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['platform']),
            models.Index(fields=['province']),
            models.Index(fields=['category']),
            models.Index(fields=['followers_count']),
        ]

    def __str__(self):
        return f"{self.channel_name} - {self.platform.name}"

    def get_absolute_url(self):
        return reverse('influencers:channel_detail', kwargs={'channel_id': self.id})

    def generate_qr(self, force=False):
        """
        تولید و ذخیره QR Code برای کانال
        """

        if self.qr_code and not force:
            return

        url = f"{settings.SITE_URL}{self.get_absolute_url()}"

        logo_path = get_site_logo_path()
        color1, color2, gradient_direction = get_default_qr_colors()

        filename = f'channel_{self.id}_{self.platform.slug}.png'
        qr_file = generate_and_save_qr(
            data=url,
            filename=filename,
            logo_path=logo_path,
            color1=color1,
            color2=color2,
            gradient_direction=gradient_direction,
            use_gradient=True
        )

        self.qr_code.save(filename, qr_file, save=False)
        self.save(update_fields=['qr_code'])

    def followers_formatted(self):
        if self.followers_count >= 1000000:
            return f"{self.followers_count / 1000000:.1f}M"
        elif self.followers_count >= 1000:
            return f"{self.followers_count / 1000:.1f}K"
        return str(self.followers_count)

    def get_full_location(self):
        return {self.province}

    followers_formatted.short_description = _('فالوورها')

    @property
    def avg_rating(self):
        if hasattr(self, '_avg_rating') and self._avg_rating is not None:
            return round(self._avg_rating, 1)
        avg = self.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg is not None else None

    @property
    def reviews_count(self):
        return self.reviews.count()


class ChannelServiceRate(models.Model):
    channel = models.ForeignKey('Channel', on_delete=models.CASCADE,
                                related_name='service_rates', verbose_name=_('کانال'))
    ad_type = models.ForeignKey('core.AdType', on_delete=models.CASCADE,
                                related_name='influencer_rates', verbose_name=_('نوع تبلیغ'))
    price = models.DecimalField(_('قیمت'), max_digits=12, decimal_places=0,
                                help_text=_('قیمت به تومان'))
    is_active = models.BooleanField(_('فعال'), default=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('نرخ خدمت')
        verbose_name_plural = _('نرخ خدمات')
        unique_together = [('channel', 'ad_type')]
        ordering = ['ad_type']

    def __str__(self):
        return f"{self.channel} - {self.ad_type.name} - {self.price:,} تومان"

    def formatted_price(self):
        if self.price is None:
            return "-"
        if self.price == 0:
            return "رایگان 🎁"
        return f"{self.price:,} تومان"

    formatted_price.short_description = _('قیمت')


class ChannelReview(models.Model):
    """
    نظرات و امتیاز تبلیغ دهندگان درباره اینفلوئنسرها
    """

    channel = models.ForeignKey(
        'Channel',
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('کانال اینفلوئنسر'),
    )

    campaign_booking = models.OneToOneField(
        'ChannelBooking',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='review',
        verbose_name=_('رزرو کمپین')
    )

    advertiser = models.ForeignKey(
        'advertisers.AdvertiserProfile',
        on_delete=models.CASCADE,
        related_name='influencer_reviews',
        verbose_name=_('تبلیغ دهنده')
    )

    rating = models.PositiveSmallIntegerField(
        _('امتیاز'),
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text=_('از 1 تا 5')
    )

    comment = models.TextField(
        _('نظر'), max_length=500
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ثبت'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('بازخورد کانال')
        verbose_name_plural = _('بازخورد کانال ها')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
            models.Index(fields=['channel', '-created_at']),
        ]

    def __str__(self):
        return f"نظر {self.advertiser.user.nickname} برای {self.channel.channel_name} - {self.rating}/5"


class ChannelBooking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        ACCEPTED = "accepted", "پذیرفته شد"
        REJECTED = "rejected", "رد شد"
        COMPLETED = "completed", "انجام شد"
        REPLACED = "replaced", "جایگزین شد"

    campaign = models.ForeignKey(
        'campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name="influencer_bookings",
        verbose_name="کمپین"
    )

    channel = models.ForeignKey(
        'influencers.Channel',
        on_delete=models.PROTECT,
        related_name="campaign_bookings",
        verbose_name="کانال اینفلوئنسر"
    )

    service_rate = models.ForeignKey(
        'influencers.ChannelServiceRate',
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

    rejection_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="دلیل رد سفارش"
    )
    rejected_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ رد"
    )

    class Meta:
        verbose_name = "رزرو کانال"
        verbose_name_plural = "رزرو کانال ها"

    def __str__(self):
        return f"{self.campaign} - {self.channel.channel_name} - {self.channel.platform}"

    def get_absolute_url(self):
        return reverse('influencers:order_detail', kwargs={'order_id': self.id})

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

    def uniq_url(self, ):
        from django.conf import settings
        if not self.tracking_code:
            return "#"  # یا None
        return f"{settings.SITE_URL}/campaigns/r/{self.tracking_code}"
