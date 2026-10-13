from django.contrib import admin
from django_jalali.admin.filters import JDateFieldListFilter
from .models import DirectRule, DirectMessageEvent
from windirect.common.admin import ToolAdmin, ImmutableRecordAdmin


@admin.register(DirectRule)
class DirectRuleAdmin(ToolAdmin):
    """مدیریت اولویت و مقصد پاسخ قوانین دایرکت."""

    list_display = (
        "name",
        "connection",
        "keyword",
        "response_type",
        "priority",
        "is_active",
        "created_display",
    )
    list_filter = ToolAdmin.list_filter + ("response_type", "match_type")
    search_fields = ToolAdmin.search_fields + ("keyword",)
    autocomplete_fields = ("connection", "showcase", "form")
    fieldsets = (
        ("قانون", {"fields": ("connection", "name", "is_active", "priority")}),
        ("محرک", {"fields": ("keyword", "match_type")}),
        ("پاسخ", {"fields": ("response_type", "reply_text", "showcase", "form")}),
        (
            "تاریخچه",
            {
                "fields": ("created_display", "updated_display"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(DirectMessageEvent)
class DirectMessageEventAdmin(ImmutableRecordAdmin):
    """مرور پیام‌های نمونه و خروجی ثبت‌شدهٔ آن‌ها."""

    list_display = (
        "external_message_id",
        "connection",
        "sender_id",
        "rule",
        "created_display",
    )
    list_filter = (("created_at", JDateFieldListFilter),)
    search_fields = ("external_message_id", "sender_id", "connection__username", "text")
    list_select_related = ("rule", "connection")
    readonly_fields = (
        "external_message_id",
        "connection",
        "sender_id",
        "text",
        "rule",
        "response",
        "created_display",
    )
