from django.contrib import admin
from .models import CampaignChannel, CampaignClick


class CampaignChannelInline(admin.TabularInline):
    model = CampaignChannel
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
