# core/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django_jalali.db import models as jmodels


class Category(models.Model):
    """دسته‌بندی مشترک برای تبلیغ‌دهنده و اینفلوئنسر با قابلیت سلسله‌مراتبی"""

    name = models.CharField(_('نام دسته‌بندی'), max_length=100, unique=True)
    slug = models.SlugField(_('اسلاگ'), max_length=100, unique=True)
    description = models.TextField(_('توضیحات'), blank=True)
    icon = models.CharField(_('آیکون'), max_length=50, blank=True,
                            help_text=_('نام کلاس آیکون (مثلاً: fa-shopping-cart)'))

    parent = models.ForeignKey(
        "self",
        verbose_name=_('دسته‌بندی والد'),
        on_delete=models.CASCADE,
        related_name='children',
        null=True,
        blank=True,
        help_text=_('اگر این دسته زیرمجموعه دسته دیگری است، والد آن را انتخاب کنید')
    )

    order = models.PositiveIntegerField(_('ترتیب نمایش'), default=0)

    is_active = models.BooleanField(_('فعال'), default=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('آخرین ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('دسته‌بندی')
        verbose_name_plural = _('دسته‌بندی‌ها')
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return self.name

    def get_full_path(self):
        """
        بازگرداندن مسیر کامل دسته‌بندی از ریشه تا این دسته
        """
        path = []
        current = self
        while current:
            path.insert(0, current.name)
            current = current.parent
        return ' → '.join(path)

    def get_absolute_url(self):
        """
        آدرس مطلق برای دسته‌بندی (در صورت نیاز)
        """
        return reverse('category_detail', kwargs={'slug': self.slug})

    def get_children_count(self):
        """
        تعداد زیرمجموعه‌های مستقیم
        """
        return self.children.filter(is_active=True).count()

    def get_all_children_count(self):
        """
        تعداد کل زیرمجموعه‌ها (به صورت بازگشتی)
        """
        count = self.get_children_count()
        for child in self.children.filter(is_active=True):
            count += child.get_all_children_count()
        return count

    def get_level(self):
        """
        سطح دسته‌بندی در درخت (ریشه = 0)
        """
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level

    def is_root(self):
        """
        آیا این دسته ریشه است؟
        """
        return self.parent is None

    def is_leaf(self):
        """
        آیا این دسته برگ است (زیرمجموعه ندارد)؟
        """
        return self.get_children_count() == 0

    @property
    def display_name(self):
        """
        نام نمایشی با توجه به سطح
        """
        level = self.get_level()
        prefix = "─ " * level
        return f"{prefix}{self.name}"

    def clean(self):
        """
        اعتبارسنجی برای جلوگیری از حلقه در سلسله‌مراتب
        """
        from django.core.exceptions import ValidationError

        # جلوگیری از انتخاب خود به عنوان والد
        if self.parent == self:
            raise ValidationError({'parent': 'یک دسته‌بندی نمی‌تواند والد خودش باشد.'})

        # جلوگیری از ایجاد حلقه در سلسله‌مراتب
        if self.parent:
            ancestors = []
            current = self.parent
            while current:
                if current == self:
                    raise ValidationError({'parent': 'ایجاد حلقه در سلسله‌مراتب امکان‌پذیر نیست.'})
                ancestors.append(current)
                current = current.parent
