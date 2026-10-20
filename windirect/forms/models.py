# windirect/forms/models


from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels

from windirect.common.models import PanelAsset


class ConversationForm(PanelAsset):
    """تعریف پرسش‌نامه‌ای که پاسخ‌ها را مرحله‌به‌مرحله دریافت می‌کند."""

    completion_text = models.TextField(
        _("پیام پایان فرم"),
        max_length=1000,
        default="پاسخ‌های شما با موفقیت ثبت شد. همکاران ما با شما تماس می‌گیرند.",
    )
    cancel_keyword = models.CharField(_("کلمهٔ لغو فرم"), max_length=50, default="لغو")

    class Meta(PanelAsset.Meta):
        db_table = "windirect_conversationform"
        verbose_name = _("فرم مکالمه‌ای")
        verbose_name_plural = _("فرم‌های مکالمه‌ای")


class FormQuestion(models.Model):
    """پرسش و نوع اعتبارسنجی پاسخ در یک فرم."""

    class Kind(models.TextChoices):
        TEXT = "text", _("متن")
        NUMBER = "number", _("عدد صحیح")
        EMAIL = "email", _("ایمیل")
        PHONE = "phone", _("شماره همراه ایران")
        CHOICE = "choice", _("انتخاب از گزینه‌ها")

    form = models.ForeignKey(
        ConversationForm,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name=_("فرم"),
    )
    prompt = models.CharField(_("متن سؤال"), max_length=500)
    kind = models.CharField(
        _("نوع پاسخ"), max_length=15, choices=Kind.choices, default=Kind.TEXT
    )
    options = models.TextField(
        _("گزینه‌ها"),
        blank=True,
        max_length=1000,
        help_text=_("فقط برای سؤال انتخابی؛ هر گزینه در یک خط (۲ تا ۱۰ گزینه)."),
    )
    position = models.PositiveSmallIntegerField(
        _("ترتیب سؤال"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )

    class Meta:
        db_table = "windirect_formquestion"
        verbose_name = _("سؤال فرم")
        verbose_name_plural = _("سؤال‌های فرم")
        ordering = ["position", "pk"]

    def clean(self):
        """گزینه‌های پرسش انتخابی را پیش از ذخیره بررسی می‌کند."""
        super().clean()
        if self.kind == self.Kind.CHOICE:
            values = [v.strip() for v in self.options.splitlines() if v.strip()]
            if not 2 <= len(values) <= 10 or len(set(values)) != len(values):
                raise ValidationError(
                    {"options": "۲ تا ۱۰ گزینهٔ غیرتکراری وارد کنید."}
                )
            self.options = "\n".join(values)

    def __str__(self):
        return self.prompt


class FormSubmission(models.Model):
    """نسخهٔ ثابت سؤال‌ها و جواب‌های یک مخاطب؛ مستقل از ویرایش بعدی فرم."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("در حال تکمیل")
        COMPLETED = "completed", _("تکمیل‌شده")
        CANCELLED = "cancelled", _("لغوشده")

    form = models.ForeignKey(
        ConversationForm,
        on_delete=models.PROTECT,
        related_name="submissions",
        verbose_name=_("فرم"),
    )
    connection = models.ForeignKey(
        "connections.InstagramConnection",
        on_delete=models.PROTECT,
        verbose_name=_("حساب"),
    )
    sender_id = models.CharField(_("شناسهٔ مخاطب آزمایشی"), max_length=100)
    status = models.CharField(
        _("وضعیت"), max_length=15, choices=Status.choices, default=Status.ACTIVE
    )
    schema = models.JSONField(_("نسخهٔ سؤال‌ها و تنظیمات"), default=dict)
    answers = models.JSONField(_("پاسخ‌ها"), default=list)
    created_at = jmodels.jDateTimeField(_("تاریخ شروع"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("آخرین پاسخ"), auto_now=True)
    completed_at = jmodels.jDateTimeField(_("تاریخ تکمیل"), null=True, blank=True)

    class Meta:
        db_table = "windirect_formsubmission"
        verbose_name = _("پاسخ‌نامه")
        verbose_name_plural = _("پاسخ‌نامه‌ها")
        ordering = ["-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "sender_id"],
                condition=models.Q(status="active"),
                name="wd_one_active_form",
            )
        ]

    def __str__(self):
        return f"{self.form} — {self.sender_id}"
