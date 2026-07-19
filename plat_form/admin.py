from django.contrib import admin
from .models import Platform


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}
    search_fields = (
        "name",
        "slug",
    )
