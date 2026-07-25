from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from .validators import validate_ticket_attachment_size


# ==================== مدل‌های موضوع و عنوان تیکت ====================

class TicketCategory(models.Model):
    """دسته‌بندی اصلی (موضوع) تیکت - مثل: مالی، کمپین، حساب کاربری و..."""

    name = models.CharField(
        max_length=255,
        verbose_name=_('نام دسته‌بندی')
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        allow_unicode=True,
        verbose_name=_('اسلاگ')
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('توضیحات')
    )

    icon = models.CharField(
        max_length=50,
        default='fi-help',
        verbose_name=_('آیکون (کلاس finder-icons)'),
        help_text=_('مثال: fi-cash, fi-flag, fi-user')
    )

    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('ترتیب نمایش')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('فعال')
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name=_('تاریخ ایجاد')
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name=_('آخرین بروزرسانی')
    )

    class Meta:
        verbose_name = _('دسته‌بندی تیکت')
        verbose_name_plural = _('دسته‌بندی‌های تیکت')
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    @property
    def active_titles_count(self):
        return self.titles.filter(is_active=True).count()


class TicketTitle(models.Model):
    """عنوان تیکت - زیرمجموعه هر دسته‌بندی"""

    category = models.ForeignKey(
        TicketCategory,
        on_delete=models.CASCADE,
        related_name='titles',
        verbose_name=_('دسته‌بندی')
    )

    name = models.CharField(
        max_length=255,
        verbose_name=_('نام عنوان')
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        allow_unicode=True,
        verbose_name=_('اسلاگ')
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('توضیحات'),
        help_text=_('توضیح مختصر برای کاربر - زیر عنوان نمایش داده میشه')
    )

    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('ترتیب نمایش')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('فعال')
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name=_('تاریخ ایجاد')
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name=_('آخرین بروزرسانی')
    )

    class Meta:
        verbose_name = _('عنوان تیکت')
        verbose_name_plural = _('عناوین تیکت')
        ordering = ['category__order', 'order', 'name']

    def __str__(self):
        return f"{self.category.name} > {self.name}"

    @property
    def faqs_count(self):
        return self.faqs.count()


class TicketFAQ(models.Model):
    """پرسش‌های متداول برای هر عنوان تیکت"""

    title = models.ForeignKey(
        TicketTitle,
        on_delete=models.CASCADE,
        related_name='faqs',
        verbose_name=_('عنوان تیکت')
    )

    question = models.TextField(
        verbose_name=_('سوال')
    )

    answer = models.TextField(
        verbose_name=_('پاسخ')
    )

    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('ترتیب نمایش')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('فعال')
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name=_('تاریخ ایجاد')
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name=_('آخرین بروزرسانی')
    )

    class Meta:
        verbose_name = _('سوال متداول')
        verbose_name_plural = _('سوالات متداول')
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.question[:80]


# ==================== مدل‌های اصلی تیکت ====================

class Ticket(models.Model):
    """تیکت پشتیبانی"""

    class Status(models.TextChoices):
        WAITING_USER = 'waiting_user', _('منتظر پاسخ کاربر')
        WAITING_ADMIN = 'waiting_admin', _('منتظر پاسخ پشتیبانی')
        IN_PROGRESS = 'in_progress', _('در حال بررسی')
        CLOSED = 'closed', _('بسته شده')

    class Priority(models.TextChoices):
        LOW = 'low', _('کم')
        MEDIUM = 'medium', _('متوسط')
        HIGH = 'high', _('زیاد')
        URGENT = 'urgent', _('فوری')

    # کاربری که تیکت رو ایجاد کرده
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name=_('کاربر')
    )

    # ارتباط با مدل‌های جدید
    category = models.ForeignKey(
        TicketCategory,
        on_delete=models.PROTECT,
        related_name='tickets',
        verbose_name=_('موضوع')
    )

    title = models.ForeignKey(
        TicketTitle,
        on_delete=models.PROTECT,
        related_name='tickets',
        verbose_name=_('عنوان تیکت'),
        null=True,
        blank=True
    )

    # عنوان دستی (برای مواردی که تو لیست نیست)
    custom_title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('عنوان سفارشی')
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING_ADMIN,
        db_index=True,
        verbose_name=_('وضعیت')
    )

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name=_('اولویت')
    )

    campaign = models.ForeignKey(
        'campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name=_('کمپین مرتبط')
    )

    # فیلدهای ادمین
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name=_('اختصاص به')
    )

    admin_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('یادداشت ادمین'),
        help_text=_('فقط برای ادمین قابل مشاهده است')
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name=_('تاریخ ایجاد')
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name=_('آخرین بروزرسانی')
    )

    closed_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name=_('تاریخ بسته شدن')
    )

    class Meta:
        verbose_name = _('تیکت')
        verbose_name_plural = _('تیکت‌ها')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', 'status']),
        ]

    def get_absolute_url(self):
        return reverse('tickets:ticket_detail', kwargs={'pk': self.pk})

    def __str__(self):
        title = self.title.name if self.title else self.custom_title or '-'
        return f"#{self.pk} - {title}"

    def get_display_title(self):
        """عنوان نمایشی تیکت"""
        return self.title.name if self.title else self.custom_title or 'بدون عنوان'

    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()

    @property
    def unread_messages_count(self):
        return self.messages.filter(is_read=False, is_admin_reply=True).count()

    @property
    def messages_count(self):
        return self.messages.count()

    @property
    def is_assigned(self):
        return self.assigned_to is not None


class TicketMessage(models.Model):
    """پیام‌های داخل تیکت"""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('تیکت')
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ticket_messages',
        verbose_name=_('فرستنده')
    )

    is_admin_reply = models.BooleanField(
        default=False,
        verbose_name=_('پاسخ ادمین')
    )

    message = models.TextField(
        verbose_name=_('متن پیام')
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name=_('خوانده شده')
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('تاریخ ارسال')
    )

    class Meta:
        verbose_name = _('پیام تیکت')
        verbose_name_plural = _('پیام‌های تیکت')
        ordering = ['created_at']

    def __str__(self):
        return f"پیام #{self.pk} - تیکت #{self.ticket_id}"

    @property
    def sender_name(self):
        if self.is_admin_reply:
            return f"👤 پشتیبانی"
        return f"👤 {self.sender.phone_number}"


class TicketAttachment(models.Model):
    """فایل‌های پیوست تیکت"""

    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('پیام')
    )

    file = models.FileField(
        upload_to='tickets/attachments/%Y/%m/',
        validators=[validate_ticket_attachment_size],
        verbose_name=_('فایل')
    )

    file_name = models.CharField(
        max_length=255,
        verbose_name=_('نام فایل')
    )

    file_size = models.PositiveIntegerField(
        verbose_name=_('حجم فایل (بایت)')
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('تاریخ آپلود')
    )

    class Meta:
        verbose_name = _('پیوست')
        verbose_name_plural = _('پیوست‌ها')

    def __str__(self):
        return self.file_name

    @property
    def file_size_display(self):
        """نمایش خوانای حجم فایل"""
        size = self.file_size
        if size is None:
            return "0 B"

        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def file_extension(self):
        return self.file_name.split('.')[-1].lower() if '.' in self.file_name else ''
