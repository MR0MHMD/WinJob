# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django_jalali.db import models as jmodels
from .managers import CustomUserManager
from django_resized import ResizedImageField


class CustomUser(AbstractBaseUser, PermissionsMixin):

    phone_number = models.CharField(
        _('شماره تماس'),
        max_length=11,
        unique=True
    )

    email = models.EmailField(
        _('ایمیل'),
        max_length=110,
        blank=True,
        null=True
    )

    nickname = models.CharField(
        _('نام مستعار'),
        max_length=50,
        blank=True,
        null=True
    )

    avatar = ResizedImageField(
        _('تصویر پروفایل'),
        upload_to="avatars/",
        size=[500, 500],
        scale=1,
        crop=['middle', 'center'],
        null=True,
        blank=True
    )

    sheba_code = models.CharField(_('شماره شبا'), max_length=24, null=True, blank=True)

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )

    is_staff = models.BooleanField(
        _('کارمند'),
        default=False
    )

    province = models.ForeignKey('location.Province', on_delete=models.CASCADE,
                                 related_name='accounts', verbose_name=_('استان'), null=True, blank=True)


    is_regional_manager = models.BooleanField(
        'مدیر استانی',
        default=False,
        help_text='اگر فعال باشد، کاربر فقط دسترسی به استان خودش را دارد'
    )

    date_joined = jmodels.jDateTimeField(
        _('تاریخ عضویت'),
        default=timezone.now
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('کاربر')
        verbose_name_plural = _('کاربران')
        ordering = ['-created_at']

    def __str__(self):
        return self.phone_number

    def display_sheba(self):
        if not self.sheba_code:
            return "-"

        # حذف IR از اول اگه باشه
        raw = self.sheba_code.replace("IR", "").strip()

        # ۲ رقم اول رو جدا کن
        first_two = raw[:2]
        # باقی اعداد رو از رقم ۳ به بعد
        rest = raw[2:]

        # بقیه اعداد رو هر ۴ رقم یه فاصله بنداز
        formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))

        # برگردون: IR + فاصله + ۲ رقم اول + فاصله + بقیه فرمت شده
        return f"IR - {first_two} {formatted_rest}"

    @property
    def is_advertiser(self):
        return hasattr(self, "advertiser_profile")

    @property
    def is_influencer(self):
        return hasattr(self, "influencer_profile")

    @property
    def is_team_member(self):
        return hasattr(self, "team_member")


class Wallet(models.Model):

    user = models.OneToOneField(
        CustomUser,
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
        CustomUser,
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
        'campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="کمپین مرتبط"
    )

    invoice = models.ForeignKey(
        'campaigns.CampaignInvoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="فاکتور مرتبط"
    )

    payment = models.ForeignKey(
        'campaigns.Payment',
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
        return self.type in [self.Type.DEPOSIT, self.Type.GATEWAY_PAYMENT, self.Type.CAMPAIGN_REFUND, self.Type.INFLUENCER_PAYMENT, self.Type.TEAM_PAYMENT]

    @property
    def is_expense(self):
        """آیا این تراکنش خروجی است؟"""
        if not self.type:
            return True
        return self.type in [self.Type.WITHDRAW, self.Type.CAMPAIGN_PAYMENT, self.Type.GATEWAY_PAYMENT ]

    @property
    def sign_display(self):
        """نمایش علامت (+/-) برای تراکنش"""
        if self.amount is None:
            return "- تومان"

        if self.is_income:
            return f"+ {self.amount:,} تومان"
        else:
            return f"- {self.amount:,} تومان"
