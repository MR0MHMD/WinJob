"""مسیرهای URL اپ broadcast."""

from django.urls import path
from . import views

app_name = "broadcast"

urlpatterns = [
    path("", views.forward_dashboard, name="dashboard"),
    path("send/", views.send_broadcast, name="send"),
    path("channels/", views.connected_channels, name="connected_channels"),
    path("jobs/", views.JobListView.as_view(), name="job_list"),
    path("job/<int:job_id>/", views.job_detail, name="job_detail"),
    path("r/<str:slug>/", views.public_job_detail, name="public_job_detail"),

    # Broadcast Hubs (هاب‌های ارسال گروهی)
    path("hubs/", views.hub_list, name="hub_list"),
    path("hubs/<int:hub_id>/edit/", views.hub_edit, name="hub_edit"),
    path("hubs/<int:hub_id>/delete/", views.hub_delete, name="hub_delete"),

    # Channel Presets
    path("presets/", views.preset_list, name="preset_list"),
    path("presets/<int:preset_id>/edit/", views.preset_edit, name="preset_edit"),
    path("presets/<int:preset_id>/delete/", views.preset_delete, name="preset_delete"),

    # Telegram web panel
    path("telegram/connect/", views.telegram_connect, name="telegram_connect"),
    path("telegram/channels/", views.telegram_channels, name="telegram_channels"),
    path("telegram/channels/sync-avatars/", views.telegram_sync_avatars, name="telegram_sync_avatars"),
    path("telegram/channels/<int:channel_id>/delete/", views.telegram_delete_channel, name="telegram_delete_channel"),

    # Bale web panel
    path("bale/connect/", views.bale_connect, name="bale_connect"),
    path("bale/channels/", views.bale_channels, name="bale_channels"),
    path("bale/channels/sync-avatars/", views.bale_sync_avatars, name="bale_sync_avatars"),
    path("bale/channels/<int:channel_id>/delete/", views.bale_delete_channel, name="bale_delete_channel"),

    # Eitaa web panel
    path("eitaa/connect/", views.eitaa_connect_token, name="eitaa_connect_token"),
    path("eitaa/channels/", views.eitaa_channels, name="eitaa_channels"),
    path("eitaa/channels/add/", views.eitaa_add_channel, name="eitaa_add_channel"),
    path("eitaa/channels/<int:channel_id>/delete/", views.eitaa_delete_channel, name="eitaa_delete_channel"),

    # Rubika web panel
    path("rubika/connect/", views.rubika_connect_phone, name="rubika_connect_phone"),
    path("rubika/verify/", views.rubika_verify_code, name="rubika_verify_code"),
    path("rubika/channels/", views.rubika_channels, name="rubika_channels"),
    path("rubika/channels/sync/", views.rubika_sync_channels, name="rubika_sync_channels"),
    path("rubika/channels/<int:channel_id>/delete/", views.rubika_delete_channel, name="rubika_delete_channel"),

    # Soroush+ web panel
    path("soroush/connect/", views.soroush_connect_phone, name="soroush_connect_phone"),
    path("soroush/verify/", views.soroush_verify_code, name="soroush_verify_code"),
    path("soroush/channels/", views.soroush_channels, name="soroush_channels"),
    path("soroush/channels/sync/", views.soroush_sync_channels, name="soroush_sync_channels"),
    path("soroush/channels/<int:channel_id>/delete/", views.soroush_delete_channel, name="soroush_delete_channel"),
    path("soroush/logout/", views.soroush_logout, name="soroush_logout"),

]