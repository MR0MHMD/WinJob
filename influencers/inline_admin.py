from .models import ChannelServiceRate, Channel, ChannelReview, ChannelBooking
from django.contrib import admin


class ChannelServiceRateInline(admin.TabularInline):
    fields = ("ad_type", "price", "formatted_price", "is_active", "created_at",)
    readonly_fields = ("formatted_price", "created_at",)
    autocomplete_fields = ("ad_type",)
    model = ChannelServiceRate
    classes = ['collapse']
    extra = 0


class ChannelInline(admin.TabularInline):
    model = Channel
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


class ChannelReviewInline(admin.TabularInline):
    model = ChannelReview
    fields = ("advertiser", "campaign_booking", "rating", "comment", "created_at",)
    autocomplete_fields = ("advertiser", "campaign_booking",)
    readonly_fields = ("created_at",)
    show_change_link = True
    classes = ['collapse']
    extra = 0


class ChannelBookingInline(admin.TabularInline):
    model = ChannelBooking
    extra = 0
    autocomplete_fields = ("channel", "service_rate")
    can_delete = False
    fields = (
        "channel",
        "service_rate",
        "price",
        "status",
        "created_at",
    )
    readonly_fields = ("created_at",)
