""" مدل‌های اپ messengers — اتصال کاربران سایت به ربات‌های پیام‌رسان. """

from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from django.utils import timezone
from datetime import timedelta
from django.db import models


class BotUser(models.Model):
    """
    اتصال کاربر سایت (CustomUser) به حساب کاربری در ربات‌های پیام‌رسان.

    - هر کاربر در هر پلتفرم یک حساب ربات دارد.
    - فقط بعد از لینک موفق ساخته می‌شود.
    - پلتفرم از core.Platform می‌آید تا با Channel/AdType/Campaign یکپارچه باشد.
    """

    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name="bot_users", verbose_name=_("کاربر"),)
    platform = models.ForeignKey("core.Platform", on_delete=models.PROTECT, related_name="bot_users", verbose_name=_("پلتفرم"),)
    chat_id = models.CharField(_("شناسه چت"), max_length=64, help_text=_("شناسه یکتای کاربر در این پیام‌رسان"),)
    username = models.CharField(_("نام کاربری"), max_length=64, blank=True, help_text=_("در صورت وجود: @username"),)
    api_token = models.CharField(
        _("توکن API اختصاصی"),
        max_length=256,
        blank=True,
        null=True,
        help_text=_("برای پلتفرم‌هایی مثل ایتا که هر کاربر توکن اختصاصی دارد (مثلاً ایتایار). برای بله خالی بماند."),
    )
    is_verified = models.BooleanField(_("تأیید شده"), default=False, help_text=_("آیا اتصال با موفقیت انجام شده است؟"),)
    linked_at = jmodels.jDateTimeField(_("تاریخ اتصال"), auto_now_add=True,)
    last_seen_at = jmodels.jDateTimeField(_("آخرین فعالیت"), null=True, blank=True, help_text=_("آخرین تعامل کاربر با ربات"),)

    class Meta:
        verbose_name = _("کاربر ربات")
        verbose_name_plural = _("کاربران ربات")
        ordering = ["-linked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform"],
                name="unique_user_platform_botuser",
            ),
            models.UniqueConstraint(
                fields=["platform", "chat_id"],
                name="unique_platform_chat_id_botuser",
            ),
        ]

    def __str__(self):
        """نمایش خوانای BotUser در ادمین و لاگ‌ها."""
        return f"{self.user} @ {self.platform.name}-({self.chat_id})"

    def mark_seen(self):
        """بروزرسانی last_seen_at هنگام تعامل کاربر با ربات."""
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at"])


class ConnectToken(models.Model):
    """توکن یک بار مصرف برای اتصال کاربر سایت به ربات پیام‌رسان از طریق Deep Link."""

    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name="connect_tokens", verbose_name=_("کاربر"),)
    platform = models.ForeignKey("core.Platform", on_delete=models.CASCADE, related_name="connect_tokens", verbose_name=_("پلتفرم"),)
    token = models.CharField(_("توکن اتصال"), max_length=64, unique=True, db_index=True,)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True,)
    used_at = jmodels.jDateTimeField(_("تاریخ استفاده"), null=True, blank=True,)

    class Meta:
        verbose_name = _("توکن اتصال")
        verbose_name_plural = _("توکن‌های اتصال")
        ordering = ["-created_at"]

    def __str__(self):
        """نمایش خوانای توکن برای ادمین."""
        return f"{self.user} @ {self.platform.name} ({self.token[:8]}...)"

    def is_valid(self):
        """بررسی اعتبار توکن (۱۰ دقیقه اعتبار و استفاده نشده باشد)."""
        if self.used_at:
            return False
        expiry = self.created_at + timedelta(minutes=10)
        return timezone.now() <= expiry
