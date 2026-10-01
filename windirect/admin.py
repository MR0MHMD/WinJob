from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_jalali.admin.filters import JDateFieldListFilter

from core.utils.admin_utils import format_datetime
from .models import Automation, AutomationExecution, CommentEvent, InstagramConnection


class AutomationInline(admin.TabularInline):
    """قوانین یک حساب را در صفحهٔ همان حساب نمایش می‌دهد."""

    model = Automation
    extra = 0
    show_change_link = True
    classes = ["collapse"]
    fields = ("name", "media_id", "keyword", "match_type", "is_active")


class ExecutionInline(admin.TabularInline):
    """آخرین اجراهای یک قانون را بدون امکان دست‌کاری نمایش می‌دهد."""

    model = AutomationExecution
    extra = 0
    show_change_link = True
    can_delete = False
    classes = ["collapse"]
    fields = ("event", "status", "response_text", "formatted_created_at")
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
    fields = ("automation", "status", "response_text")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        """از ثبت دستی اجرای قانون جلوگیری می‌کند."""
        return False


class ReadOnlyLogAdmin(admin.ModelAdmin):
    """لاگ‌ها را برای بررسی نگه می‌دارد و ویرایش دستی را می‌بندد."""

    def has_add_permission(self, request):
        """لاگ باید توسط سرویس ساخته شود."""
        return False

    def has_change_permission(self, request, obj=None):
        """لاگ پس از ثبت قابل تغییر نیست."""
        return False

    def has_delete_permission(self, request, obj=None):
        """از حذف دستی سابقهٔ اجرا جلوگیری می‌کند."""
        return False


@admin.register(InstagramConnection)
class InstagramConnectionAdmin(admin.ModelAdmin):
    """مدیریت حساب‌ها و مرور قوانین وابسته در پنل ادمین."""

    list_display = (
        "username", "owner_phone", "status_badge", "automations_count",
        "formatted_created_at",
    )
    list_filter = ("status", ("created_at", JDateFieldListFilter))
    search_fields = ("username", "instagram_user_id", "owner__phone_number", "owner__nickname")
    autocomplete_fields = ("owner",)
    list_select_related = ("owner",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = ("formatted_created_at", "formatted_updated_at", "automations_count")
    inlines = [AutomationInline]
    fieldsets = (
        (_("اطلاعات حساب"), {
            "fields": ("owner", "username", "instagram_user_id"),
        }),
        (_("وضعیت"), {
            "fields": ("status", "automations_count"),
        }),
        (_("تاریخچه"), {
            "fields": ("formatted_created_at", "formatted_updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("شماره مالک"), ordering="owner__phone_number")
    def owner_phone(self, obj):
        """شماره مالک حساب را نشان می‌دهد."""
        return obj.owner.phone_number

    @admin.display(description=_("وضعیت اتصال"), ordering="status")
    def status_badge(self, obj):
        """وضعیت اتصال را با رنگ مناسب نمایش می‌دهد."""
        colors = {"simulated": "#2563eb", "connected": "#15803d", "disconnected": "#b91c1c"}
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colors.get(obj.status, "#52525b"), obj.get_status_display(),
        )

    @admin.display(description=_("تعداد قوانین"))
    def automations_count(self, obj):
        """تعداد قوانین ثبت‌شده برای حساب را نمایش می‌دهد."""
        return obj.automations.count() if obj.pk else 0

    @admin.display(description=_("تاریخ ایجاد"), ordering="created_at")
    def formatted_created_at(self, obj):
        """تاریخ ایجاد را با قالب رایج پنل نمایش می‌دهد."""
        return format_datetime(obj.created_at) if obj.pk else "-"

    @admin.display(description=_("آخرین ویرایش"), ordering="updated_at")
    def formatted_updated_at(self, obj):
        """تاریخ آخرین ویرایش را نمایش می‌دهد."""
        return format_datetime(obj.updated_at) if obj.pk else "-"


@admin.register(Automation)
class AutomationAdmin(admin.ModelAdmin):
    """قوانین وین دایرکت را همراه با سابقهٔ اجرا مدیریت می‌کند."""

    list_display = (
        "name", "connection", "media_display", "keyword", "match_type",
        "is_active", "executions_count", "formatted_created_at",
    )
    list_filter = ("is_active", "match_type", ("created_at", JDateFieldListFilter))
    search_fields = ("name", "keyword", "media_id", "connection__username", "connection__owner__phone_number")
    autocomplete_fields = ("connection",)
    list_select_related = ("connection",)
    list_editable = ("is_active",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = ("formatted_created_at", "formatted_updated_at", "executions_count")
    inlines = [ExecutionInline]
    fieldsets = (
        (_("اطلاعات قانون"), {
            "fields": ("connection", "name", "media_id"),
        }),
        (_("شرط و پاسخ"), {
            "fields": ("keyword", "match_type", "reply_text"),
        }),
        (_("وضعیت"), {
            "fields": ("is_active", "executions_count"),
        }),
        (_("تاریخچه"), {
            "fields": ("formatted_created_at", "formatted_updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("پست"), ordering="media_id")
    def media_display(self, obj):
        """دامنهٔ اعمال قانون را در فهرست مشخص می‌کند."""
        return obj.media_id or _("همهٔ پست‌ها")

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


@admin.register(CommentEvent)
class CommentEventAdmin(ReadOnlyLogAdmin):
    """کامنت‌های دریافت‌شده و نتیجهٔ قوانین آن‌ها را نمایش می‌دهد."""

    list_display = ("external_comment_id", "connection", "media_id", "executions_count", "formatted_created_at")
    list_filter = (("created_at", JDateFieldListFilter),)
    search_fields = ("external_comment_id", "media_id", "text", "connection__username")
    list_select_related = ("connection",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = ("connection", "external_comment_id", "media_id", "text", "formatted_created_at")
    inlines = [EventExecutionInline]
    fieldsets = (
        (_("اطلاعات کامنت"), {
            "fields": ("connection", "external_comment_id", "media_id", "text"),
        }),
        (_("تاریخچه"), {
            "fields": ("formatted_created_at",),
            "classes": ("collapse",),
        }),
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
    """جزئیات خروجی هر قانون را برای پیگیری نمایش می‌دهد."""

    list_display = ("automation", "event", "status_badge", "formatted_created_at")
    list_filter = ("status", ("created_at", JDateFieldListFilter))
    search_fields = ("automation__name", "event__external_comment_id", "response_text")
    list_select_related = ("automation", "event")
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = ("automation", "event", "status", "response_text", "formatted_created_at")
    fieldsets = (
        (_("نتیجهٔ اجرا"), {
            "fields": ("automation", "event", "status", "response_text"),
        }),
        (_("تاریخچه"), {
            "fields": ("formatted_created_at",),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("وضعیت اجرا"), ordering="status")
    def status_badge(self, obj):
        """نتیجهٔ اجرا را با رنگ مناسب نمایش می‌دهد."""
        colors = {"simulated": "#2563eb", "sent": "#15803d", "failed": "#b91c1c"}
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colors.get(obj.status, "#52525b"), obj.get_status_display(),
        )

    @admin.display(description=_("تاریخ اجرا"), ordering="created_at")
    def formatted_created_at(self, obj):
        """زمان اجرای قانون را با قالب پنل نمایش می‌دهد."""
        return format_datetime(obj.created_at)

# ثبت ادمین ابزارهای جدید در همان اپ وین دایرکت.
from . import features_admin  # noqa: E402,F401

from .subscriptions import admin as subscription_admin  # noqa: E402,F401
