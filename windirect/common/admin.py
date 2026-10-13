from django.contrib import admin
from django_jalali.admin.filters import JDateFieldListFilter
from core.utils.admin_utils import format_datetime


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


class ToolAdmin(admin.ModelAdmin):
    """نمای مشترک ابزارها با جست‌وجو، فیلتر و تاریخ شمسی."""

    list_display = ("name", "connection", "is_active", "created_display")
    list_filter = ("is_active", ("created_at", JDateFieldListFilter))
    search_fields = ("name", "connection__username", "connection__owner__phone_number")
    autocomplete_fields = ("connection",)
    list_select_related = ("connection",)
    readonly_fields = ("created_display", "updated_display")
    list_per_page = 25

    @admin.display(description="تاریخ ایجاد", ordering="created_at")
    def created_display(self, obj):
        """تاریخ ایجاد را با قالب مشترک ادمین نمایش می‌دهد."""
        return format_datetime(obj.created_at) if obj.pk else "—"

    @admin.display(description="آخرین ویرایش", ordering="updated_at")
    def updated_display(self, obj):
        """تاریخ ویرایش را با قالب مشترک ادمین نمایش می‌دهد."""
        return format_datetime(obj.updated_at) if obj.pk else "—"

    def get_readonly_fields(self, request, obj=None):
        """از انتقال ابزار دارای سابقه به حساب دیگری جلوگیری می‌کند."""
        return self.readonly_fields + (("connection",) if obj else ())


class ImmutableRecordAdmin(admin.ModelAdmin):
    """سوابق را فقط برای مشاهده، جست‌وجو و بررسی نمایش می‌دهد."""

    list_per_page = 25

    def has_add_permission(self, request):
        """ثبت دستی سوابق مجاز نیست."""
        return False

    def has_change_permission(self, request, obj=None):
        """تغییر دستی سابقه مجاز نیست."""
        return False

    def has_delete_permission(self, request, obj=None):
        """حذف سابقه از ادمین مجاز نیست."""
        return False

    @admin.display(description="تاریخ ثبت", ordering="created_at")
    def created_display(self, obj):
        """زمان ثبت را با قالب مشترک نمایش می‌دهد."""
        return format_datetime(obj.created_at)
