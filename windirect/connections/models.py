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
        _("شناسه رسمی حساب اینستاگرام"),
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    status = models.CharField(
        _("وضعیت اتصال"),
        max_length=20,
        choices=Status.choices,
        default=Status.SIMULATED,
    )

    # ==================== فیلدهای توکن (جدید) ====================
    access_token = models.TextField(
        _("توکن دسترسی"),
        blank=True,
        default="",
        help_text=_("توکن بلندمدت (۶۰ روزه) اینستاگرام"),
    )

    token_expires_at = jmodels.jDateTimeField(
        _("انقضای توکن"),
        null=True,
        blank=True,
        help_text=_("زمانی که توکن منقضی می‌شود"),
    )

    token_refreshed_at = jmodels.jDateTimeField(
        _("آخرین تازه‌سازی توکن"),
        null=True,
        blank=True,
        help_text=_("زمانی که توکن آخرین بار تازه شد"),
    )

    # ==================== متادیتا ====================
    profile_picture = models.ImageField(
        _("تصویر پروفایل"),
        upload_to="windirect/avatars/",
        null=True,
        blank=True,
    )

    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        db_table = "windirect_instagramconnection"
        verbose_name = _("حساب اینستاگرام")
        verbose_name_plural = _("حساب های اینستاگرام")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["token_expires_at"]),  # ← جدید برای cron job
        ]

    def __str__(self):
        return f"@{self.username} ({self.get_status_display()})"

    # ==================== متدهای کمکی ====================
    @property
    def is_token_expired(self):
        """آیا توکن منقضی شده یا در ۷ روز آینده منقضی می‌شود؟"""
        from django.utils import timezone
        from datetime import timedelta

        if not self.token_expires_at:
            return True
        return self.token_expires_at <= timezone.now() + timedelta(days=7)

    @property
    def is_official_connection(self):
        """آیا اتصال رسمی (نه شبیه‌سازی) است؟"""
        return (
            self.status == self.Status.CONNECTED
            and self.instagram_user_id
            and not self.instagram_user_id.startswith("sim_")
        )
