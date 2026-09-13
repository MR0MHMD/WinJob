from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from django.utils import timezone
from django.urls import reverse
from django.db import models

class Wallet(models.Model):
    user = models.OneToOneField(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name="wallet",
        verbose_name="کاربر"
    )

    balance = models.PositiveBigIntegerField(
        default=0,
        verbose_name="موجودی"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی"
    )

    class Meta:
        verbose_name = "کیف پول"
        verbose_name_plural = "کیف پول‌ها"


class Invoice(models.Model):
    class Type(models.TextChoices):
        CAMPAIGN = 'campaign', 'فاکتور کمپین'
        WALLET = 'wallet', 'فاکتور شارژ کیف پول'
        CONTENT_ORDER = 'content_order', 'فاکتور سفارش محتوا'  # ✅ جدید

    # ========== فیلدهای اصلی ==========
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.CAMPAIGN,
        verbose_name="نوع فاکتور"
    )

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name="کاربر",
        null=True,
        blank=True
    )

    # ========== ارتباط با کمپین (اختیاری) ==========
    campaign = models.OneToOneField(
        'campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name="invoice",
        verbose_name="کمپین",
        null=True,
        blank=True
    )

    # ========== ✅ ارتباط با سفارش محتوا (اختیاری) ==========
    content_order = models.OneToOneField(
        'content_team.ContentOrder',
        on_delete=models.CASCADE,
        related_name="invoice",
        verbose_name="سفارش محتوا",
        null=True,
        blank=True
    )

    invoice_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name="شماره فاکتور"
    )

    # ========== هزینه‌های پایه (قبل از تخفیف) ==========
    base_influencer_cost = models.PositiveBigIntegerField(  # 🆕 اضافه کن
        default=0,
        verbose_name="هزینه پایه اینفلوئنسرها"
    )

    base_content_cost = models.PositiveBigIntegerField(
        default=0,
        verbose_name="هزینه پایه تولید محتوا"
    )

    base_commission = models.PositiveBigIntegerField(
        default=0,
        verbose_name="کمیسیون پایه پلتفرم"
    )

    # ========== مبالغ تخفیف ==========
    influencer_discount_amount = models.PositiveBigIntegerField(  # 🆕 اضافه کن
        default=0,
        verbose_name="تخفیف اینفلوئنسرها"
    )

    content_discount_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="تخفیف تولید محتوا"
    )
    platform_discount_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="تخفیف پلتفرم"
    )

    # ========== هزینه‌های نهایی (بعد از تخفیف) ==========
    influencer_cost = models.PositiveBigIntegerField(  # 🆕 اضافه کن
        default=0,
        verbose_name="هزینه نهایی اینفلوئنسرها"
    )

    content_cost = models.PositiveBigIntegerField(
        default=0,
        verbose_name="هزینه نهایی تولید محتوا"
    )
    commission = models.PositiveBigIntegerField(
        default=0,
        verbose_name="کمیسیون نهایی پلتفرم"
    )

    discount_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="جمع کل تخفیف"
    )

    total_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مبلغ کل"
    )

    payable_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مبلغ قابل پرداخت"
    )

    # ========== مالیات بر ارزش افزوده ==========
    influencer_vat = models.PositiveBigIntegerField(  # 🆕 اضافه کن
        default=0,
        verbose_name="مالیات هزینه اینفلوئنسرها"
    )

    content_vat = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مالیات هزینه تولید محتوا"
    )
    commission_vat = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مالیات کمیسیون پلتفرم"
    )
    total_vat = models.PositiveBigIntegerField(
        default=0,
        verbose_name="جمع کل مالیات بر ارزش افزوده"
    )

    # ========== وضعیت ==========
    is_paid = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="پرداخت شده"
    )
    paid_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ پرداخت"
    )

    commission_paid_at = jmodels.jDateTimeField(
        _('زمان واریز کمیسیون'),
        null=True,
        blank=True,
        help_text=_('زمانی که کمیسیون بین نقش‌های سازمانی تقسیم شد'),
    )

    # ========== فیلدهای اضافی برای کیف پول ==========
    wallet_deposit_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مبلغ شارژ کیف پول"
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی"
    )

    class Meta:
        verbose_name = "فاکتور"
        verbose_name_plural = "فاکتورها"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['type', 'is_paid']),
            models.Index(fields=['invoice_number']),
        ]

    def __str__(self):
        return f"{self.invoice_number}"

    def get_absolute_url(self):
        return reverse('payment:invoice_detail', kwargs={'invoice_id': self.id})

    @classmethod
    def generate_invoice_number(cls, invoice_id, created_at, invoice_type):
        year = created_at.year
        month = str(created_at.month).zfill(2)
        day = str(created_at.day).zfill(2)
        prefix_map = {
            cls.Type.CAMPAIGN: 'CMP',
            cls.Type.WALLET: 'WAL',
            cls.Type.CONTENT_ORDER: 'CTO',
        }
        prefix = prefix_map.get(invoice_type, 'INV')
        return f"{prefix}-{year}{month}{day}-{invoice_id}"

    @property
    def is_campaign_invoice(self):
        return self.type == self.Type.CAMPAIGN

    @property
    def is_wallet_invoice(self):
        return self.type == self.Type.WALLET

    @property
    def is_content_order_invoice(self):
        return self.type == self.Type.CONTENT_ORDER

    @property
    def is_commission_paid(self):
        """آیا کمیسیون این فاکتور قبلاً واریز شده؟"""
        return self.commission_paid_at is not None


class CommissionSplit(models.Model):
    """
    تسهیم کمیسیون هر فاکتور

    - یک رکورد به ازای هر فاکتور
    - وقتی payout_commission اجرا می‌شه، این رکورد پر می‌شه
    - محل ذخیره سهم هر نقش + هزینه نگهداری سایت
    - مبلغ کل کمیسیون از `invoice.commission` خونده می‌شه (نیازی به فیلد جدا نیست)
    """

    invoice = models.OneToOneField(
        'Invoice',
        on_delete=models.CASCADE,
        related_name='commission_split',
        verbose_name='فاکتور',
    )

    # ========== سهم نقش‌ها ==========
    ceo_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='سهم مدیرعامل',
    )
    developer_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='سهم توسعه‌دهنده',
    )
    publish_manager_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='سهم مدیر نشر',
    )
    content_manager_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='سهم مدیر محتوا',
    )
    regional_manager_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='سهم مدیر استانی',
    )
    site_maintenance_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='هزینه نگهداری سایت',
    )

    # ========== متادیتا ==========
    snapshot = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='اسنپ‌شات تنظیمات',
        help_text='درصدهای تنظیمات در لحظه واریز',
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
    )

    class Meta:
        verbose_name = 'تسهیم کمیسیون'
        verbose_name_plural = 'تسهیم‌های کمیسیون'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"تسهیم فاکتور {self.invoice.invoice_number}"

    @property
    def total_commission(self):
        """مبلغ کل کمیسیون — از خود فاکتور میاد"""
        return self.invoice.commission

    @property
    def sum_of_shares(self):
        """جمع همه سهم‌ها — باید برابر total_commission باشه"""
        return (
            self.ceo_amount +
            self.developer_amount +
            self.publish_manager_amount +
            self.content_manager_amount +
            self.regional_manager_amount +
            self.site_maintenance_amount
        )

    @property
    def is_balanced(self):
        return self.sum_of_shares == self.total_commission


class Coupon(models.Model):
    class Scope(models.TextChoices):
        INFLUENCER = "influencer", "اینفلوئنسر"
        CONTENT_TEAM = "content_team", "تیم محتوا"
        PLATFORM = "platform", "پلتفرم"

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "درصدی"
        FIXED = "fixed", "مبلغ ثابت"

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="کد"
    )

    scope = models.CharField(
        max_length=20,
        choices=Scope.choices,
        verbose_name="نوع تخفیف"
    )

    channel = models.ForeignKey(
        'influencers.Channel',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="coupons",
        verbose_name="اینفلوئنسر"
    )

    team = models.ForeignKey(
        "content_team.ContentTeam",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="coupons",
        verbose_name="تیم محتوا"
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        verbose_name="نوع مقدار تخفیف"
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="مقدار"
    )

    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="حداکثر استفاده"
    )

    used_count = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد استفاده"
    )

    expires_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ انقضا"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال"
    )

    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"

    def calculate_discount(self, amount):
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return int(amount * (float(self.value) / 100))

        return int(self.value)

    def is_valid(self):

        if not self.is_active:
            return False

        if self.expires_at and self.expires_at < timezone.now():
            return False

        if self.max_uses and self.used_count >= self.max_uses:
            return False

        return True


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"

    class Method(models.TextChoices):
        GATEWAY = "gateway", "درگاه پرداخت"
        WALLET = "wallet", "کیف پول"

    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="کاربر"
    )

    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="فاکتور"
    )

    amount = models.DecimalField(
        _('مبلغ'),
        max_digits=12,
        decimal_places=0
    )

    payment_method = models.CharField(
        max_length=20,
        choices=Method.choices,
        verbose_name="روش پرداخت"
    )

    authority = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="authority"
    )

    ref_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ref id"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="وضعیت"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )

    class Meta:
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"


class Transaction(models.Model):
    class Type(models.TextChoices):
        # کیف پول
        DEPOSIT = "deposit", "شارژ کیف پول"
        WITHDRAW = "withdraw", "برداشت از کیف پول"

        # کمپین
        CAMPAIGN_PAYMENT = "campaign_payment", "پرداخت کمپین"
        CAMPAIGN_REFUND = "campaign_refund", "بازگشت وجه کمپین"

        GATEWAY_PAYMENT = "gateway_payment", "پرداخت مستقیم از درگاه"
        GATEWAY_REFUND = "gateway_refund", "بازگشت وجه از درگاه"

        INFLUENCER_PAYMENT = "influencer_payment", "پرداخت به ناشر"

        TEAM_PAYMENT = "team_payment", "پرداخت به تیم تولید محتوا"
        CONTENT_ORDER_PAYMENT = 'content_order_payment', 'پرداخت سفارش تولید محتوا'
        CONTENT_ORDER_REFUND = 'content_order_refund', 'بازگشت وجه سفارش محتوا'

        INFLUENCER_WITHDRAWAL = 'influencer_withdrawal', _('تسویه ناشر')
        CONTENT_TEAM_WITHDRAWAL = 'content_team_withdrawal', _('تسویه تیم محتوا')

        # ===== جدید: کمیسیون =====
        COMMISSION_CEO = 'commission_ceo', _('کمیسیون مدیرعامل')
        COMMISSION_DEVELOPER = 'commission_developer', _('کمیسیون توسعه‌دهنده')
        COMMISSION_PUBLISH_MANAGER = 'commission_publish_manager', _('کمیسیون مدیر نشر')
        COMMISSION_CONTENT_MANAGER = 'commission_content_manager', _('کمیسیون مدیر محتوا')
        COMMISSION_REGIONAL_MANAGER = 'commission_regional_manager', _('کمیسیون مدیر استانی')

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"
        CANCELLED = "cancelled", "لغو شده"

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="کاربر"
    )

    amount = models.PositiveBigIntegerField(
        verbose_name="مبلغ"
    )

    type = models.CharField(
        max_length=30,
        choices=Type.choices,
        verbose_name="نوع تراکنش"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUCCESS,
        verbose_name="وضعیت"
    )

    # ارتباط با مدل‌های مختلف
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="کمپین مرتبط"
    )

    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="فاکتور مرتبط"
    )

    payment = models.ForeignKey(
        'Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="پرداخت مرتبط"
    )

    team_member = models.ForeignKey(
        'content_team.ContentTeamMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="عضو تیم محتوا"
    )

    reference_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="شماره مرجع"
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )

    class Meta:
        verbose_name = "تراکنش"
        verbose_name_plural = "تراکنش‌ها"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['type', 'status']),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_type_display()} - {self.amount:,} تومان"

    @property
    def is_income(self):
        """آیا این تراکنش ورودی است؟"""
        if not self.type:
            return False
        return self.type in [
            self.Type.DEPOSIT,
            self.Type.GATEWAY_PAYMENT,
            self.Type.CAMPAIGN_REFUND,
            self.Type.INFLUENCER_PAYMENT,
            self.Type.TEAM_PAYMENT,
            self.Type.COMMISSION_CEO,
            self.Type.COMMISSION_DEVELOPER,
            self.Type.COMMISSION_PUBLISH_MANAGER,
            self.Type.COMMISSION_CONTENT_MANAGER,
            self.Type.COMMISSION_REGIONAL_MANAGER,
        ]

    @property
    def is_expense(self):
        """آیا این تراکنش خروجی است؟"""
        if not self.type:
            return True
        return self.type in [self.Type.WITHDRAW, self.Type.CAMPAIGN_PAYMENT, self.Type.GATEWAY_PAYMENT]

    @property
    def sign_display(self):
        """نمایش علامت (+/-) برای تراکنش"""
        if self.amount is None:
            return "- تومان"

        if self.is_income:
            return f"+ {self.amount:,} تومان"
        else:
            return f"- {self.amount:,} تومان"


class BankAccount(models.Model):
    """حساب بانکی کاربر برای تسویه حساب"""

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name=_('کاربر')
    )

    sheba_code = models.CharField(
        _('شماره شبا'),
        max_length=24,
        help_text=_('شماره شبا بدون IR')
    )

    bank = models.ForeignKey(
        'core.Bank',
        on_delete=models.PROTECT,
        related_name='accounts',
        verbose_name=_('بانک'),
        null=True,
        blank=True
    )

    account_holder_name = models.CharField(
        _('نام صاحب حساب'),
        max_length=100
    )

    is_default = models.BooleanField(
        _('حساب پیش‌فرض'),
        default=False
    )

    is_verified = models.BooleanField(
        _('تأیید شده'),
        default=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('حساب بانکی')
        verbose_name_plural = _('حساب‌های بانکی')
        unique_together = [['user', 'sheba_code']]
        ordering = ['-created_at']

    def sheba_display(self):
        if not self.sheba_code:
            return "-"
        raw = self.sheba_code.replace(" ", "").strip()
        if len(raw) >= 2:
            first_two = raw[:2]
            rest = raw[2:]
            formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))
            return f"IR {first_two} {formatted_rest}"
        return self.sheba_code

    @property
    def bank_name(self):
        return self.bank.name if self.bank else "بانک نامشخص"

    def __str__(self):
        return f"{self.user} - {self.sheba_code}"

    def save(self, *args, **kwargs):
        if self.sheba_code and self.sheba_code.upper().startswith('IR'):
            self.sheba_code = self.sheba_code[2:]
        super().save(*args, **kwargs)


class WithdrawalRequest(models.Model):
    """درخواست تسویه حساب"""

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار بررسی')
        PROCESSING = 'processing', _('در حال پردازش')
        COMPLETED = 'completed', _('انجام شده')
        REJECTED = 'rejected', _('رد شده')
        CANCELLED = 'cancelled', _('لغو شده')

    class Type(models.TextChoices):
        INFLUENCER = 'influencer', _('تسویه ناشر')
        CONTENT_TEAM = 'content_team', _('تسویه تیم محتوا')

    # ارتباط با کاربر و حساب بانکی
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='withdrawal_requests',
        verbose_name=_('کاربر')
    )

    bank_account = models.ForeignKey(
        'BankAccount',
        on_delete=models.PROTECT,
        related_name='withdrawal_requests',
        verbose_name=_('حساب بانکی مقصد')
    )

    withdrawal_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        verbose_name=_('نوع تسویه')
    )

    # مبلغ
    amount = models.PositiveBigIntegerField(
        _('مبلغ درخواستی (تومان)')
    )

    # وضعیت
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_('وضعیت')
    )

    # پیگیری
    tracking_code = models.CharField(
        _('کد پیگیری'),
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    # اطلاعات تکمیلی
    description = models.TextField(
        _('توضیحات'),
        blank=True
    )

    admin_note = models.TextField(
        _('یادداشت ادمین'),
        blank=True
    )

    # تاریخ‌ها
    requested_at = jmodels.jDateTimeField(
        _('تاریخ درخواست'),
        auto_now_add=True
    )

    processed_at = jmodels.jDateTimeField(
        _('تاریخ پردازش'),
        null=True,
        blank=True
    )

    completed_at = jmodels.jDateTimeField(
        _('تاریخ تسویه'),
        null=True,
        blank=True
    )

    # ارتباط با تراکنش
    transaction = models.ForeignKey(
        'payment.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawal_requests',
        verbose_name=_('تراکنش مرتبط')
    )

    class Meta:
        verbose_name = _('درخواست تسویه')
        verbose_name_plural = _('درخواست‌های تسویه')
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', '-requested_at']),
            models.Index(fields=['tracking_code']),
        ]

    def __str__(self):
        return f"تسویه {self.user} - {self.amount:,} تومان - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            import random
            import string
            code = ''.join(random.choices(string.digits, k=8))
            self.tracking_code = f"WDL-{code}"
        super().save(*args, **kwargs)

    @property
    def formatted_amount(self):
        return f"{self.amount:,} تومان"

    def complete(self, transaction):
        """تکمیل تسویه"""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.transaction = transaction
        self.save()
