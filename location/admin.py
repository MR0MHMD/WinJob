from django.contrib import admin
from .models import Province, City


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]



@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'province', 'slug')
    list_filter = ('province',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}