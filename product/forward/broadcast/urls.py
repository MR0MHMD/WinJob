"""مسیرهای URL اپ broadcast."""

from django.urls import path
from . import views

app_name = "broadcast"

urlpatterns = [
    path("send/", views.send_broadcast, name="send"),
    path("jobs/", views.JobListView.as_view(), name="job_list"),
    path("job/<int:job_id>/", views.job_detail, name="job_detail"),
]
