"""مسیرهای URL اپ broadcast."""

from django.urls import path
from . import views

app_name = "broadcast"

urlpatterns = [
    path("send/", views.send_broadcast, name="send"),
    path("jobs/", views.JobListView.as_view(), name="job_list"),
    path("job/<int:job_id>/", views.job_detail, name="job_detail"),

    # Eitaa web panel
    path("eitaa/connect/", views.eitaa_connect_token, name="eitaa_connect_token"),
    path("eitaa/channels/", views.eitaa_channels, name="eitaa_channels"),
    path("eitaa/channels/add/", views.eitaa_add_channel, name="eitaa_add_channel"),
    path("eitaa/channels/<int:channel_id>/delete/", views.eitaa_delete_channel, name="eitaa_delete_channel"),

    # Rubika web panel
    path("rubika/connect/", views.rubika_connect_phone, name="rubika_connect_phone"),
    path("rubika/verify/", views.rubika_verify_code, name="rubika_verify_code"),
    path("rubika/channels/", views.rubika_channels, name="rubika_channels"),
    path("rubika/channels/add/", views.rubika_add_channel, name="rubika_add_channel"),
    path("rubika/channels/sync/", views.rubika_sync_channels, name="rubika_sync_channels"),
    path("rubika/channels/<int:channel_id>/delete/", views.rubika_delete_channel, name="rubika_delete_channel"),

    # Soroush Plus web panel
    path("soroush/connect/", views.soroush_connect_phone, name="soroush_connect_phone"),
    path("soroush/verify/", views.soroush_verify_code, name="soroush_verify_code"),
    path("soroush/channels/", views.soroush_channels, name="soroush_channels"),
    path("soroush/channels/add/", views.soroush_add_channel, name="soroush_add_channel"),
    path("soroush/channels/sync/", views.soroush_sync_channels, name="soroush_sync_channels"),
    path("soroush/channels/<int:channel_id>/delete/", views.soroush_delete_channel, name="soroush_delete_channel"),
]