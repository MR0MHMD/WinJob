from django.urls import path, register_converter
from . import views


class DirectToolConverter:
    regex = "direct"

    def to_python(self, value):
        return value

    def to_url(self, value):
        if value != "direct":
            raise ValueError(value)
        return value


register_converter(DirectToolConverter, "directtool")

urlpatterns = [
    path("direct/test/", views.direct_simulation, name="direct_simulation"),
    path("direct/logs/", views.direct_logs, name="direct_logs"),
    path("tools/<directtool:kind>/", views.asset_list, name="asset_list"),
    path("tools/<directtool:kind>/new/", views.asset_edit, name="asset_create"),
    path("tools/<directtool:kind>/<int:pk>/edit/", views.asset_edit, name="asset_edit"),
    path(
        "tools/<directtool:kind>/<int:pk>/toggle/",
        views.asset_toggle,
        name="asset_toggle",
    ),
    path(
        "tools/<directtool:kind>/<int:pk>/delete/",
        views.asset_delete,
        name="asset_delete",
    ),
]
