from django.contrib import admin
from django_jalali.admin.filters import JDateFieldListFilter
from .models import ConversationForm, FormSubmission
from .inline_admin import QuestionsInline
from windirect.common.admin import ToolAdmin, ImmutableRecordAdmin


@admin.register(ConversationForm)
class ConversationFormAdmin(ToolAdmin):
    """مدیریت تنظیمات پرسش‌نامه و سؤال‌ها."""

    inlines = (QuestionsInline,)
    fieldsets = (
        ("فرم", {"fields": ("connection", "name", "is_active")}),
        ("مکالمه", {"fields": ("completion_text", "cancel_keyword")}),
        (
            "تاریخچه",
            {
                "fields": ("created_display", "updated_display"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(FormSubmission)
class FormSubmissionAdmin(ImmutableRecordAdmin):
    """مرور پاسخ‌نامه‌ها با تفکیک وضعیت و تاریخ."""

    list_display = ("form", "connection", "sender_id", "status", "created_display")
    list_filter = ("status", ("created_at", JDateFieldListFilter))
    search_fields = ("form__name", "connection__username", "sender_id")
    list_select_related = ("form", "connection")
    readonly_fields = (
        "form",
        "connection",
        "sender_id",
        "status",
        "schema",
        "answers",
        "created_display",
        "updated_at",
        "completed_at",
    )
