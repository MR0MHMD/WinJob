from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django_jalali.db import models as jmodels


class Category(models.Model):
    """دسته‌بندی ساده برای تبلیغ‌دهنده و اینفلوئنسر"""

    name = models.CharField(_('نام دسته‌بندی'), max_length=100, unique=True)
    slug = models.SlugField(_('اسلاگ'), max_length=100, unique=True)
    description = models.TextField(_('توضیحات'), blank=True)
    icon = models.CharField(_('آیکون'), max_length=50, blank=True)

    order = models.PositiveIntegerField(_('ترتیب نمایش'), default=0)
    is_active = models.BooleanField(_('فعال'), default=True)

    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('آخرین ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('دسته‌بندی')
        verbose_name_plural = _('دسته‌بندی‌ها')
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('category_detail', kwargs={'slug': self.slug})

    @property
    def display_name(self):
        return self.name


class Platform(models.Model):
    name = models.CharField(_("نام"), max_length=50)
    slug = models.SlugField(_("اسلاگ"), max_length=160)
    description = models.TextField(_('توضیحات'), max_length=750)
    logo = models.ImageField(_('لوگو'), upload_to="platform/logos", null=True, blank=True)
    is_active = models.BooleanField(_('فعال باشد؟'), default=True)

    class Meta:
        verbose_name = _('پلتفرم')
        verbose_name_plural = _('پلتفرم ها')
        ordering = ['-is_active', 'name']

    def get_absolute_url(self):
        return reverse('core:landing_page', kwargs={'slug': self.slug})

    def __str__(self):
        return self.name


class Province(models.Model):
    name = models.CharField("نام", max_length=100, unique=True)
    slug = models.SlugField("اسلاگ", max_length=120, unique=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "استان"
        verbose_name_plural = "استان‌ها"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True)
            slug = base_slug
            i = 1
            while Province.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ContentServiceType(models.Model):
    """
    انواع خدمات تولید محتوا - توسط ادمین تعریف می‌شود
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

    allowed_units = models.JSONField(
        _('واحدهای مجاز'),
        default=list,
        blank=True,
        help_text=_('واحدهایی که این سرویس می‌تواند داشته باشد. مثال: ["second", "minute", "quantity"]')
    )

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

    def get_allowed_units_display(self):
        """نمایش واحدهای مجاز به صورت خوانا"""
        unit_labels = {
            'second': 'ثانیه',
            'minute': 'دقیقه',
            'quantity': 'تعدادی'
        }
        return ', '.join([unit_labels.get(u, u) for u in self.allowed_units])
