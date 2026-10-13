from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels

from windirect.common.models import PanelAsset


class DirectRule(PanelAsset):
    """قانون پاسخ به پیام ورودی؛ اولین قانون منطبق اجرا می‌شود."""

    class ResponseType(models.TextChoices):
        TEXT = "text", _("پاسخ متنی")
        SHOWCASE = "showcase", _("نمایش ویترین")
        FORM = "form", _("شروع فرم")

    keyword = models.CharField(_("کلمهٔ فعال‌کننده"), max_length=100)
    match_type = models.CharField(
        _("نوع تطبیق"),
        max_length=20,
        choices=[("exact", "برابر"), ("contains", "شامل")],
        default="exact",
    )
    priority = models.PositiveSmallIntegerField(
        _("اولویت"),
        default=10,
        help_text=_("عدد کمتر زودتر بررسی می‌شود؛ در تساوی، قانون قدیمی‌تر."),
    )
    response_type = models.CharField(
        _("نوع پاسخ"),
        max_length=15,
        choices=ResponseType.choices,
        default=ResponseType.TEXT,
    )
    reply_text = models.TextField(_("متن پاسخ"), max_length=1000, blank=True)
    showcase = models.ForeignKey(
        "windirect_showcases.Showcase",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("ویترین"),
    )
    form = models.ForeignKey(
        "windirect_forms.ConversationForm",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("فرم"),
    )

    class Meta(PanelAsset.Meta):
        db_table = "windirect_directrule"
        verbose_name = _("قانون دایرکت")
        verbose_name_plural = _("قوانین دایرکت")
        ordering = ["priority", "pk"]
        indexes = [
            models.Index(
                fields=["connection", "is_active", "priority"],
                name="wd_direct_route_idx",
            )
        ]

    def clean(self):
        """پاسخ انتخابی و تعلق ابزار به همان حساب را کنترل می‌کند."""
        super().clean()
        if not self.keyword.strip():
            raise ValidationError({"keyword": "کلمهٔ فعال‌کننده خالی است."})
        if self.response_type == self.ResponseType.TEXT and not self.reply_text.strip():
            raise ValidationError({"reply_text": "متن پاسخ را وارد کنید."})
        for field, kind in [("showcase", "showcase"), ("form", "form")]:
            asset = getattr(self, field, None)
            if self.response_type == kind and asset is None:
                raise ValidationError({field: "ابزار پاسخ را انتخاب کنید."})
            if asset and asset.connection_id != self.connection_id:
                raise ValidationError({field: "ابزار باید متعلق به همین حساب باشد."})


class DirectMessageEvent(models.Model):
    """پیام نمونه و خروجی ثبت‌شده برای جلوگیری از اجرای تکراری."""

    connection = models.ForeignKey(
        "windirect_connections.InstagramConnection",
        on_delete=models.PROTECT,
        verbose_name=_("حساب"),
    )
    external_message_id = models.CharField(_("شناسهٔ پیام"), max_length=100)
    sender_id = models.CharField(_("شناسهٔ مخاطب آزمایشی"), max_length=100)
    text = models.TextField(_("متن ورودی"), max_length=2000)
    rule = models.ForeignKey(
        DirectRule,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("قانون اجراشده"),
    )
    response = models.JSONField(_("خروجی شبیه‌سازی"), default=dict)
    created_at = jmodels.jDateTimeField(_("تاریخ دریافت"), auto_now_add=True)

    class Meta:
        db_table = "windirect_directmessageevent"
        verbose_name = _("پیام آزمایشی دایرکت")
        verbose_name_plural = _("پیام‌های آزمایشی دایرکت")
        ordering = ["-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "external_message_id"],
                name="wd_unique_direct_message",
            )
        ]

    def __str__(self):
        return self.external_message_id
