from .models import CampaignClick, CampaignReport
from django.utils.html import format_html
from django.contrib import admin


class CampaignClickInline(admin.TabularInline):
    model = CampaignClick
    extra = 0
    readonly_fields = (
        "ip_address",
        "user_agent",
        "created_at",
    )
    can_delete = False
    ordering = ("-created_at",)

    class CampaignReportInline(admin.StackedInline):
        """
        اینلاین برای نمایش گزارش در صفحه جزئیات ChannelBooking
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


class CampaignReportInline(admin.StackedInline):
    """
    اینلاین برای نمایش گزارش در صفحه جزئیات ChannelBooking
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
