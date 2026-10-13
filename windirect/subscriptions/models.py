"""پلن‌ها، دوره‌های دسترسی و سوابق خرید و معرفی وین دایرکت."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class SubscriptionPlan(models.Model):
    """تعریف امکانات پلن؛ دورهٔ رایگان نیز یک پلن واقعی است."""

    name = models.CharField(_("نام پلن"), max_length=100)
    code = models.SlugField(_("کد پلن"), unique=True)
    description = models.TextField(_("توضیحات"), blank=True)
    level = models.PositiveSmallIntegerField(
        _("سطح پلن"),
        default=1,
        help_text=_("پایه ۱، حرفه‌ای ۲؛ کاهش سطح خریداری‌شده مجاز نیست."),
    )
    is_trial = models.BooleanField(_("دورهٔ رایگان یک‌بار مصرف"), default=False)
    smart_comments = models.BooleanField(_("کامنت هوشمند"), default=True)
    smart_direct = models.BooleanField(_("دایرکت هوشمند"), default=True)
    showcases = models.BooleanField(_("ویترین‌ساز"), default=False)
    forms = models.BooleanField(_("فرم‌ساز"), default=False)
    max_pages = models.PositiveSmallIntegerField(
        _("حداکثر پیج"), default=1, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField(_("قابل عرضه"), default=True)
    is_featured = models.BooleanField(_("پلن پیشنهادی"), default=False)
    position = models.PositiveSmallIntegerField(_("ترتیب نمایش"), default=1)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        db_table = "windirect_subscriptionplan"
        verbose_name = _("پلن وین دایرکت")
        verbose_name_plural = _("پلن‌های وین دایرکت")
        ordering = ["position", "pk"]

    def __str__(self):
        return self.name

    def capabilities(self):
        """نسخهٔ ثابت امکانات را برای سفارش و دورهٔ دسترسی برمی‌گرداند."""
        return {
            key: getattr(self, key)
            for key in (
                "smart_comments",
                "smart_direct",
                "showcases",
                "forms",
                "max_pages",
                "level",
            )
        }


class SubscriptionOffer(models.Model):
    """قیمت مستقل دوره‌های یک‌ماهه، سه‌ماهه و سالانهٔ هر پلن."""

    class Duration(models.IntegerChoices):
        MONTH = 30, _("یک‌ماهه؛ ۳۰ روز")
        QUARTER = 90, _("سه‌ماهه؛ ۹۰ روز")
        YEAR = 365, _("یک‌ساله؛ ۳۶۵ روز")

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="offers",
        verbose_name=_("پلن"),
    )
    duration_days = models.PositiveSmallIntegerField(
        _("مدت"), choices=Duration.choices, default=30
    )
    price = models.PositiveBigIntegerField(_("قیمت پیش از مالیات؛ تومان"), default=0)
    is_active = models.BooleanField(_("قابل فروش"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        db_table = "windirect_subscriptionoffer"
        verbose_name = _("دوره و قیمت پلن")
        verbose_name_plural = _("دوره‌ها و قیمت‌های پلن")
        ordering = ["duration_days", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "duration_days"], name="wd_plan_duration_unique"
            )
        ]

    def clean(self):
        """فروش رایگان فقط برای پلن آزمایشی مجاز است."""
        super().clean()
        if self.plan_id:
            if self.plan.is_trial and (self.price != 0 or self.duration_days != 30):
                raise ValidationError("دورهٔ آزمایشی باید ۳۰ روزه و با قیمت صفر باشد.")
            if not self.plan.is_trial and self.is_active and self.price <= 0:
                raise ValidationError({"price": "قیمت پلن پولی باید مثبت باشد."})

    def __str__(self):
        return f"{self.plan} — {self.get_duration_days_display()}"


class SubscriptionAccount(models.Model):
    """قفل و وضعیت مشترک خریدها، استفادهٔ رایگان و اعتبار هدیهٔ یک کاربر."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="windirect_subscription",
        verbose_name=_("کاربر"),
    )
    trial_used_at = jmodels.jDateTimeField(
        _("زمان فعال‌سازی رایگان"), null=True, blank=True
    )
    first_paid_at = jmodels.jDateTimeField(_("اولین خرید موفق"), null=True, blank=True)
    highest_level = models.PositiveSmallIntegerField(
        _("بالاترین سطح خریداری‌شده"), default=0
    )
    banked_gift_days = models.PositiveIntegerField(_("روز هدیهٔ ذخیره‌شده"), default=0)
    revision = models.PositiveIntegerField(_("نسخهٔ وضعیت خرید"), default=0)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        db_table = "windirect_subscriptionaccount"
        verbose_name = _("حساب اشتراک وین دایرکت")
        verbose_name_plural = _("حساب‌های اشتراک وین دایرکت")
        ordering = ["-pk"]

    def __str__(self):
        return str(self.user)


class ReferralCode(models.Model):
    """کد متعلق به یک معرف؛ مزایای آن فقط در اولین خرید خریدار اعمال می‌شود."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="windirect_referral_code",
        verbose_name=_("صاحب کد"),
    )
    code = models.CharField(
        _("کد معرف"),
        max_length=40,
        unique=True,
        validators=[
            RegexValidator(
                r"^[A-Z0-9_-]+$", "حروف بزرگ انگلیسی، عدد، خط تیره یا زیرخط وارد کنید."
            )
        ],
    )
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        db_table = "windirect_referralcode"
        verbose_name = _("کد معرف وین دایرکت")
        verbose_name_plural = _("کدهای معرف وین دایرکت")
        ordering = ["-pk"]

    def __str__(self):
        return self.code


class SubscriptionOrder(models.Model):
    """قیمت قطعی و عملیات درخواستی؛ مستقل از ویرایش بعدی پلن."""

    class Kind(models.TextChoices):
        PURCHASE = "purchase", _("خرید یا تمدید")
        UPGRADE = "upgrade", _("ارتقا")

    class Status(models.TextChoices):
        PENDING = "pending", _("در انتظار پرداخت")
        PAID = "paid", _("پرداخت و فعال‌سازی موفق")
        CANCELLED = "cancelled", _("لغوشده")
        CREDITED = "credited", _("وجه تأییدشده به کیف پول برگشت")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="windirect_orders",
        verbose_name=_("خریدار"),
    )
    offer = models.ForeignKey(
        SubscriptionOffer, on_delete=models.PROTECT, verbose_name=_("دورهٔ انتخاب‌شده")
    )
    kind = models.CharField(
        _("نوع سفارش"), max_length=15, choices=Kind.choices, default=Kind.PURCHASE
    )
    status = models.CharField(
        _("وضعیت"), max_length=15, choices=Status.choices, default=Status.PENDING
    )
    quote = models.JSONField(_("نسخهٔ قیمت و شرایط خرید"), default=dict)
    account_revision = models.PositiveIntegerField(
        _("نسخهٔ حساب هنگام سفارش"), default=0
    )
    referral = models.ForeignKey(
        ReferralCode,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("کد معرفی"),
    )
    created_at = jmodels.jDateTimeField(_("تاریخ ثبت"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ آخرین ویرایش"), auto_now=True)
    settled_at = jmodels.jDateTimeField(_("تاریخ تعیین تکلیف"), null=True, blank=True)

    class Meta:
        db_table = "windirect_subscriptionorder"
        verbose_name = _("سفارش اشتراک وین دایرکت")
        verbose_name_plural = _("سفارش‌های اشتراک وین دایرکت")
        ordering = ["-pk"]
        indexes = [
            models.Index(fields=["user", "status"], name="wd_order_owner_status")
        ]

    def __str__(self):
        return f"اشتراک #{self.pk} — {self.user}"


class UserSubscription(models.Model):
    """یک بازهٔ دسترسی رایگان، پولی یا هدیه با نسخهٔ ثابت امکانات."""

    class Kind(models.TextChoices):
        TRIAL = "trial", _("رایگان")
        PAID = "paid", _("خریداری‌شده")
        GIFT = "gift", _("هدیه")

    account = models.ForeignKey(
        SubscriptionAccount,
        on_delete=models.PROTECT,
        related_name="periods",
        verbose_name=_("حساب اشتراک"),
    )
    offer = models.ForeignKey(
        SubscriptionOffer, on_delete=models.PROTECT, verbose_name=_("دورهٔ مبنا")
    )
    order = models.ForeignKey(
        SubscriptionOrder,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="periods",
        verbose_name=_("سفارش ایجادکننده"),
    )
    kind = models.CharField(_("نوع دسترسی"), max_length=10, choices=Kind.choices)
    starts_at = jmodels.jDateTimeField(_("شروع دسترسی"))
    ends_at = jmodels.jDateTimeField(_("پایان دسترسی"))
    capabilities = models.JSONField(_("امکانات خریداری‌شده"), default=dict)
    plan_name = models.CharField(_("نام پلن هنگام خرید"), max_length=100)
    duration_days = models.PositiveSmallIntegerField(_("مدت دورهٔ فروش مبنا"))
    is_superseded = models.BooleanField(_("بازهٔ جایگزین‌شده در ارتقا"), default=False)
    credit_daily = models.DecimalField(
        _("اعتبار روزانهٔ بدون مالیات؛ تومان"),
        max_digits=22,
        decimal_places=8,
        default=0,
    )
    created_at = jmodels.jDateTimeField(_("تاریخ ثبت"), auto_now_add=True)

    class Meta:
        db_table = "windirect_usersubscription"
        verbose_name = _("بازهٔ اشتراک کاربر")
        verbose_name_plural = _("بازه‌های اشتراک کاربران")
        ordering = ["starts_at", "pk"]
        indexes = [
            models.Index(fields=["account", "ends_at"], name="wd_period_account_end")
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="wd_period_positive",
            )
        ]

    def __str__(self):
        return f"{self.account} — {self.plan_name}"


class ReferralRedemption(models.Model):
    """ثبت یک‌بارهٔ تخفیف و پاداش برای اولین خرید موفق هر کاربر."""

    buyer = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name=_("خریدار")
    )
    referral = models.ForeignKey(
        ReferralCode,
        on_delete=models.PROTECT,
        related_name="redemptions",
        verbose_name=_("کد معرف"),
    )
    order = models.OneToOneField(
        SubscriptionOrder, on_delete=models.PROTECT, verbose_name=_("سفارش موفق")
    )
    buyer_days = models.PositiveSmallIntegerField(_("روز هدیهٔ خریدار"), default=5)
    owner_days = models.PositiveSmallIntegerField(_("روز هدیهٔ معرف"), default=1)
    created_at = jmodels.jDateTimeField(_("تاریخ ثبت"), auto_now_add=True)

    class Meta:
        db_table = "windirect_referralredemption"
        verbose_name = _("استفادهٔ موفق از کد معرف")
        verbose_name_plural = _("استفاده‌های موفق از کد معرف")
        ordering = ["-pk"]

    def __str__(self):
        return f"{self.buyer} — {self.referral}"


class SubscriptionGift(models.Model):
    """دفتر روزهای هدیه؛ ثبت می‌کند هدیه ذخیره یا به کدام دوره افزوده شده است."""

    account = models.ForeignKey(
        SubscriptionAccount,
        on_delete=models.PROTECT,
        related_name="gifts",
        verbose_name=_("حساب"),
    )
    redemption = models.ForeignKey(
        ReferralRedemption, on_delete=models.PROTECT, verbose_name=_("معرفی موفق")
    )
    days = models.PositiveSmallIntegerField(_("تعداد روز"))
    period = models.ForeignKey(
        UserSubscription,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("بازهٔ تخصیص‌یافته"),
    )
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        db_table = "windirect_subscriptiongift"
        verbose_name = _("هدیهٔ اشتراک")
        verbose_name_plural = _("هدیه‌های اشتراک")
        ordering = ["-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "redemption"], name="wd_unique_referral_gift"
            )
        ]

    def __str__(self):
        return f"{self.account} — {self.days} روز"


class WindirectCoupon(models.Model):
    """کد تخفیف اختصاصی وین دایرکت (فقط برای اشتراک)."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", _("درصدی")
        FIXED = "fixed", _("مبلغ ثابت")

    code = models.CharField(_("کد تخفیف"), max_length=50, unique=True)
    discount_type = models.CharField(
        _("نوع تخفیف"),
        max_length=20,
        choices=DiscountType.choices,
    )
    value = models.DecimalField(
        _("مقدار"),
        max_digits=10,
        decimal_places=2,
    )
    max_uses = models.PositiveIntegerField(
        _("حداکثر استفاده"),
        null=True,
        blank=True,
    )
    used_count = models.PositiveIntegerField(_("تعداد استفاده"), default=0)
    expires_at = jmodels.jDateTimeField(
        _("تاریخ انقضا"),
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        db_table = "windirect_windirectcoupon"
        verbose_name = _("کد تخفیف وین دایرکت")
        verbose_name_plural = _("کدهای تخفیف وین دایرکت")
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def is_valid(self, now=None):
        """اعتبار کد رو چک می‌کنه."""
        now = now or timezone.now()
        if not self.is_active:
            return False
        if self.expires_at and as_datetime(self.expires_at) <= now:
            return False
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        return True

    def calculate_discount(self, base_amount):
        """مبلغ تخفیف رو از base محاسبه می‌کنه (بدون مالیات)."""
        base_amount = int(base_amount)
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = int(base_amount * float(self.value) / 100)
        else:
            discount = int(self.value)
        return min(discount, base_amount)  # تخفیف نباید از base بیشتر بشه
