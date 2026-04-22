from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import *


class ContentServiceRateInline(admin.TabularInline):
    model = ContentServiceRate
    extra = 0
    fields = (
        "service_type",
        "price_per_unit",
        "estimated_delivery_days",
        "is_available",
        "created_at",
    )
    readonly_fields = ("created_at",)
    classes = ['collapse']


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
    """
    بریف سفارش - به صورت Stacked نمایش داده می‌شه
    چون فیلدهای زیادی داره و TabularInline خوانا نیست
    """
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
    """
    فایل‌های پیوست سفارش
    """
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
