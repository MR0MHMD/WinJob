from django.urls import path
from . import webhooks, api_views

app_name = "messengers"

urlpatterns = [
    path("bale/", webhooks.bale_webhook, name="bale_webhook"),
    path("telegram/", webhooks.telegram_webhook, name="telegram_webhook"),
    path("api/connect/", api_views.api_connect_user, name="api_connect_user"),
    path("api/channels/", api_views.api_get_channels, name="api_get_channels"),
    path("api/draft/", api_views.api_create_draft, name="api_create_draft"),
    path("api/toggle/", api_views.api_toggle_target, name="api_toggle_target"),
    path("api/dispatch/", api_views.api_dispatch_job, name="api_dispatch_job"),
    path("api/bot-status/", api_views.api_bot_status, name="api_bot_status"),
    path("api/bot-channels/", api_views.api_bot_channels_list, name="api_bot_channels_list"),
    path("api/bot-channel-event/", api_views.api_bot_channel_event, name="api_bot_channel_event"),
]