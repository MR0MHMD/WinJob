from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class InstagramConnection(models.Model):
    """حساب اینستاگرامی که مالک آن برای وین دایرکت ثبت می‌کند."""

    class Status(models.TextChoices):
        SIMULATED = "simulated", _("آزمایشی")
        DISCONNECTED = "disconnected", _("قطع شده")
        CONNECTED = "connected", _("متصل")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="windirect_connections",
        verbose_name=_("مالک حساب"),
    )
    username = models.CharField(_("نام کاربری اینستاگرام"), max_length=100)
    instagram_user_id = models.CharField(
        _("شناسه رسمی حساب اینستاگرام"), max_length=100,
        unique=True, null=True, blank=True,
    )
    status = models.CharField(
        _("وضعیت اتصال"), max_length=20,
        choices=Status.choices, default=Status.SIMULATED,
    )
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        verbose_name = _("حساب اینستاگرام وین دایرکت")
        verbose_name_plural = _("حساب‌های اینستاگرام وین دایرکت")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "status"])]

    def __str__(self):
        return f"@{self.username} ({self.get_status_display()})"


class Automation(models.Model):
    """قانون پاسخ به کامنت برای یک حساب و پست مشخص یا همهٔ پست‌ها."""

    class MatchType(models.TextChoices):
        CONTAINS = "contains", _("شامل")
        EXACT = "exact", _("برابر")

    connection = models.ForeignKey(
        InstagramConnection, on_delete=models.CASCADE,
        related_name="automations", verbose_name=_("حساب اینستاگرام"),
    )
    name = models.CharField(_("نام قانون"), max_length=150)
    media_id = models.CharField(
        _("شناسه پست"), max_length=100, blank=True,
        help_text=_("اگر خالی باشد، قانون برای همهٔ پست‌های این حساب اعمال می‌شود."),
    )
    keyword = models.CharField(_("کلیدواژه"), max_length=100)
    match_type = models.CharField(
        _("نوع تطبیق"), max_length=10,
        choices=MatchType.choices, default=MatchType.CONTAINS,
    )
    reply_text = models.TextField(_("متن پاسخ"))
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        verbose_name = _("قانون وین دایرکت")
        verbose_name_plural = _("قوانین وین دایرکت")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["connection", "is_active", "media_id"])]

    def __str__(self):
        return self.name


class CommentEvent(models.Model):
    """کامنت ثبت‌شده برای اجرای یکتای قوانین یک حساب."""

    connection = models.ForeignKey(
        InstagramConnection, on_delete=models.CASCADE,
        related_name="comment_events", verbose_name=_("حساب اینستاگرام"),
    )
    external_comment_id = models.CharField(_("شناسه کامنت"), max_length=100)
    media_id = models.CharField(_("شناسه پست"), max_length=100)
    text = models.TextField(_("متن کامنت"))
    created_at = jmodels.jDateTimeField(_("تاریخ دریافت"), auto_now_add=True)

    class Meta:
        verbose_name = _("رویداد کامنت وین دایرکت")
        verbose_name_plural = _("رویدادهای کامنت وین دایرکت")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "external_comment_id"],
                name="windirect_unique_comment",
            ),
        ]

    def __str__(self):
        return f"کامنت {self.external_comment_id} - {self.connection.username}"


class AutomationExecution(models.Model):
    """نتیجهٔ اجرای یک قانون برای یک کامنت، بدون اجرای تکراری."""

    class Status(models.TextChoices):
        SIMULATED = "simulated", _("شبیه‌سازی شد")
        SENT = "sent", _("ارسال شد")
        FAILED = "failed", _("ناموفق")

    automation = models.ForeignKey(
        Automation, on_delete=models.CASCADE,
        related_name="executions", verbose_name=_("قانون"),
    )
    event = models.ForeignKey(
        CommentEvent, on_delete=models.CASCADE,
        related_name="executions", verbose_name=_("رویداد کامنت"),
    )
    status = models.CharField(
        _("وضعیت اجرا"), max_length=20,
        choices=Status.choices, default=Status.SIMULATED,
    )
    response_text = models.TextField(_("متن پاسخ ثبت‌شده"))
    created_at = jmodels.jDateTimeField(_("تاریخ اجرا"), auto_now_add=True)

    class Meta:
        verbose_name = _("اجرای قانون وین دایرکت")
        verbose_name_plural = _("اجراهای قوانین وین دایرکت")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["automation", "event"],
                name="windirect_unique_execution",
            ),
        ]

    def __str__(self):
        return f"{self.automation.name} - {self.event.external_comment_id}"
