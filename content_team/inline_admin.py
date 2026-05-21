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
        "price_per_unit",
        "estimated_delivery_days",
        "is_active",
        "formated_created_at",
    )
    readonly_fields = ("service_type",
                       "name",
                       "price_per_unit",
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
