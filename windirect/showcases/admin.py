from django.contrib import admin
from .models import Showcase
from .inline_admin import CardsInline
from windirect.common.admin import ToolAdmin


@admin.register(Showcase)
class ShowcaseAdmin(ToolAdmin):
    """مدیریت ویترین‌ها و کارت‌های وابسته."""

    inlines = (CardsInline,)
    fieldsets = (
        ("ویترین", {"fields": ("connection", "name", "is_active")}),
        (
            "تاریخچه",
            {
                "fields": ("created_display", "updated_display"),
                "classes": ("collapse",),
            },
        ),
    )
