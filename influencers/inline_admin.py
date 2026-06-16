from .models import InfluencerServiceRate, InfluencerChannel, InfluencerReview, CampaignReport
from django.utils.html import format_html
from django.contrib import admin


class InfluencerServiceRateInline(admin.TabularInline):
    fields = ("ad_type", "price", "formatted_price", "is_active", "created_at",)
    readonly_fields = ("formatted_price", "created_at",)
    autocomplete_fields = ("ad_type",)
    model = InfluencerServiceRate
    classes = ['collapse']
    extra = 0


class InfluencerChannelInline(admin.TabularInline):
    model = InfluencerChannel
    extra = 0
    readonly_fields = ("followers_formatted_display", "created_at",)
    show_change_link = True
    classes = ['collapse']
    fields = (
        "platform",
        "channel_id",
        "followers_count",
        "followers_formatted_display",
        "is_active",
        "created_at",
    )

    def followers_formatted_display(self, obj):
        return obj.followers_formatted()

    followers_formatted_display.short_description = "فالوورها"


class InfluencerReviewInline(admin.TabularInline):
    model = InfluencerReview
    fields = ("advertiser", "campaign_booking", "rating", "comment", "created_at",)
    autocomplete_fields = ("advertiser", "campaign_booking",)
    readonly_fields = ("created_at",)
    show_change_link = True
    classes = ['collapse']
    extra = 0


class CampaignReportInline(admin.StackedInline):
    """
    اینلاین برای نمایش گزارش در صفحه جزئیات CampaignInfluencer
    """
    model = CampaignReport
    extra = 0
    can_delete = False
    max_num = 1
    min_num = 0
    classes = ['collapse']

    fields = (
        "post_link",
        "screenshot_preview",
        "screenshot",
        "status",
        "admin_notes",
        "created_at",
        "updated_at",
    )

    readonly_fields = (
        "screenshot_preview",
        "created_at",
        "updated_at",
    )

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" width="150" height="auto" style="border-radius: 8px;" />'
                '</a>',
                obj.screenshot.url,
                obj.screenshot.url
            )
        return "-"

    screenshot_preview.short_description = "پیش‌نمایش اسکرین‌شات"
