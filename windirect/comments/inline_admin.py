from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from core.utils.admin_utils import format_datetime
from .models import (
    Automation,
    AutomationExecution,
    AutomationKeyword,
    CommentReplyTemplate,
)


class AutomationInline(admin.TabularInline):
    """قوانین یک حساب را در صفحهٔ همان حساب نمایش می‌دهد."""

    model = Automation
    extra = 0
    show_change_link = True
    classes = ["collapse"]
    fields = ("name", "target_type", "reply_channel", "match_type", "is_active")
    verbose_name = _("کامنت هوشمند")
    verbose_name_plural = _("کامنت‌های هوشمند")


class KeywordInline(admin.TabularInline):
    """فعال‌سازهای یک کامنت هوشمند."""

    model = AutomationKeyword
    extra = 1
    max_num = 3
    fields = ("value",)
    verbose_name = _("فعال‌ساز")
    verbose_name_plural = _("فعال‌سازها (حداکثر ۳ تا)")


class CommentReplyInline(admin.TabularInline):
    """متن‌های پاسخ کامنت (ضد اسپم)."""

    model = CommentReplyTemplate
    extra = 1
    max_num = 3
    fields = ("text",)
    verbose_name = _("متن پاسخ کامنت")
    verbose_name_plural = _("متن‌های پاسخ کامنت (حداکثر ۳ تا)")


class ExecutionInline(admin.TabularInline):
    """آخرین اجراهای یک قانون را بدون امکان دست‌کاری نمایش می‌دهد."""

    model = AutomationExecution
    extra = 0
    show_change_link = True
    can_delete = False
    classes = ["collapse"]
    fields = ("event", "status", "formatted_created_at")
    readonly_fields = fields
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        """اجرای قانون فقط باید توسط سرویس ثبت شود."""
        return False

    @admin.display(description=_("تاریخ اجرا"))
    def formatted_created_at(self, obj):
        """تاریخ اجرا را با قالب رایج پنل نمایش می‌دهد."""
        return format_datetime(obj.created_at) if obj.pk else "-"


class EventExecutionInline(admin.TabularInline):
    """قوانین اجراشده برای یک کامنت را نشان می‌دهد."""

    model = AutomationExecution
    extra = 0
    show_change_link = True
    can_delete = False
    classes = ["collapse"]
    fields = ("automation", "status")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        """از ثبت دستی اجرای قانون جلوگیری می‌کند."""
        return False