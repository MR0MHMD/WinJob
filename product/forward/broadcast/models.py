"""
مدل‌های اپ broadcast — قلب وین فوروارد برای ارسال گروهی پیام.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class BroadcastChannel(models.Model):
    """کانال ثبت‌شده در وین فوروارد — مستقل از influencers.Channel."""

    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name="broadcast_channels", verbose_name=_("کاربر"),)
    platform = models.ForeignKey("core.Platform", on_delete=models.PROTECT, related_name="broadcast_channels", verbose_name=_("پلتفرم"),)
    chat_id = models.CharField(_("شناسه کانال"), max_length=64, help_text=_("شناسه یکتای کانال در پلتفرم (مثلاً @my_channel یا -100123456789)"),)
    title = models.CharField(_("عنوان کانال"), max_length=200,)
    username = models.CharField(_("نام کاربری کانال"), max_length=64, blank=True, help_text=_("در صورت وجود: @username"),)
    bot_is_admin = models.BooleanField(_("ربات ادمین است"), default=False,)
    bot_admin_checked_at = jmodels.jDateTimeField(_("آخرین بررسی ادمین بودن ربات"), null=True, blank=True,)
    verification_token = models.CharField(_("توکن تأیید"), max_length=64, blank=True, db_index=True, help_text=_("توکن یک‌بارمصرف برای تأیید مالکیت از طریق Deep Link"),)
    verification_token_created_at = jmodels.jDateTimeField(_("زمان ایجاد توکن"), null=True, blank=True,)
    verification_token_used_at = jmodels.jDateTimeField(_("زمان استفاده از توکن"), null=True, blank=True,)
    is_active = models.BooleanField(_("فعال"), default=True, help_text=_("آیا ارسال به این کانال مجاز است؟"),)
    last_broadcast_at = jmodels.jDateTimeField(_("آخرین ارسال"), null=True, blank=True,)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True,)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True,)

    class Meta:
        verbose_name = _("کانال وین فوروارد")
        verbose_name_plural = _("کانال‌های وین فوروارد")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "platform", "chat_id"], name="unique_user_platform_channel_broadcast"),
        ]
        indexes = [
            models.Index(fields=["platform", "bot_is_admin"], name="idx_broadcast_channel_active"),
            models.Index(fields=["verification_token"], name="idx_broadcast_channel_token"),
        ]

    def __str__(self):
        """نمایش خوانای کانال برای ادمین و لاگ."""
        return f"{self.title} @ {self.platform.name} ({self.chat_id})"

    def is_token_valid(self):
        """آیا توکن تأیید هنوز معتبر است؟ (۱۰ دقیقه اعتبار)"""
        if not self.verification_token or self.verification_token_used_at:
            return False
        if not self.verification_token_created_at:
            return False
        expiry = self.verification_token_created_at + timedelta(minutes=10)
        return timezone.now() <= expiry

    def mark_verified(self):
        """تأیید موفق کانال و باطل کردن توکن."""
        self.bot_is_admin = True
        self.bot_admin_checked_at = timezone.now()
        self.verification_token_used_at = timezone.now()
        self.save(update_fields=["bot_is_admin", "bot_admin_checked_at", "verification_token_used_at"])


class BroadcastMessage(models.Model):
    """محتوای یک پیام ارسالی — متن، عکس، ویدیو، صوت، ویس، فایل، گیف یا استیکر."""

    class ContentType(models.TextChoices):
        TEXT = "text", _("متن")
        PHOTO = "photo", _("عکس")
        VIDEO = "video", _("ویدیو")
        AUDIO = "audio", _("فایل صوتی")
        VOICE = "voice", _("پیام صوتی (ویس)")
        DOCUMENT = "document", _("فایل")
        ANIMATION = "animation", _("گیف")
        STICKER = "sticker", _("استیکر")

    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name="broadcast_messages", verbose_name=_("کاربر"),)
    content_type = models.CharField(_("نوع محتوا"), max_length=20, choices=ContentType.choices, default=ContentType.TEXT, db_index=True,)
    text = models.TextField(_("متن پیام"), max_length=4096, blank=True, help_text=_("حداکثر ۴۰۹۶ کاراکتر — برای عکس/ویدیو/صوت به عنوان کپشن استفاده می‌شود"),)
    file = models.FileField(_("فایل"), upload_to="broadcast/messages/%Y/%m/", null=True, blank=True,)
    platform_file_ids = models.JSONField(_("شناسه فایل در پلتفرم‌ها"), default=dict, blank=True, help_text=_("کش شناسه فایل‌ها برای ارسال سریع بدون آپلود مجدد"), )
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True,)

    class Meta:
        verbose_name = _("پیام ارسالی")
        verbose_name_plural = _("پیام‌های ارسالی")
        ordering = ["-created_at"]

    def __str__(self):
        """نمایش کوتاه پیام برای ادمین و لاگ."""
        snippet = (self.text[:40] + "…") if self.text and len(self.text) > 40 else (self.text or "—")
        return f"#{self.pk} [{self.get_content_type_display()}] {snippet}"

    @property
    def has_media(self):
        """آیا پیام حاوی فایل است؟"""
        return bool(self.file)

    def clean(self):
        """اعتبارسنجی هم‌خوانی نوع محتوا با وجود فایل، متن یا file_id."""
        if self.content_type == self.ContentType.TEXT and self.file:
            raise ValidationError({"file": _("برای پیام متنی، فایل نباید آپلود شود.")})

        # پیام غیرمتنی باید یا فایل فیزیکی داشته باشه یا file_id از پلتفرم
        if self.content_type != self.ContentType.TEXT:
            has_platform_file = bool(self.platform_file_ids)
            if not self.file and not has_platform_file:
                raise ValidationError({"file": _("برای این نوع محتوا، فایل یا شناسه فایل پلتفرم الزامی است.")})

        if not (self.text or "").strip() and not self.has_media and not self.platform_file_ids:
            raise ValidationError({"text": _("حداقل یکی از متن، فایل یا شناسه فایل باید موجود باشد.")})

    def save(self, *args, **kwargs):
        """اجرای اعتبارسنجی قبل از ذخیره."""
        self.full_clean()
        super().save(*args, **kwargs)


class BroadcastJob(models.Model):
    """یک عملیات ارسال گروهی — یک پیام به چند کانال."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("پیش‌نویس")
        PENDING = "pending", _("در انتظار")
        RUNNING = "running", _("در حال اجرا")
        DONE = "done", _("کامل موفق")
        PARTIAL = "partial", _("نیمه‌موفق")
        FAILED = "failed", _("کامل ناموفق")

    message = models.ForeignKey(BroadcastMessage, on_delete=models.CASCADE, related_name="jobs", verbose_name=_("پیام"),)
    status = models.CharField(_("وضعیت"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True,)
    total_targets = models.PositiveIntegerField(_("تعداد کل مقاصد"), default=0,)
    success_count = models.PositiveIntegerField(_("موفق"), default=0,)
    failed_count = models.PositiveIntegerField(_("ناموفق"), default=0,)
    started_at = jmodels.jDateTimeField(_("زمان شروع"), null=True, blank=True,)
    finished_at = jmodels.jDateTimeField(_("زمان پایان"), null=True, blank=True,)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True,)

    class Meta:
        verbose_name = _("جاب ارسال")
        verbose_name_plural = _("جاب‌های ارسال")
        ordering = ["-created_at"]

    def __str__(self):
        """نمایش خوانای جاب برای ادمین و لاگ."""
        return f"جاب #{self.pk} — {self.get_status_display()} ({self.success_count}/{self.total_targets})"

    @property
    def is_finished(self):
        """آیا جاب به وضعیت نهایی رسیده است؟"""
        return self.status in (self.Status.DONE, self.Status.PARTIAL, self.Status.FAILED)

    @property
    def success_rate(self):
        """درصد موفقیت بر اساس تعداد کل مقاصد."""
        if not self.total_targets:
            return 0
        return int(self.success_count * 100 / self.total_targets)

    def recalculate_counts(self, save=True):
        """بازشماری موفق/ناموفق/کل از روی Targetها و به‌روزرسانی خودکار وضعیت."""
        agg = self.targets.aggregate(
            total=Count("id"),
            success=Count("id", filter=Q(status=BroadcastTarget.Status.SUCCESS)),
            failed=Count("id", filter=Q(status=BroadcastTarget.Status.FAILED)),
        )
        self.total_targets = agg["total"] or 0
        self.success_count = agg["success"] or 0
        self.failed_count = agg["failed"] or 0
        if self.total_targets > 0:
            if self.success_count == self.total_targets:
                self.status = self.Status.DONE
                self.finished_at = timezone.now()
            elif self.failed_count == self.total_targets:
                self.status = self.Status.FAILED
                self.finished_at = timezone.now()
            elif (self.success_count + self.failed_count) == self.total_targets:
                self.status = self.Status.PARTIAL
                self.finished_at = timezone.now()
        if save:
            self.save(update_fields=["total_targets", "success_count", "failed_count", "status", "finished_at"])


class BroadcastTarget(models.Model):
    """یک مقصد ارسال — کانال + نتیجه ارسال."""

    class Status(models.TextChoices):
        PENDING = "pending", _("در انتظار")
        RUNNING = "running", _("در حال ارسال")
        SUCCESS = "success", _("موفق")
        FAILED = "failed", _("ناموفق")
        SKIPPED = "skipped", _("رد شده")

    job = models.ForeignKey(BroadcastJob, on_delete=models.CASCADE, related_name="targets", verbose_name=_("جاب"),)
    channel = models.ForeignKey(BroadcastChannel, on_delete=models.PROTECT, related_name="broadcast_targets", verbose_name=_("کانال"),)
    status = models.CharField(_("وضعیت"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True,)
    platform_message_id = models.CharField(_("شناسه پیام در پلتفرم"), max_length=100, blank=True, help_text=_("شناسه‌ای که API پیام‌رسان برگردانده"),)
    error_message = models.TextField(_("خطا"), blank=True, help_text=_("در صورت ناموفق بودن، متن کامل خطا"),)
    sent_at = jmodels.jDateTimeField(_("زمان ارسال"), null=True, blank=True,)
    retry_count = models.PositiveSmallIntegerField(_("تعداد تلاش"), default=0,)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True,)

    class Meta:
        verbose_name = _("مقصد ارسال")
        verbose_name_plural = _("مقاصد ارسال")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "channel"], name="unique_job_channel_target"),
        ]
        indexes = [
            models.Index(fields=["job", "status"], name="idx_target_job_status"),
        ]

    def __str__(self):
        """نمایش خوانای مقصد برای ادمین و لاگ."""
        return f"جاب #{self.job_id} → {self.channel.title} [{self.get_status_display()}]"

    def mark_success(self, platform_message_id=""):
        """علامت‌گذاری به عنوان موفق و ثبت شناسه پیام در پلتفرم."""
        self.status = self.Status.SUCCESS
        self.platform_message_id = platform_message_id or ""
        self.sent_at = timezone.now()
        self.error_message = ""
        self.save(update_fields=["status", "platform_message_id", "sent_at", "error_message"])

    def mark_failed(self, error_message=""):
        """علامت‌گذاری به عنوان ناموفق و ثبت خطا."""
        self.status = self.Status.FAILED
        self.error_message = (error_message or "")[:2000]
        self.save(update_fields=["status", "error_message"])
