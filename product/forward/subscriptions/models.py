"""مدل‌های اپ اشتراک وین فوروارد — پلن‌ها، حساب اشتراک، دسترسی پلتفرم‌ها و سفارش‌ها."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


FORWARD_PLATFORMS = (
    ("bale", "بله"),
    ("eitaa", "ایتا"),
    ("rubika", "روبیکا"),
)

FORWARD_PLATFORM_SLUGS = tuple(slug for slug, _ in FORWARD_PLATFORMS)
FORWARD_PLATFORM_LABELS = dict(FORWARD_PLATFORMS)


class ForwardSubscriptionPlan(models.Model):
    """تعریف پلن‌های اشتراک وین فوروارد (رایگان ۷ روزه، ۳۰ روزه، ۹۰ روزه و یک‌ساله)."""

    code = models.SlugField(_("کد پلن"), max_length=40, unique=True)
    name = models.CharField(_("نام پلن"), max_length=100)
    description = models.TextField(_("توضیحات"), blank=True)
    duration_days = models.PositiveSmallIntegerField(_("مدت اعتبار (روز)"), default=30)
    price_per_platform = models.PositiveBigIntegerField(
        _("قیمت هر پلتفرم (تومان)"),
        default=0,
        help_text=_("برای پلن رایگان ۷ روزه مقدار ۰ و برای پلن‌های پولی قیمت هر پلتفرم به تومان ثبت شود."),
    )
    is_trial = models.BooleanField(_("دوره رایگان یک‌بارمصرف"), default=False)
    is_active = models.BooleanField(_("فعال برای فروش"), default=True)
    is_featured = models.BooleanField(_("پیشنهادی"), default=False)
    position = models.PositiveSmallIntegerField(_("ترتیب نمایش"), default=1)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        verbose_name = _("پلن اشتراک وین فوروارد")
        verbose_name_plural = _("پلن‌های اشتراک وین فوروارد")
        ordering = ["position", "duration_days", "pk"]

    def __str__(self) -> str:
        """نمایش خوانای نام و مدت پلن در ادمین و قالب‌ها."""
        return f"{self.name} ({self.duration_days} روز)"

    def clean(self) -> None:
        """اعتبارسنجی هم‌خوانی قیمت پلن با وضعیت رایگان یا پولی بودن آن."""
        super().clean()
        if self.is_trial and self.price_per_platform != 0:
            raise ValidationError({"price_per_platform": _("قیمت پلن رایگان باید صفر باشد.")})
        if not self.is_trial and self.is_active and self.price_per_platform <= 0:
            raise ValidationError({"price_per_platform": _("قیمت پلن پولی باید بزرگ‌تر از صفر باشد.")})


class ForwardSubscriptionAccount(models.Model):
    """حساب اشتراک کاربر در وین فوروارد برای ثبت استفاده یک‌بارمصرف از دوره رایگان و قفل تراکنش‌ها."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="forward_subscription_account",
        verbose_name=_("کاربر"),
    )
    trial_used_at = jmodels.jDateTimeField(_("زمان فعال‌سازی دوره رایگان"), null=True, blank=True)
    first_paid_at = jmodels.jDateTimeField(_("زمان اولین خرید پولی"), null=True, blank=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("حساب اشتراک وین فوروارد")
        verbose_name_plural = _("حساب‌های اشتراک وین فوروارد")
        ordering = ["-pk"]

    def __str__(self) -> str:
        """نمایش خوانای حساب اشتراک کاربر."""
        return str(self.user)

    @property
    def can_use_trial(self) -> bool:
        """بررسی مجاز بودن کاربر برای فعال‌سازی دوره رایگان ۷ روزه."""
        return self.trial_used_at is None


class ForwardPlatformAccess(models.Model):
    """دسترسی فعال و تاریخ انقضای هر پلتفرم برای کاربر در وین فوروارد."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forward_platform_accesses",
        verbose_name=_("کاربر"),
    )
    platform_slug = models.CharField(
        _("پلتفرم"),
        max_length=20,
        choices=FORWARD_PLATFORMS,
        db_index=True,
    )
    plan = models.ForeignKey(
        ForwardSubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_accesses",
        verbose_name=_("آخرین پلن"),
    )
    started_at = jmodels.jDateTimeField(_("شروع اشتراک"), default=timezone.now)
    expires_at = jmodels.jDateTimeField(_("پایان اشتراک"), db_index=True)
    is_active = models.BooleanField(_("فعال"), default=True)
    updated_at = jmodels.jDateTimeField(_("آخرین بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("دسترسی پلتفرم وین فوروارد")
        verbose_name_plural = _("دسترسی پلتفرم‌های وین فوروارد")
        ordering = ["platform_slug"]
        constraints = [
            models.UniqueConstraint(fields=["user", "platform_slug"], name="unique_forward_user_platform_access"),
        ]

    def __str__(self) -> str:
        """نمایش خوانای وضعیت دسترسی پلتفرم کاربر."""
        return f"{self.user} — {self.get_platform_slug_display()} (تا {self.expires_at})"

    @property
    def is_valid(self) -> bool:
        """بررسی فعال و منقضی‌نشدن دسترسی پلتفرم در لحظه فعلی."""
        return bool(self.is_active and self.expires_at and self.expires_at > timezone.now())

    @property
    def remaining_days(self) -> int:
        """محاسبه تعداد روزهای باقی‌مانده از اشتراک این پلتفرم."""
        if not self.is_valid:
            return 0
        delta = self.expires_at - timezone.now()
        return max(1, delta.days + (1 if delta.seconds > 0 else 0))


class ForwardSubscriptionOrder(models.Model):
    """سفارش خرید، تمدید یا افزودن پلتفرم در اشتراک وین فوروارد."""

    class OrderKind(models.TextChoices):
        NEW = "new", _("خرید جدید")
        RENEW = "renew", _("تمدید اشتراک")
        ADD_PLATFORM = "add_platform", _("افزودن پلتفرم در میانه دوره")

    class Status(models.TextChoices):
        PENDING = "pending", _("در انتظار پرداخت")
        PAID = "paid", _("پرداخت‌شده")
        CANCELLED = "cancelled", _("لغوشده")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forward_subscription_orders",
        verbose_name=_("کاربر"),
    )
    plan = models.ForeignKey(
        ForwardSubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name=_("پلن"),
    )
    order_kind = models.CharField(
        _("نوع سفارش"),
        max_length=20,
        choices=OrderKind.choices,
        default=OrderKind.NEW,
    )
    platforms = models.JSONField(
        _("پلتفرم‌های انتخاب‌شده"),
        default=list,
        help_text=_("لیست slug پلتفرم‌های انتخاب‌شده (مثلاً ['bale', 'eitaa'])."),
    )
    duration_days = models.PositiveSmallIntegerField(_("مدت اعمال‌شده (روز)"), default=30)
    price_per_platform = models.PositiveBigIntegerField(_("مبلغ واحد هر پلتفرم (تومان)"), default=0)
    subtotal_amount = models.PositiveBigIntegerField(_("جمع پایه (تومان)"), default=0)
    vat_amount = models.PositiveBigIntegerField(_("مالیات (تومان)"), default=0)
    total_amount = models.PositiveBigIntegerField(_("مبلغ قابل پرداخت (تومان)"), default=0)
    status = models.CharField(
        _("وضعیت"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    paid_at = jmodels.jDateTimeField(_("زمان پرداخت"), null=True, blank=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("سفارش اشتراک وین فوروارد")
        verbose_name_plural = _("سفارش‌های اشتراک وین فوروارد")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """نمایش خوانای سفارش اشتراک برای ادمین و قالب‌ها."""
        return f"سفارش #{self.pk} — {self.plan.name} ({self.get_status_display()})"

    @property
    def selected_platforms(self) -> list[str]:
        """سازگاری با نام selected_platforms برای برگرداندن لیست اسلاگ پلتفرم‌ها."""
        return list(self.platforms or [])

    @property
    def platforms_count(self) -> int:
        """تعداد پلتفرم‌های انتخاب‌شده در این سفارش."""
        return len(self.platforms or [])

    @property
    def unit_price(self) -> int:
        """مبلغ واحد هر پلتفرم در این سفارش (معادل price_per_platform)."""
        return int(self.price_per_platform or 0)

    @property
    def platform_labels(self) -> list[str]:
        """تبدیل لیست slugهای پلتفرم به نام فارسی خوانا."""
        return [FORWARD_PLATFORM_LABELS.get(slug, slug) for slug in (self.platforms or [])]
