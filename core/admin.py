from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'order', 'is_active_badge', 'created_at']
    list_display_links = ['name']
    list_filter = ['is_active', 'order']
    search_fields = ['name', 'slug', 'description']
    ordering = ['order', 'name']
    list_per_page = 25

    fieldsets = (
        (_('اطلاعات اصلی'), {
            'fields': ('name', 'slug', 'description', 'icon')
        }),
        (_('تنظیمات'), {
            'fields': ('order', 'is_active')
        }),
    )

    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']

    actions = ['make_active', 'make_inactive', 'duplicate_category']

    def is_active_badge(self, obj):
        """نمایش وضعیت با بج ساده"""
        if obj.is_active:
            return mark_safe('<span style="color: green;">✓ فعال</span>')
        return mark_safe('<span style="color: red;">✗ غیرفعال</span>')

    is_active_badge.short_description = _('وضعیت')
    is_active_badge.admin_order_field = 'is_active'

    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} دسته‌بندی فعال شدند.', messages.SUCCESS)

    make_active.short_description = _('فعال کردن انتخاب‌ها')

    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} دسته‌بندی غیرفعال شدند.', messages.SUCCESS)

    make_inactive.short_description = _('غیرفعال کردن انتخاب‌ها')

    def duplicate_category(self, request, queryset):
        for category in queryset:
            Category.objects.create(
                name=f"{category.name} (کپی)",
                slug=f"{category.slug}-copy",
                description=category.description,
                icon=category.icon,
                order=category.order + 1,
                is_active=False
            )
        self.message_user(request, f'{queryset.count()} دسته‌بندی کپی شدند.', messages.SUCCESS)

    duplicate_category.short_description = _('کپی کردن انتخاب‌ها')
