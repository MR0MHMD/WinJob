"""مسیرهای URL اپ messengers."""

from django.urls import path
from . import webhooks

app_name = "messengers"

urlpatterns = [
    path("bale/", webhooks.bale_webhook, name="bale_webhook"),
]