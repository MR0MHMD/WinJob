from core.utils.utils import generate_and_save_qr, get_site_logo_path, get_default_qr_colors
from django.utils.translation import gettext_lazy as _
from gamification.mixins import GamificationMixin
from django_jalali.db import models as jmodels
from django_resized import ResizedImageField
from django.conf import settings
from django.db.models import Avg
from django.urls import reverse
from django.db import models


class InfluencerProfile(models.Model):
    user = models.OneToOneField(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='influencer_profile',
        verbose_name=_('کاربر')
    )
    full_name = models.CharField(_('اسم کامل کانال/پیج'), max_length=200)
    description = models.TextField(_('توضیحات'), blank=True)
    is_active = models.BooleanField(_('فعال'), default=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('اینفلوئنسر')
        verbose_name_plural = _('اینفلوئنسرها')
        ordering = ['-created_at']

    @property
    def completed_campaigns(self):
        return self.channels.filter(
            campaign_bookings__status='completed'
        ).count()

    def __str__(self):
        return self.full_name


class InfluencerChannel(GamificationMixin, models.Model):
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
        verbose_name = _('کانال اینفلوئنسر')
        verbose_name_plural = _('کانال‌های اینفلوئنسر')
        unique_together = [('influencer', 'platform', 'channel_id')]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['platform']),
            models.Index(fields=['province']),
            models.Index(fields=['category']),
            models.Index(fields=['followers_count']),
        ]

    def __str__(self):
        return f"{self.influencer.full_name} - {self.platform.name} ({self.channel_id})"

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


class InfluencerServiceRate(models.Model):
    channel = models.ForeignKey('InfluencerChannel', on_delete=models.CASCADE,
                                related_name='service_rates', verbose_name=_('کانال'))
    ad_type = models.ForeignKey('campaigns.AdType', on_delete=models.CASCADE,
                                related_name='influencer_rates', verbose_name=_('نوع تبلیغ'))
    price = models.DecimalField(_('قیمت'), max_digits=12, decimal_places=0,
                                help_text=_('قیمت به تومان'))
    is_active = models.BooleanField(_('فعال'), default=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('نرخ خدمت اینفلوئنسر')
        verbose_name_plural = _('نرخ‌های خدمات اینفلوئنسر')
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


class CampaignReport(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار بررسی'
        APPROVED = 'approved', 'تأیید شد'
        REJECTED = 'rejected', 'رد شد'

    campaign_influencer = models.OneToOneField(
        "campaigns.CampaignInfluencer",
        on_delete=models.CASCADE,
        related_name='report',
        verbose_name='سفارش'
    )

    post_link = models.URLField(verbose_name='لینک پست')
    screenshot = models.ImageField(upload_to='campaign_reports/screenshots/')

    # وضعیت نهایی گزارش (بعد از بررسی خودکار یا دستی)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='وضعیت بررسی'
    )

    # نتایج بررسی خودکار (توسط n8n پر می‌شه)
    auto_check_details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='جزئیات بررسی خودکار'
    )

    admin_notes = models.TextField(blank=True, verbose_name='یادداشت ادمین')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'گزارش کمپین'
        verbose_name_plural = 'گزارش‌های کمپین'


class InfluencerReview(models.Model):
    """
    نظرات و امتیاز تبلیغ‌دهندگان درباره اینفلوئنسرها
    """

    channel = models.ForeignKey(
        'InfluencerChannel',
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('کانال اینفلوئنسر'),
    )

    campaign_booking = models.OneToOneField(
        'campaigns.CampaignInfluencer',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='review',
        verbose_name=_('رزرو کمپین')
    )

    advertiser = models.ForeignKey(
        'advertisers.AdvertiserProfile',
        on_delete=models.CASCADE,
        related_name='influencer_reviews',
        verbose_name=_('تبلیغ‌دهنده')
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
        verbose_name = _('نظر درباره اینفلوئنسر')
        verbose_name_plural = _('نظرات درباره اینفلوئنسرها')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
            models.Index(fields=['channel', '-created_at']),
        ]

    def __str__(self):
        return f"نظر {self.advertiser.user.nickname} برای {self.channel.channel_name} - {self.rating}/5"
