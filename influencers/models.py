from django.db import models
from django.db.models import Avg
from django.utils.translation import gettext_lazy as _
from django_resized import ResizedImageField
import django_jalali.db.models as jmodels
from accounts.models import CustomUser
from gamification.mixins import GamificationMixin


class InfluencerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='influencer_profile',
                                verbose_name=_('کاربر'))
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

    influencer = models.ForeignKey(InfluencerProfile, on_delete=models.CASCADE,
                                   related_name='channels', verbose_name=_('اینفلوئنسر'))
    platform = models.ForeignKey('plat_form.Platform', on_delete=models.CASCADE,
                                 related_name='influencer_channels', verbose_name=_('پلتفرم'))

    province = models.ForeignKey('location.Province', on_delete=models.CASCADE, related_name="influencers",
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
    url = models.URLField(_('آدرس کانال'), blank=True, null=True)
    followers_count = models.PositiveIntegerField(_('تعداد فالوور/مشترک'), default=0)
    status = models.CharField(_('وضعیت'), max_length=20, choices=STATUS_CHOICES, default='pending', )
    is_active = models.BooleanField(_('فعال'), default=True)
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
    channel = models.ForeignKey(InfluencerChannel, on_delete=models.CASCADE,
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
        PARTIAL = 'partial', 'تأیید جزئی'

    campaign_influencer = models.OneToOneField(
        "campaigns.CampaignInfluencer",
        on_delete=models.CASCADE,
        related_name='report',
        verbose_name='سفارش'
    )

    post_link = models.URLField(
        verbose_name='لینک پست',
        help_text='لینک مستقیم پست منتشر شده'
    )

    screenshot = models.ImageField(
        upload_to='campaign_reports/screenshots/',
        verbose_name='اسکرین‌شات پست'
    )

    link_valid = models.BooleanField(default=False)
    hashtag_match_percent = models.FloatField(default=0)
    text_match_percent = models.FloatField(default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='وضعیت بررسی'
    )

    admin_notes = models.TextField(
        blank=True,
        verbose_name='یادداشت ادمین'
    )

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
        'influencers.InfluencerChannel',
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
