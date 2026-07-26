from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
import django_jalali.db.models as jmodels
from django.db import models


class BaseScore(models.Model):
    """مدل پایه (Abstract) برای ذخیره فیلدهای مشترک امتیازدهی با ارتباط به Badge"""

    points = models.IntegerField(default=0, verbose_name=_('کل امتیازات'))

    badge = models.ForeignKey(
        'Badge',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('نشان فعلی')
    )
    highest_badge = models.ForeignKey(
        'Badge',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('بالاترین نشان کسب شده')
    )
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name=_('آخرین بروزرسانی'))

    class Meta:
        abstract = True


class AdvertiserScore(BaseScore):
    profile = models.OneToOneField(
        'advertisers.AdvertiserProfile',
        on_delete=models.CASCADE,
        related_name='score',
        verbose_name=_('تبلیغ‌دهنده')
    )

    class Meta:
        verbose_name = _('امتیاز تبلیغ‌دهنده')
        verbose_name_plural = _('امتیازات تبلیغ‌دهندگان')

    def __str__(self):
        return f"{self.profile.business_name}"


class ChannelScore(BaseScore):
    channel = models.OneToOneField(
        'influencers.Channel',
        on_delete=models.CASCADE,
        related_name='score',
        verbose_name=_('کانال اینفلوئنسر')
    )

    class Meta:
        verbose_name = _('امتیاز کانال')
        verbose_name_plural = _('امتیازات کانال‌ها')

    def __str__(self):
        return self.channel.channel_name


class TeamScore(BaseScore):
    team = models.OneToOneField(
        "content_team.ContentTeam",
        on_delete=models.CASCADE,
        related_name='score',
        verbose_name=_('تیم تولید محتوا')
    )

    class Meta:
        verbose_name = _('امتیاز تیم')
        verbose_name_plural = _('امتیازات تیم‌ها')

    def __str__(self):
        return self.team.name


class PointLog(models.Model):
    """ثبت تاریخچه امتیازات با استفاده از روابط جنریک برای اتصال به هر سه مدل بالا"""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    score_profile = GenericForeignKey('content_type', 'object_id')

    points_changed = models.IntegerField(verbose_name=_('تغییرات امتیاز'))
    action_key = models.CharField(max_length=100, verbose_name=_('کلید اکشن'))
    description = models.TextField(verbose_name=_('توضیحات'))
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name=_('تاریخ ثبت'))

    class Meta:
        verbose_name = _('لاگ امتیاز')
        verbose_name_plural = _('لاگ های امتیازات')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]


class Badge(models.Model):
    """
    مدل سطح‌بندی (نشان) با قابلیت آپلود تصویر و تاریخ شمسی
    """
    slug = models.SlugField(
        _('اسلاگ'),
        max_length=50,
        unique=True,
        help_text=_('کد یکتا برای استفاده در برنامه، مثال: bronze, silver, gold')
    )
    name = models.CharField(
        _('نام سطح'),
        max_length=100,
        help_text=_('نام نمایشی، مثال: برنزی، نقره‌ای، طلایی')
    )
    min_points = models.IntegerField(
        _('حداقل امتیاز'),
        default=0,
        help_text=_('حداقل امتیاز مورد نیاز برای کسب این سطح')
    )

    icon = models.ImageField(_('لوگو'), upload_to="badges/icons/", null=True, blank=True)

    description = models.TextField(
        _('توضیحات'),
        blank=True,
        help_text=_('توضیحات این سطح (اختیاری)')
    )
    order = models.PositiveSmallIntegerField(
        _('ترتیب'),
        default=0,
        help_text=_('عدد کوچک‌تر = سطح پایین‌تر')
    )

    is_active = models.BooleanField(_('فعال'), default=True)

    class Meta:
        verbose_name = _('نشان / سطح')
        verbose_name_plural = _('نشان‌ها / سطوح')
        ordering = ['order', 'min_points']

    def __str__(self):
        return f"{self.name} ({self.min_points}+ امتیاز)"

    @property
    def icon_url(self):
        return self.icon.url if self.icon else None
