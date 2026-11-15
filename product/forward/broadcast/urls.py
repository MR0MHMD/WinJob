"""مسیرهای URL اپ broadcast."""

from django.urls import path
from . import views

app_name = "broadcast"

urlpatterns = [
    path("", views.forward_dashboard, name="dashboard"),
    path("send/", views.send_broadcast, name="send"),
    path("jobs/", views.JobListView.as_view(), name="job_list"),
    path("job/<int:job_id>/", views.job_detail, name="job_detail"),

    # Bale web panel
    path("bale/connect/", views.bale_connect, name="bale_connect"),
    path("bale/channels/", views.bale_channels, name="bale_channels"),
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
    path("rubika/channels/add/", views.rubika_add_channel, name="rubika_add_channel"),
    path("rubika/channels/sync/", views.rubika_sync_channels, name="rubika_sync_channels"),
    path("rubika/channels/<int:channel_id>/delete/", views.rubika_delete_channel, name="rubika_delete_channel"),

]