from django.urls import path, register_converter
from . import views


class FormsToolConverter:
    regex = "forms"

    def to_python(self, value):
        return value

    def to_url(self, value):
        if value != "forms":
            raise ValueError(value)
        return value


register_converter(FormsToolConverter, "formstool")

urlpatterns = [
    path("forms/<int:pk>/responses/", views.submissions, name="submissions"),
    path("forms/<int:pk>/export/", views.export_submissions, name="export_submissions"),
    path("responses/<int:pk>/", views.submission_detail, name="submission_detail"),
    path("tools/<formstool:kind>/", views.asset_list, name="asset_list"),
    path("tools/<formstool:kind>/new/", views.asset_edit, name="asset_create"),
    path("tools/<formstool:kind>/<int:pk>/edit/", views.asset_edit, name="asset_edit"),
    path(
        "tools/<formstool:kind>/<int:pk>/toggle/",
        views.asset_toggle,
        name="asset_toggle",
    ),
    path(
        "tools/<formstool:kind>/<int:pk>/delete/",
        views.asset_delete,
        name="asset_delete",
    ),
]
