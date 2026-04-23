from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class Notification(models.Model):
    class Type(models.TextChoices):
        CAMPAIGN_PENDING = 'campaign_pending', 'کمپین در انتظار تایید'
        CAMPAIGN_APPROVED = 'campaign_approved', 'کمپین تایید شد'
        CAMPAIGN_REJECTED = 'campaign_rejected', 'کمپین رد شد'
        CAMPAIGN_COMPLETED = 'campaign_completed', 'کمپین تمام شد'
        INFLUENCER_ACCEPTED = 'influencer_accepted', 'اینفلوئنسر سفارش را قبول کرد'
        INFLUENCER_REPORT_APPROVED = 'influencer_report_approved', 'گزارش اینفلوئنسر تایید شد'
        TICKET_ANSWERED = 'ticket_answered', 'تیکت پاسخ داده شد'
        NEW_ORDER = 'new_order', 'سفارش جدید'
        PENALTY = 'penalty', 'جریمه'
        REPORT_APPROVED = 'report_approved', 'گزارش تایید شد'
        WALLET_DEPOSIT = 'wallet_deposit', 'واریز به کیف پول'
        WITHDRAWAL_SUCCESS = 'withdrawal_success', 'برداشت موفق'
        NEW_CONTENT_ORDER = 'new_content_order', 'سفارش محتوا جدید'
        REVISION_REQUESTED = 'revision_requested', 'درخواست ویرایش'
        FINAL_ACCEPTED = 'final_accepted', 'تایید نهایی سفارش'
        CONTENT_WALLET_DEPOSIT = 'content_wallet_deposit', 'واریز به حساب تیم'
        CONTENT_WITHDRAWAL_SUCCESS = 'content_withdrawal_success', 'برداشت موفق تیم'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('کاربر')
    )

    type = models.CharField(
        max_length=50,
        choices=Type.choices,
        verbose_name=_('نوع نوتیفیکیشن')
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_('عنوان')
    )

    message = models.TextField(
        verbose_name=_('متن پیام')
    )

    link = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('لینک مرتبط')
    )

    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('شناسه آبجکت مرتبط')
    )

    related_content_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('نوع مدل مرتبط')
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name=_('خوانده شده')
    )

    read_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name=_('زمان خواندن')
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name=_('زمان ایجاد')
    )

    class Meta:
        verbose_name = _('نوتیفیکیشن')
        verbose_name_plural = _('نوتیفیکیشن‌ها')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"{self.user} - {self.title[:50]}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    @property
    def time_ago(self):
        now = timezone.now()
        diff = now - self.created_at

        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600} ساعت پیش"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60} دقیقه پیش"
        else:
            return "چند لحظه پیش"
