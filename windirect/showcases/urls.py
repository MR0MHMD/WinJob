from django.urls import path, register_converter
from . import views


class ShowcasesToolConverter:
    regex = "showcases"

    def to_python(self, value):
        return value

    def to_url(self, value):
        if value != "showcases":
            raise ValueError(value)
        return value


register_converter(ShowcasesToolConverter, "showcasestool")

urlpatterns = [
    path("tools/<showcasestool:kind>/", views.asset_list, name="asset_list"),
    path("tools/<showcasestool:kind>/new/", views.asset_edit, name="asset_create"),
    path(
        "tools/<showcasestool:kind>/<int:pk>/edit/", views.asset_edit, name="asset_edit"
    ),
    path(
        "tools/<showcasestool:kind>/<int:pk>/toggle/",
        views.asset_toggle,
        name="asset_toggle",
    ),
    path(
        "tools/<showcasestool:kind>/<int:pk>/delete/",
        views.asset_delete,
        name="asset_delete",
    ),
]
