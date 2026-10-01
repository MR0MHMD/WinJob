"""تلاش‌های پرداخت درگاه اشتراک؛ اطلاعات قطعی در دیتابیس نگه‌داری می‌شوند."""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class SubscriptionPaymentAttempt(models.Model):
    """شناسهٔ یکتای درگاه و پرداخت مربوط به سفارش اشتراک."""

    order = models.ForeignKey(
        "windirect.SubscriptionOrder",
        on_delete=models.PROTECT,
        related_name="attempts",
        verbose_name=_("سفارش اشتراک"),
    )
    payment = models.OneToOneField(
        "Payment", on_delete=models.PROTECT, verbose_name=_("پرداخت")
    )
    authority = models.CharField(
        _("شناسهٔ درگاه"), max_length=255, unique=True, null=True, blank=True
    )
    gateway_url = models.URLField(_("نشانی پرداخت"), max_length=1000, blank=True)
    verified_at = jmodels.jDateTimeField(
        _("زمان تأیید و تعیین تکلیف"), null=True, blank=True
    )
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("تلاش پرداخت اشتراک")
        verbose_name_plural = _("تلاش‌های پرداخت اشتراک")
        ordering = ["-pk"]

    def __str__(self):
        return f'{self.order} — {self.authority or "در حال ایجاد"}'
