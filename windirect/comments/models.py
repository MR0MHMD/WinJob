from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class Automation(models.Model):
    """کامنت هوشمند: پیکربندی کامل یک قاعده پاسخ‌دهی به کامنت یا لایو."""

    class TargetType(models.TextChoices):
        POST = "post", _("پست")
        LIVE = "live", _("لایو")

    class ReplyChannel(models.TextChoices):
        COMMENT = "comment", _("پاسخ در کامنت")
        DIRECT = "direct", _("پاسخ در دایرکت")

    class MatchType(models.TextChoices):
        CONTAINS = "contains", _("شامل")
        EXACT = "exact", _("برابر")

    class DirectKind(models.TextChoices):
        TEXT = "text", _("متن")
        AUDIO = "audio", _("صوت")
        IMAGE = "image", _("تصویر")
        VIDEO = "video", _("ویدیو")

    # ==================== مالکیت و نام ====================
    connection = models.ForeignKey(
        "connections.InstagramConnection",
        on_delete=models.CASCADE,
        related_name="automations",
        verbose_name=_("حساب اینستاگرام"),
    )
    name = models.CharField(_("نام کامنت هوشمند"), max_length=150)

    # ==================== نوع هدف ====================
    target_type = models.CharField(
        _("نوع هدف"),
        max_length=10,
        choices=TargetType.choices,
        default=TargetType.POST,
    )

    # ==================== انتخاب پست (فقط post) ====================
    post_media_id = models.CharField(
        _("شناسه پست انتخاب‌شده"),
        max_length=100,
        blank=True,
        help_text=_("اگر خالی باشد، قانون روی همهٔ پست‌ها اعمال می‌شود."),
    )
    post_is_simulated = models.BooleanField(
        _("پست آزمایشی"),
        default=False,
        help_text=_("در حالت آزمایشی، پست واقعی انتخاب نشده است."),
    )

    # ==================== تطبیق ====================
    match_type = models.CharField(
        _("نوع تطبیق"),
        max_length=10,
        choices=MatchType.choices,
        default=MatchType.CONTAINS,
    )

    # ==================== کانال پاسخ ====================
    reply_channel = models.CharField(
        _("کانال پاسخ"),
        max_length=10,
        choices=ReplyChannel.choices,
        default=ReplyChannel.COMMENT,
    )

    # ==================== فالو اجباری (فقط direct) ====================
    require_follow = models.BooleanField(_("فالو اجباری"), default=False)
    follow_prompt_text = models.TextField(
        _("متن پیام فالو"),
        max_length=500,
        blank=True,
        help_text=_("مثلاً: باید اول پیجم رو فالو کنی رفیق 🙃"),
    )
    follow_prompt_button = models.CharField(
        _("متن دکمه فالو"),
        max_length=50,
        blank=True,
        help_text=_("مثلاً: فالو کردم"),
    )

    # ==================== محتوای دایرکت (فقط direct) ====================
    direct_message_kind = models.CharField(
        _("نوع محتوای دایرکت"),
        max_length=10,
        choices=DirectKind.choices,
        default=DirectKind.TEXT,
        blank=True,
    )
    direct_message_text = models.TextField(
        _("متن دایرکت"),
        max_length=2000,
        blank=True,
    )

    # ==================== فایل مدیا (BoxAPI) ====================
    media_upload = models.OneToOneField(
        "MediaUpload",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="automation",
        verbose_name=_("فایل مدیا"),
        help_text=_("فایل آپلود شده در BoxAPI"),
    )

    # ==================== وضعیت و زمان ====================
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        db_table = "windirect_automation"
        verbose_name = _("کامنت هوشمند")
        verbose_name_plural = _("کامنت‌های هوشمند")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["connection", "is_active", "target_type"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """اعتبارسنجی‌های سطح مدل."""
        super().clean()

        # ==================== فالو اجباری فقط برای دایرکت ====================
        if self.require_follow and self.reply_channel != self.ReplyChannel.DIRECT:
            raise ValidationError(
                {"require_follow": "فالو اجباری فقط برای پاسخ در دایرکت مجاز است."}
            )
        if self.require_follow:
            if not self.follow_prompt_text.strip():
                raise ValidationError(
                    {"follow_prompt_text": "متن پیام فالو را وارد کنید."}
                )
            if not self.follow_prompt_button.strip():
                raise ValidationError(
                    {"follow_prompt_button": "متن دکمه فالو را وارد کنید."}
                )

        # ==================== محتوای دایرکت ====================
        if self.reply_channel == self.ReplyChannel.DIRECT:
            # ===== متن =====
            if self.direct_message_kind == self.DirectKind.TEXT:
                if not self.direct_message_text.strip():
                    raise ValidationError(
                        {"direct_message_text": "متن دایرکت را وارد کنید."}
                    )

            # ===== صوت/تصویر/ویدیو =====
            elif self.direct_message_kind in (
                    self.DirectKind.AUDIO,
                    self.DirectKind.IMAGE,
                    self.DirectKind.VIDEO,
            ):
                # چک کن فایل مدیا وصل شده
                if not self.media_upload:
                    raise ValidationError({
                        "direct_message_file": "فایل مدیای دایرکت را انتخاب کنید."
                    })

                # چک کن نوع فایل با kind مطابقت داشته باشه
                if self.media_upload.file_kind != self.direct_message_kind:
                    raise ValidationError({
                        "direct_message_file": "نوع فایل با محتوای انتخابی مطابقت ندارد."
                    })

            # ===== نوع نامعتبر =====
            else:
                raise ValidationError({
                    "direct_message_kind": "نوع محتوای دایرکت نامعتبر است."
                })

        # ==================== انتخاب پست فقط برای post ====================
        if self.target_type == self.TargetType.LIVE:
            if self.post_media_id:
                raise ValidationError(
                    {"post_media_id": "برای لایو، انتخاب پست معنایی ندارد."}
                )

    def has_media_file(self):
        """چک می‌کنه آیا rule فایل مدیا داره."""
        return bool(self.media_upload)

    def get_media_url(self):
        """URL فایل مدیا رو برمی‌گردونه."""
        if self.media_upload:
            return self.media_upload.boxapi_url
        return ""

    def get_media_size_display(self):
        """حجم فایل رو به صورت خوانا برمی‌گردونه."""
        if self.media_upload:
            return self.media_upload.get_size_display()
        return ""


class AutomationKeyword(models.Model):
    """فعال‌سازهای یک کامنت هوشمند (حداکثر ۳ کلمه)."""

    automation = models.ForeignKey(
        Automation,
        on_delete=models.CASCADE,
        related_name="keywords",
        verbose_name=_("کامنت هوشمند"),
    )
    value = models.CharField(_("فعال‌ساز"), max_length=100)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        db_table = "windirect_automationkeyword"
        verbose_name = _("فعال‌ساز کامنت هوشمند")
        verbose_name_plural = _("فعال‌سازهای کامنت هوشمند")
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["automation", "value"],
                name="windirect_unique_keyword_per_automation",
            ),
        ]

    def __str__(self):
        return self.value


class CommentReplyTemplate(models.Model):
    """متن‌های پاسخ کامنت (تا ۳ تا، به‌صورت تصادفی انتخاب می‌شوند)."""

    automation = models.ForeignKey(
        Automation,
        on_delete=models.CASCADE,
        related_name="comment_replies",
        verbose_name=_("کامنت هوشمند"),
    )
    text = models.TextField(_("متن پاسخ"), max_length=2000)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        db_table = "windirect_commentreplytemplate"
        verbose_name = _("متن پاسخ کامنت")
        verbose_name_plural = _("متن‌های پاسخ کامنت")
        ordering = ["pk"]

    def __str__(self):
        return self.text[:50]


class CommentEvent(models.Model):
    """کامنت ثبت‌شده برای اجرای یکتای قوانین یک حساب."""

    connection = models.ForeignKey(
        "connections.InstagramConnection",
        on_delete=models.CASCADE,
        related_name="comment_events",
        verbose_name=_("حساب اینستاگرام"),
    )
    external_comment_id = models.CharField(_("شناسه کامنت"), max_length=100)
    media_id = models.CharField(_("شناسه پست"), max_length=100)
    text = models.TextField(_("متن کامنت"))

    # ==================== جدید: اطلاعات کامنت‌کننده ====================
    customer_id = models.CharField(
        _("شناسه کامنت‌کننده"),
        max_length=100,
        blank=True,
        default="",
        help_text=_("data.from.id از Webhook — برای follow_status و send_message"),
    )
    customer_username = models.CharField(
        _("نام کاربری کامنت‌کننده"),
        max_length=100,
        blank=True,
        default="",
        help_text=_("data.from.username از Webhook"),
    )

    created_at = jmodels.jDateTimeField(_("تاریخ دریافت"), auto_now_add=True)

    class Meta:
        db_table = "windirect_commentevent"
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
    """نتیجهٔ اجرای یک کامنت هوشمند برای یک کامنت."""

    class Status(models.TextChoices):
        SIMULATED = "simulated", _("شبیه‌سازی شد")
        SENT = "sent", _("ارسال شد")
        FAILED = "failed", _("ناموفق")
        FOLLOW_REQUIRED = "follow_required", _("فالو اجباری")

    automation = models.ForeignKey(
        Automation,
        on_delete=models.CASCADE,
        related_name="executions",
        verbose_name=_("کامنت هوشمند"),
    )
    event = models.ForeignKey(
        CommentEvent,
        on_delete=models.CASCADE,
        related_name="executions",
        verbose_name=_("رویداد کامنت"),
    )
    status = models.CharField(
        _("وضعیت اجرا"),
        max_length=20,
        choices=Status.choices,
        default=Status.SIMULATED,
    )
    response_payload = models.JSONField(
        _("خروجی ثبت‌شده"),
        default=dict,
        help_text=_("ساختار خروجی: نوع، متن یا URL، و کانال ارسال."),
    )
    created_at = jmodels.jDateTimeField(_("تاریخ اجرا"), auto_now_add=True)

    class Meta:
        db_table = "windirect_automationexecution"
        verbose_name = _("اجرای کامنت هوشمند")
        verbose_name_plural = _("اجراهای کامنت هوشمند")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["automation", "event"],
                name="windirect_unique_execution",
            ),
        ]

    def __str__(self):
        return f"{self.automation.name} - {self.event.external_comment_id}"


class MediaUpload(models.Model):
    """
    فایل‌های آپلود شده در BoxAPI.

    - pending: فایل آپلود شده ولی هنوز به هیچ rule‌ای وصل نشده
    - attached: فایل به یه rule وصل شده
    - orphan: فایل منقضی شده (بیشتر از TTL در pending مونده)
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("در انتظار")
        ATTACHED = "attached", _("متصل")
        ORPHAN = "orphan", _("یتیم — منقضی شده")

    # ==================== فایل ====================
    boxapi_file_id = models.CharField(
        _("شناسه فایل در BoxAPI"),
        max_length=100,
        unique=True,
        help_text=_("UUID فایل در BoxAPI برای حذف"),
    )
    boxapi_url = models.URLField(
        _("URL فایل در BoxAPI"),
        max_length=500,
    )
    file_name = models.CharField(
        _("نام اصلی فایل"),
        max_length=255,
    )
    file_size = models.PositiveIntegerField(
        _("حجم فایل (بایت)"),
    )
    file_kind = models.CharField(
        _("نوع فایل"),
        max_length=10,
        help_text=_("audio / image / video"),
    )

    # ==================== وضعیت ====================
    status = models.CharField(
        _("وضعیت"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # ==================== زمان ====================
    created_at = jmodels.jDateTimeField(
        _("تاریخ ایجاد"),
        auto_now_add=True,
        db_index=True,
    )
    attached_at = jmodels.jDateTimeField(
        _("تاریخ اتصال"),
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "windirect_mediaupload"
        verbose_name = _("فایل آپلود شده")
        verbose_name_plural = _("فایل‌های آپلود شده")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.file_name} ({self.get_status_display()})"

    def get_size_display(self):
        """حجم فایل رو به صورت خوانا برمی‌گردونه."""
        size = self.file_size
        if not size:
            return ""
        if size < 1024:
            return f"{size} بایت"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} کیلوبایت"
        return f"{size / (1024 * 1024):.2f} مگابایت"

    def mark_attached(self):
        """فایل رو attached می‌کنه."""
        self.status = self.Status.ATTACHED
        self.attached_at = timezone.now()
        self.save(update_fields=["status", "attached_at"])

    def mark_orphan(self):
        """فایل رو orphan می‌کنه."""
        self.status = self.Status.ORPHAN
        self.save(update_fields=["status"])
