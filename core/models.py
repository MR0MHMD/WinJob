# models.py
from django.db import models
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
