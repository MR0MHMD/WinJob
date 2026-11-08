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
]