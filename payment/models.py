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


# payment/models.py

class Invoice(models.Model):
    class Type(models.TextChoices):
        CAMPAIGN = 'campaign', 'فاکتور کمپین'
        WALLET = 'wallet', 'فاکتور شارژ کیف پول'

    # ========== فیلدهای جدید ==========
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
        blank=True  # برای کمپین‌ها از campaign.advertiser.user استفاده میشه
    )

    # ========== فیلدهای موجود (با تغییرات جزئی) ==========
    campaign = models.OneToOneField(
        'campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name="invoice",
        verbose_name="کمپین",
        null=True,
        blank=True  # برای کیف پول خالی باشه
    )

    invoice_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name="شماره فاکتور"
    )

    # ========== هزینه‌های پایه (قبل از تخفیف) ==========
    base_influencer_cost = models.PositiveBigIntegerField(
        default=0,
        verbose_name="هزینه پایه ناشران"
    )
    base_content_cost = models.PositiveBigIntegerField(
        default=0,
        verbose_name="هزینه پایه تولید محتوا"
    )
    base_commission = models.PositiveBigIntegerField(
        default=0,
        verbose_name="کمیسیون پایه پلتفرم"
    )

    # ========== مبالغ تخفیف اعمال شده (به تفکیک) ==========
    influencer_discount_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name="تخفیف ناشران"
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
    influencer_cost = models.PositiveBigIntegerField(
        default=0,
        verbose_name="هزینه نهایی اینفلوئنسر"
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

    # ========== فیلدهای مالیات بر ارزش افزوده ==========
    influencer_vat = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مالیات هزینه ناشران"
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

    # ========== فیلدهای جدید برای کیف پول ==========
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
        prefix = 'INV'
        if invoice_type == cls.Type.WALLET:
            prefix = 'WAL'
        elif invoice_type == cls.Type.CAMPAIGN:
            prefix = 'CMP'
        return f"{prefix}-{year}{month}{day}-{invoice_id}"

    def payable_amount_display(self):
        return f"{self.payable_amount:,} تومان"

    @property
    def is_campaign_invoice(self):
        return self.type == self.Type.CAMPAIGN

    @property
    def is_wallet_invoice(self):
        return self.type == self.Type.WALLET

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
        return self.type in [self.Type.DEPOSIT, self.Type.GATEWAY_PAYMENT, self.Type.CAMPAIGN_REFUND,
                             self.Type.INFLUENCER_PAYMENT, self.Type.TEAM_PAYMENT]

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
