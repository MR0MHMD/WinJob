from django import forms
from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

from content_team.models import ContentServicePlan
from .models import Category, Platform, Province, ContentServiceType, FAQ, AdType


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


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}
    search_fields = (
        "name",
        "slug",
    )


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]


@admin.register(ContentServiceType)
class ContentServiceTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "icon",
        "allowed_units_display",  # ← جدید
        "display_order",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
    )

    ordering = (
        "display_order",
        "name",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": (
                "name",
                "slug",
                "description",
                "icon",
            )
        }),
        ("تنظیمات واحد", {  # ← جدید
            "fields": (
                "allowed_units",
                "allowed_units_display",
            ),
            "classes": ("wide",),
            "description": "واحدهایی که این سرویس می‌تواند داشته باشد. "
                           "تیم‌های تولید محتوا فقط می‌توانند از این واحدها برای پلن‌های خود استفاده کنند."
        }),
        ("وضعیت", {
            "fields": (
                "is_active",
                "display_order",
            )
        }),
        ("تاریخ‌ها", {
            "fields": (
                "created_at",
            ),
            "classes": ("collapse",)
        }),
    )

    readonly_fields = (
        "created_at",
        "allowed_units_display",
    )

    def allowed_units_display(self, obj):
        """نمایش واحدهای مجاز به صورت خوانا"""
        return obj.get_allowed_units_display() or "همه واحدها"

    allowed_units_display.short_description = "واحدهای مجاز"

    # ========== فیلتر فرم برای انتخاب واحدهای مجاز ==========
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "allowed_units":
            # استفاده از CheckboxSelectMultiple برای انتخاب راحت‌تر
            kwargs['widget'] = forms.CheckboxSelectMultiple(
                choices=ContentServicePlan.PricingUnit.choices
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['short_question', 'title', 'order', 'is_active']
    list_display_links = ['short_question']
    list_filter = ['title__category', 'title', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['question', 'answer']
    readonly_fields = ['created_at', 'updated_at']

    def short_question(self, obj):
        return obj.question[:80] + '...' if len(obj.question) > 80 else obj.question

    short_question.short_description = _('سوال')


@admin.register(AdType)
class AdTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "platform", "slug", "is_active")
    list_filter = ("platform", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
