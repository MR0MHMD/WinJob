from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from core.admin_utils import format_datetime
from .models import *


class ContentServicePlanInline(admin.TabularInline):
    """
    اینلاین پلن‌های خدمات - جایگزین ContentServiceRateInline
    """
    model = ContentServicePlan
    extra = 0
    fields = (
        "service_type",
        "name",
        "pricing_unit",           # ← جدید (جایگزین price_per_unit)
        "base_quantity",          # ← جدید
        "price",                  # ← جدید (جایگزین price_per_unit)
        "delivery_type",          # ← جدید
        "estimated_delivery_days",
        "is_active",
        "formated_created_at",
    )
    readonly_fields = (
        "service_type",
        "name",
        "pricing_unit",           # ← جدید
        "base_quantity",          # ← جدید
        "price",                  # ← جدید
        "delivery_type",          # ← جدید
        "estimated_delivery_days",
        "is_active",
        "formated_created_at",
    )
    classes = ['collapse']

    def formated_created_at(self, obj):
        return format_datetime(obj.created_at)

    formated_created_at.short_description = _("تاریخ ایجاد")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('service_type')


class TeamReviewInline(admin.TabularInline):
    model = TeamReview
    extra = 0
    readonly_fields = (
        "advertiser",
        "rating",
        "comment",
        "created_at",
    )
    can_delete = False
    classes = ['collapse']


class ContentTeamMemberInline(admin.TabularInline):
    model = ContentTeamMember
    extra = 0
    fields = [
        'user',
        'role',
        'is_active',
        'revenue_share_percent'
    ]
    classes = ['collapse']


class ContentOrderDescriptionInline(admin.StackedInline):
    model = ContentOrderDescription
    extra = 0
    can_delete = False
    max_num = 1

    fieldsets = (
        ("هدف و لحن", {
            "fields": (
                "goal",
                "goal_description",
                "tone",
            )
        }),
        ("اطلاعات برند", {
            "fields": (
                "brand_name",
                "hashtags",
            )
        }),
        ("محتوا", {
            "fields": (
                "target_audience",
                "description",
                "do_not_include",
            )
        }),
        ("مراجع", {
            "fields": (
                "reference_links",
            ),
            "classes": ("collapse",)
        }),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    classes = ['collapse']


class ContentOrderFileInline(admin.TabularInline):
    model = ContentOrderFile
    extra = 0
    can_delete = True

    fields = (
        "file",
        "file_type",
        "original_name",
        "description",
        "file_size_display",
        "uploaded_at",
    )

    readonly_fields = (
        "original_name",
        "file_size_display",
        "uploaded_at",
    )
    classes = ['collapse']


class ContentPortfolioInline(admin.TabularInline):
    model = ContentPortfolio
    extra = 0
    fields = (
        "title",
        "media_preview",
        "service_type",
        "display_order",
        "is_active",
    )
    readonly_fields = ("media_preview",)

    def media_preview(self, obj):
        if obj.media:
            return format_html('<img src="{}" style="width: 40px; height: 40px; object-fit: cover;" />', obj.media.url)
        return "-"

    media_preview.short_description = _("پیش‌نمایش")

    classes = ['collapse']


class ContentDeliveryFileInline(admin.TabularInline):
    """فایل‌های یک تحویل"""
    model = ContentDeliveryFile
    extra = 0
    fields = (
        "file",
        "file_name",
        "file_size_display",
        "is_option",
        "option_number",
        "created_at",
    )
    readonly_fields = (
        "file_name",
        "file_size_display",
        "created_at",
    )
    classes = ['collapse']

    def file_size_display(self, obj):
        return obj.file_size_display

    file_size_display.short_description = _("حجم فایل")
