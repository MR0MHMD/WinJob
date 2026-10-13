from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django_jalali.admin.filters import JDateFieldListFilter
from core.utils.admin_utils import format_datetime
from .models import InstagramConnection
from windirect.comments.inline_admin import AutomationInline


@admin.register(InstagramConnection)
class InstagramConnectionAdmin(admin.ModelAdmin):
    """مدیریت حساب‌ها و مرور قوانین وابسته در پنل ادمین."""

    list_display = (
        "id",
        "avatar_preview",
        "username",
        "owner_phone",
        "status_badge",
        "automations_count",
        "formatted_created_at",
    )
    list_filter = ("status", ("created_at", JDateFieldListFilter))
    search_fields = (
        "username",
        "instagram_user_id",
        "owner__phone_number",
        "owner__nickname",
    )
    autocomplete_fields = ("owner",)
    list_select_related = ("owner",)
    ordering = ("-created_at",)
    list_per_page = 25
    readonly_fields = (
        "avatar_preview_large",
        "formatted_created_at",
        "formatted_updated_at",
        "automations_count",
    )
    inlines = [AutomationInline]
    fieldsets = (
        (
            _("اطلاعات حساب"),
            {
                "fields": ("owner", "username", "instagram_user_id"),
            },
        ),
        (
            _("تصویر پروفایل"),
            {
                "fields": ("profile_picture", "avatar_preview_large"),
            },
        ),
        (
            _("وضعیت"),
            {
                "fields": ("status", "automations_count"),
            },
        ),
        (
            _("تاریخچه"),
            {
                "fields": ("formatted_created_at", "formatted_updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # ==================== نمایش‌های سفارشی ====================

    @admin.display(description=_("تصویر"))
    def avatar_preview(self, obj):
        """پیش‌نمایش دایره‌ای کوچک عکس پروفایل در لیست ادمین."""
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="'
                'width:40px;height:40px;'
                'border-radius:50%;'
                'object-fit:cover;'
                'box-shadow:0 2px 6px rgba(0,0,0,0.15);'
                '" />',
                obj.profile_picture.url,
            )
        # اگه عکس نداشت، حرف اول با پس‌زمینه‌ی رنگی
        initial = (obj.username or "?")[0].upper()
        return format_html(
            '<div style="'
            'width:40px;height:40px;'
            'border-radius:50%;'
            'background:linear-gradient(135deg,#07c98b,#17a2b8);'
            'color:#fff;font-weight:700;font-size:16px;'
            'display:flex;align-items:center;justify-content:center;'
            'box-shadow:0 2px 6px rgba(0,0,0,0.15);'
            '">{}</div>',
            initial,
        )

    @admin.display(description=_("پیش‌نمایش تصویر"))
    def avatar_preview_large(self, obj):
        """پیش‌نمایش بزرگ عکس پروفایل در صفحه‌ی ویرایش."""
        if not obj.pk:
            return "-"
        if obj.profile_picture:
            return format_html(
                '<div style="display:flex;align-items:center;gap:1.5rem;">'
                '<img src="{}" style="'
                'width:120px;height:120px;'
                'border-radius:50%;'
                'object-fit:cover;'
                'border:3px solid #e5e7eb;'
                'box-shadow:0 6px 20px rgba(0,0,0,0.2);'
                '" />'
                '<div style="color:#6b7280;font-size:13px;">'
                '<div style="font-weight:600;margin-bottom:4px;">@{} </div>'
                '<div>تصویر از اینستاگرام دریافت شده است.</div>'
                '</div>'
                '</div>',
                obj.profile_picture.url,
                obj.username,
            )
        return mark_safe(
            '<div style="color:#9ca3af;font-style:italic;">'
            'هنوز تصویری برای این حساب ثبت نشده است.'
            '</div>'
        )

    @admin.display(description=_("شماره مالک"), ordering="owner__phone_number")
    def owner_phone(self, obj):
        """شماره مالک حساب را نشان می‌دهد."""
        return obj.owner.phone_number

    @admin.display(description=_("وضعیت اتصال"), ordering="status")
    def status_badge(self, obj):
        """وضعیت اتصال را با رنگ مناسب نمایش می‌دهد."""
        colors = {
            "simulated": "#2563eb",
            "connected": "#15803d",
            "disconnected": "#b91c1c",
        }
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colors.get(obj.status, "#52525b"),
            obj.get_status_display(),
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