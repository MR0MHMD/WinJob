from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_jalali.admin.filters import JDateFieldListFilter
from core.utils.admin_utils import format_datetime
from .models import (
    Automation,
    AutomationExecution,
    AutomationKeyword,
    CommentEvent,
    CommentReplyTemplate,
)
from .inline_admin import (
    ExecutionInline,
    EventExecutionInline,
    KeywordInline,
    CommentReplyInline,
)
from windirect.common.admin import ReadOnlyLogAdmin


# ==================== Inlines برای Automation ====================
class KeywordInline(admin.TabularInline):
    """فعال‌سازهای یک کامنت هوشمند را در صفحهٔ همان قانون نمایش می‌دهد."""
    model = AutomationKeyword
    extra = 1
    max_num = 3
    fields = ("value",)
    verbose_name = _("فعال‌ساز")
    verbose_name_plural = _("فعال‌سازها (حداکثر ۳ تا)")


class CommentReplyInline(admin.TabularInline):
    """متن‌های پاسخ کامنت (ضد اسپم) را در صفحهٔ قانون نمایش می‌دهد."""
    model = CommentReplyTemplate
    extra = 1
    max_num = 3
    fields = ("text",)
    verbose_name = _("متن پاسخ")
    verbose_name_plural = _("متن‌های پاسخ کامنت (حداکثر ۳ تا)")


@admin.register(Automation)
class AutomationAdmin(admin.ModelAdmin):
    """کامنت‌های هوشمند را همراه با سابقهٔ اجرا مدیریت می‌کند."""

    list_display = (
        "name",
        "connection",
        "target_badge",
        "channel_badge",
        "match_type",
        "keywords_display",
        "is_active",
        "executions_count",
        "formatted_created_at",
    )
    list_filter = (
        "is_active",
        "target_type",
        "reply_channel",
        "match_type",
        ("created_at", JDateFieldListFilter),
    )
    search_fields = (
        "name",
        "keywords__value",
        "post_media_id",
        "connection__username",
        "connection__owner__phone_number",
    )
    autocomplete_fields = ("connection",)
    list_select_related = ("connection",)
    list_editable = ("is_active",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = (
        "formatted_created_at",
        "formatted_updated_at",
        "executions_count",
    )
    inlines = [KeywordInline, CommentReplyInline, ExecutionInline]

    fieldsets = (
        (
            _("اطلاعات پایه"),
            {
                "fields": ("connection", "name", "is_active"),
            },
        ),
        (
            _("نوع هدف و تطبیق"),
            {
                "fields": ("target_type", "post_media_id", "post_is_simulated", "match_type"),
            },
        ),
        (
            _("کانال پاسخ"),
            {
                "fields": ("reply_channel",),
            },
        ),
        (
            _("فالو اجباری (فقط دایرکت)"),
            {
                "fields": (
                    "require_follow",
                    "follow_prompt_text",
                    "follow_prompt_button",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("محتوای دایرکت (فقط دایرکت)"),
            {
                "fields": (
                    "direct_message_kind",
                    "direct_message_text",
                    "direct_message_url",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("تاریخچه"),
            {
                "fields": ("formatted_created_at", "formatted_updated_at", "executions_count"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description=_("نوع هدف"), ordering="target_type")
    def target_badge(self, obj):
        """نوع هدف (پست/لایو) را با رنگ نمایش می‌دهد."""
        colors = {"post": "#2563eb", "live": "#dc2626"}
        labels = {"post": "پست", "live": "لایو"}
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colors.get(obj.target_type, "#52525b"),
            labels.get(obj.target_type, obj.target_type),
        )

    @admin.display(description=_("کانال پاسخ"), ordering="reply_channel")
    def channel_badge(self, obj):
        """کانال پاسخ (کامنت/دایرکت) را با رنگ نمایش می‌دهد."""
        colors = {"comment": "#16a34a", "direct": "#7c3aed"}
        labels = {"comment": "کامنت", "direct": "دایرکت"}
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colors.get(obj.reply_channel, "#52525b"),
            labels.get(obj.reply_channel, obj.reply_channel),
        )

    @admin.display(description=_("فعال‌سازها"))
    def keywords_display(self, obj):
        """لیست فعال‌سازها را به‌صورت خلاصه نمایش می‌دهد."""
        if not obj.pk:
            return "—"
        keywords = obj.keywords.values_list("value", flat=True)[:3]
        return " · ".join(keywords) if keywords else "—"

    @admin.display(description=_("تعداد اجرا"))
    def executions_count(self, obj):
        """تعداد اجراهای ثبت‌شدهٔ قانون را نمایش می‌دهد."""
        return obj.executions.count() if obj.pk else 0

    @admin.display(description=_("تاریخ ایجاد"), ordering="created_at")
    def formatted_created_at(self, obj):
        """تاریخ ایجاد را با قالب رایج پنل نمایش می‌دهد."""
        return format_datetime(obj.created_at) if obj.pk else "-"

    @admin.display(description=_("آخرین ویرایش"), ordering="updated_at")
    def formatted_updated_at(self, obj):
        """تاریخ آخرین ویرایش را نمایش می‌دهد."""
        return format_datetime(obj.updated_at) if obj.pk else "-"


@admin.register(AutomationKeyword)
class AutomationKeywordAdmin(admin.ModelAdmin):
    """فعال‌سازها را برای جست‌وجو و بررسی نمایش می‌دهد."""

    list_display = ("value", "automation", "formatted_created_at")
    list_filter = (("created_at", JDateFieldListFilter),)
    search_fields = ("value", "automation__name", "automation__connection__username")
    autocomplete_fields = ("automation",)
    list_select_related = ("automation",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = ("formatted_created_at",)

    @admin.display(description=_("تاریخ ایجاد"), ordering="created_at")
    def formatted_created_at(self, obj):
        """تاریخ ایجاد را نمایش می‌دهد."""
        return format_datetime(obj.created_at)


@admin.register(CommentReplyTemplate)
class CommentReplyTemplateAdmin(admin.ModelAdmin):
    """متن‌های پاسخ کامنت را نمایش می‌دهد."""

    list_display = ("preview", "automation", "formatted_created_at")
    list_filter = (("created_at", JDateFieldListFilter),)
    search_fields = ("text", "automation__name", "automation__connection__username")
    autocomplete_fields = ("automation",)
    list_select_related = ("automation",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = ("formatted_created_at",)

    @admin.display(description=_("متن پاسخ"))
    def preview(self, obj):
        """پیش‌نمایش کوتاه متن پاسخ."""
        return obj.text[:80] + ("…" if len(obj.text) > 80 else "")

    @admin.display(description=_("تاریخ ایجاد"), ordering="created_at")
    def formatted_created_at(self, obj):
        """تاریخ ایجاد را نمایش می‌دهد."""
        return format_datetime(obj.created_at)


@admin.register(CommentEvent)
class CommentEventAdmin(ReadOnlyLogAdmin):
    """کامنت‌های دریافت‌شده و نتیجهٔ قوانین آن‌ها را نمایش می‌دهد."""

    list_display = (
        "external_comment_id",
        "connection",
        "media_id",
        "executions_count",
        "formatted_created_at",
    )
    list_filter = (("created_at", JDateFieldListFilter),)
    search_fields = ("external_comment_id", "media_id", "text", "connection__username")
    list_select_related = ("connection",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = (
        "connection",
        "external_comment_id",
        "media_id",
        "text",
        "formatted_created_at",
    )
    inlines = [EventExecutionInline]
    fieldsets = (
        (
            _("اطلاعات کامنت"),
            {
                "fields": ("connection", "external_comment_id", "media_id", "text"),
            },
        ),
        (
            _("تاریخچه"),
            {
                "fields": ("formatted_created_at",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description=_("تعداد اجرا"))
    def executions_count(self, obj):
        """تعداد قوانین اجراشده روی کامنت را نمایش می‌دهد."""
        return obj.executions.count()

    @admin.display(description=_("تاریخ دریافت"), ordering="created_at")
    def formatted_created_at(self, obj):
        """زمان دریافت کامنت را با قالب پنل نمایش می‌دهد."""
        return format_datetime(obj.created_at)


@admin.register(AutomationExecution)
class AutomationExecutionAdmin(ReadOnlyLogAdmin):
    """جزئیات خروجی هر کامنت هوشمند را برای پیگیری نمایش می‌دهد."""

    list_display = ("automation", "event", "status_badge", "payload_preview", "formatted_created_at")
    list_filter = ("status", ("created_at", JDateFieldListFilter))
    search_fields = ("automation__name", "event__external_comment_id")
    list_select_related = ("automation", "event")
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = (
        "automation",
        "event",
        "status",
        "response_payload",
        "formatted_created_at",
    )
    fieldsets = (
        (
            _("نتیجهٔ اجرا"),
            {
                "fields": ("automation", "event", "status", "response_payload"),
            },
        ),
        (
            _("تاریخچه"),
            {
                "fields": ("formatted_created_at",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description=_("وضعیت اجرا"), ordering="status")
    def status_badge(self, obj):
        """نتیجهٔ اجرا را با رنگ مناسب نمایش می‌دهد."""
        colors = {
            "simulated": "#2563eb",
            "sent": "#15803d",
            "failed": "#b91c1c",
            "follow_required": "#f59e0b",
        }
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colors.get(obj.status, "#52525b"),
            obj.get_status_display(),
        )

    @admin.display(description=_("خروجی"))
    def payload_preview(self, obj):
        """پیش‌نمایش کوتاه از response_payload."""
        payload = obj.response_payload or {}
        kind = payload.get("kind", "")
        if kind == "text":
            text = payload.get("text", "")
            return text[:60] + ("…" if len(text) > 60 else "")
        elif kind in ("image", "video", "audio"):
            return f"[{kind}] {payload.get('url', '')[:50]}"
        elif kind == "follow_prompt":
            return f"[فالو اجباری] {payload.get('prompt_text', '')[:40]}"
        return "—"

    @admin.display(description=_("تاریخ اجرا"), ordering="created_at")
    def formatted_created_at(self, obj):
        """زمان اجرای قانون را با قالب پنل نمایش می‌دهد."""
        return format_datetime(obj.created_at)