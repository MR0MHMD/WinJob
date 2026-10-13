from django.urls import path
from . import views

urlpatterns = [
    path("accounts/", views.connections, name="connections"),
    path("accounts/<int:pk>/toggle/", views.connection_toggle, name="connection_toggle"),
    path("instagram/connect/", views.instagram_connect, name="instagram_connect"),
    path("instagram/callback/", views.instagram_callback, name="instagram_callback"),
    path("webhook/instagram/", views.instagram_webhook, name="instagram_webhook"),
    # ==================== جدید ====================
    path("posts/load/", views.instagram_posts_load, name="instagram_posts_load"),
    path("posts/status/", views.instagram_posts_status, name="instagram_posts_status"),
]
