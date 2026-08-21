from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from django.utils import timezone
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        CAMPAIGN_PENDING = 'campaign_pending', 'کمپین در انتظار تایید'
        CAMPAIGN_APPROVED = 'campaign_approved', 'کمپین تایید شد'
        CAMPAIGN_REJECTED = 'campaign_rejected', 'کمپین رد شد'
        CAMPAIGN_RUNNING = 'campaign_running', 'کمپین در حال اجراست'
        CAMPAIGN_COMPLETED = 'campaign_completed', 'کمپین تمام شد'
        CONTENT_ACCEPTED = 'content_accepted', 'سفارش محتوا قبول شد'
        CONTENT_REJECTED = 'content_rejected', 'سفارش محتوا رد شد'
        CONTENT_DELIVERED = 'content_delivered', 'فایل محتوا تحویل شد'
        REVISION_ACCEPTED = 'revision_accepted', 'ویرایش قبول شد'
        REVISION_REJECTED = 'revision_rejected', 'ویرایش رد شد'
        FINAL_ACCEPT = 'final_accept', 'تسویه با اعضای تیم'
        INFLUENCER_ACCEPTED = 'influencer_accepted', 'اینفلوئنسر سفارش را قبول کرد'
        INFLUENCER_REPORT_APPROVED = 'influencer_report_approved', 'گزارش اینفلوئنسر تایید شد'
        INFLUENCER_REPORT_REJECTED = 'influencer_report_rejected', 'گزارش اینفلوئنسر رد شد'
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
        INFLUENCER_REJECTED = 'influencer_rejected', 'رد سفارش توسط اینفلوئنسر'
        CAMPAIGN_NEEDS_REVISION = 'campaign_needs_revision', 'کمپین نیاز به اصلاح دارد'
        CAMPAIGN_AUTO_APPROVED = 'campaign_auto_approved', 'ادامه خودکار کمپین'

    user = models.ForeignKey(
        'accounts.CustomUser',
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
        verbose_name = _('اعلان')
        verbose_name_plural = _('اعلان ها')
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

    def get_icon_data(self):
        # (آیکون، کلاس رنگی پس‌زمینه)
        mapping = {
            # موفقیت‌ها (سبز)
            'campaign_approved': ('bi-check-circle-fill', 'bg-success'),
            'content_accepted': ('bi-people-fill', 'bg-success'),
            'revision_accepted': ('bi-pencil-square', 'bg-success'),
            'influencer_accepted': ('bi-person-check-fill', 'bg-success'),
            'influencer_report_approved': ('bi bi-file-text', 'bg-success'),
            'report_approved': ('bi-cart-plus-fill', 'bg-success'),
            'final_accepted': ('bi bi-thumbs-up', 'bg-success'),
            'withdrawal_success': ('bi bi-credit-card', 'bg-success'),
            'content_withdrawal_success': ('bi bi-credit-card', 'bg-success'),

            'campaign_pending': ('bi-check-circle-fill', 'bg-warning'),
            'new_order': ('bi-cart-plus-fill', 'bg-warning'),
            'new_content_order': ('bi bi-file-plus', 'bg-warning'),
            'revision_requested': ('bi bi-edit', 'bg-warning'),
            'ticket_answered': ('bi-envelope-open-fill', 'bg-warning'),

            # شکست / جریمه (قرمز)
            'campaign_rejected': ('bi-x-circle-fill', 'bg-danger'),
            'content_rejected': ('bi-people-fill', 'bg-danger'),
            'revision_rejected': ('bi-pencil-square', 'bg-danger'),
            'influencer_report_rejected': ('bi-cash-stack', 'bg-danger'),

            # اطلاعات / کیف پول (آبی)
            'campaign_completed': ('bi-check-all', 'bg-info'),
            'final_accept': ('bi-cart-plus-fill', 'bg-info'),
            'campaign_running': ('bi-check-circle-fill', 'bg-info'),
            'content_delivered': ('bi-file-check-fill', 'bg-info'),
            'wallet_deposit': ('bi bi-wallet', 'bg-info'),
            'content_wallet_deposit': ('bi bi-wallet', 'bg-info'),
        }

        icon_class, bg_class = mapping.get(self.type, ('fi-bell', 'bg-secondary'))
        return icon_class, bg_class


    @property
    def time_ago(self):
        # گرفتن زمان حال به صورت Aware (منطبق با تنظیمات TIME_ZONE در settings.py)
        now = timezone.now()

        # تبدیل فیلد created_at (که jDateTimeField است) به datetime استاندارد پایتون برای مقایسه
        # چون created_at خودش Aware هست، حالا هر دو Aware میشن و تفریق بدون خطا انجام میشه
        created_at_dt = self.created_at

        diff = now - created_at_dt

        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600} ساعت پیش"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60} دقیقه پیش"
        else:
            return "چند لحظه پیش"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='notification_prefs',
        verbose_name=_('کاربر')
    )

    # ==================== تنظیمات عمومی ====================
    receive_in_bale = models.BooleanField(_('دریافت نوتیفیکیشن در بله'), default=True)
    ticket_replies = models.BooleanField(_('پاسخ تیکت‌ها'), default=True)
    marketing_messages = models.BooleanField(_('اخبار، آپدیت‌ها و کدهای تخفیف'), default=False)
    financial_alerts = models.BooleanField(_('تراکنش‌های مالی (واریز، برداشت، فاکتور)'), default=True)

    # ==================== تنظیمات تبلیغ دهنده ====================
    adv_campaign_status = models.BooleanField(
        _('وضعیت کمپین‌ها (تایید، رد، اکران، پایان)'), default=True
    )
    adv_influencer_actions = models.BooleanField(
        _('واکنش ناشران (پذیرش سفارش تبلیغ)'), default=True
    )
    adv_content_orders = models.BooleanField(
        _('وضعیت سفارش تولید محتوا (تایید، رد، تحویل فایل)'), default=True
    )

    # ==================== تنظیمات ناشر (اینفلوئنسر) ====================
    inf_new_orders = models.BooleanField(
        _('دریافت سفارش تبلیغ جدید'), default=True
    )
    inf_report_status = models.BooleanField(
        _('تایید یا رد گزارش‌های کار'), default=True
    )

    # ==================== تنظیمات تیم تولید محتوا ====================
    team_new_orders = models.BooleanField(
        _('دریافت سفارش تولید محتوای جدید'), default=True
    )
    team_revisions = models.BooleanField(
        _('درخواست ویرایش توسط تبلیغ دهنده'), default=True
    )
    team_financial = models.BooleanField(
        _('تایید نهایی فایل و واریز وجه'), default=True
    )

    class Meta:
        verbose_name = _('تنظیمات اعلان کاربر')
        verbose_name_plural = _('تنظیمات اعلان کاربران')

    def __str__(self):
        return f"تنظیمات نوتیفیکیشن - کاربر {self.user.id}"
