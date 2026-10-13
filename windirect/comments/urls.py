from django.urls import path
from . import views

urlpatterns = [
    path("rules/", views.rules, name="rules"),
    path("rules/new/", views.rule_create, name="rule_create"),
    path("rules/<int:pk>/edit/", views.rule_edit, name="rule_edit"),
    path("rules/<int:pk>/toggle/", views.rule_toggle, name="rule_toggle"),
    path("rules/<int:pk>/delete/", views.rule_delete, name="rule_delete"),
    path("test/", views.simulation, name="simulation"),
    path("logs/", views.logs, name="logs"),
    path("upload-media/", views.upload_media, name="upload_media"),
]
