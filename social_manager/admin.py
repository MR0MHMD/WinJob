from django.contrib import admin

from .models import Brand, ContentDraft, SocialAccount


class SocialAccountInline(admin.TabularInline):
    model = SocialAccount
    extra = 0
    fields = ('platform', 'username', 'status', 'external_id')
    readonly_fields = ('status', 'external_id')


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'website', 'created_at')
    search_fields = ('name', 'owner__phone_number')
    list_select_related = ('owner',)
    readonly_fields = ('created_at',)
    inlines = (SocialAccountInline,)


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'platform', 'brand', 'status', 'updated_at')
    list_filter = ('platform', 'status')
    search_fields = ('username', 'external_id', 'brand__name', 'brand__owner__phone_number')
    list_select_related = ('brand',)
    readonly_fields = ('status', 'external_id', 'created_at', 'updated_at')
    fieldsets = (
        ('حساب', {'fields': ('brand', 'platform', 'username')}),
        ('اتصال', {'fields': ('status', 'external_id')}),
        ('تاریخ‌ها', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(ContentDraft)
class ContentDraftAdmin(admin.ModelAdmin):
    list_display = ('title', 'brand', 'content_format', 'status', 'planned_for', 'updated_at')
    list_filter = ('brand', 'content_format', 'status')
    search_fields = ('title', 'idea', 'caption', 'brand__name')
    list_select_related = ('brand',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('برنامه', {'fields': ('brand', 'title', 'content_format', 'objective', 'planned_for')}),
        ('محتوا', {'fields': ('idea', 'hook', 'caption', 'call_to_action', 'hashtags')}),
        ('بررسی', {'fields': ('status',)}),
        ('تاریخ‌ها', {'fields': ('created_at', 'updated_at')}),
    )
