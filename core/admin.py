from django import forms
from django.contrib import admin
from django.utils.html import mark_safe, format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.db.models import Count
from django.contrib import admin
from content_team.models import ContentServicePlan
from .models import Category, Platform, Province, ContentServiceType, FAQ, AdType, ContentType, Bank, City


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
    """مدیریت حرفه‌ای پلتفرم‌های وین‌جاب."""

    list_display = ("id", "name", "slug", "logo_thumbnail", "is_active", "is_forward_active", "bot_users_count")
    list_filter = ("is_active", "is_forward_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("logo_preview",)
    list_per_page = 30
    actions = ("action_activate_forward", "action_deactivate_forward", "action_activate_platform", "action_deactivate_platform")
    fieldsets = (
        (_("اطلاعات پایه"), {"fields": ("name", "slug", "description")}),
        (_("برندینگ"), {"fields": ("logo", "logo_preview")}),
        (_("وضعیت"), {"fields": ("is_active", "is_forward_active")}),
    )

    def get_queryset(self, request):
        """بهینه‌سازی با annotate تعداد BotUserهای هر پلتفرم."""
        return super().get_queryset(request).annotate(_bot_users_count=Count("bot_users"))

    @admin.display(description=_("لوگو"))
    def logo_thumbnail(self, obj):
        """نمایش بندانگشتی لوگو."""
        if not obj.logo:
            return mark_safe('<span style="color:#9691a4;">—</span>')
        return format_html('<img src="{}" style="height:32px;width:32px;border-radius:6px;object-fit:cover;" />', obj.logo.url)

    @admin.display(description=_("ربات کاربران"), ordering="_bot_users_count")
    def bot_users_count(self, obj):
        """نمایش تعداد کاربران ربات متصل به این پلتفرم."""
        if obj._bot_users_count == 0:
            return mark_safe('<span style="color:#9691a4;">0</span>')
        return format_html('<strong>{}</strong>', obj._bot_users_count)

    @admin.display(description=_("پیش نمایش لوگو"))
    def logo_preview(self, obj):
        """پیش‌نمایش بزرگ‌تر لوگو در صفحه ویرایش."""
        if not obj.logo:
            return "—"
        return format_html('<img src="{}" style="max-height:120px;border-radius:8px;" />', obj.logo.url)

    @admin.action(description=_("فعال سازی وین فوروارد"))
    def action_activate_forward(self, request, queryset):
        """فعال‌سازی پلتفرم‌های انتخاب‌شده برای وین فوروارد."""
        n = queryset.update(is_forward_active=True)
        self.message_user(request, f"{n} پلتفرم برای وین فوروارد فعال شد.")

    @admin.action(description=_("غیرفعال سازی وین فوروارد"))
    def action_deactivate_forward(self, request, queryset):
        """غیرفعال‌سازی پلتفرم‌های انتخاب‌شده برای وین فوروارد."""
        n = queryset.update(is_forward_active=False)
        self.message_user(request, f"{n} پلتفرم از وین فوروارد غیرفعال شد.")

    @admin.action(description=_("فعال سازی پلتفرم"))
    def action_activate_platform(self, request, queryset):
        """فعال‌سازی کلی پلتفرم‌های انتخاب‌شده."""
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} پلتفرم فعال شد.")

    @admin.action(description=_("غیر فعال سازی پلتفرم"))
    def action_deactivate_platform(self, request, queryset):
        """غیرفعال‌سازی کلی پلتفرم‌های انتخاب‌شده."""
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} پلتفرم غیرفعال شد.")


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "slug")
    list_filter = ("province",)
    search_fields = ("name", "slug")
    autocomplete_fields = ("province",)
    list_per_page = 30


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


@admin.register(ContentType)
class ContentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        'logo_preview',
        'name',
        'code',
        'slug',
        'is_active',
        'order',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'slug')
    ordering = ('order', 'name')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('logo_preview_large',)

    fieldsets = (
        (None, {
            'fields': (
                'name',
                'slug',
                'code',
            )
        }),
        (_('لوگو'), {
            'fields': (
                'logo',
                'logo_preview_large',
            )
        }),
        (_('تنظیمات نمایش'), {
            'fields': (
                'is_active',
                'order',
            )
        }),
    )

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="height: 32px; width: auto; border-radius: 4px;" />',
                obj.logo.url
            )
        return "—"
    logo_preview.short_description = _('لوگو')

    def logo_preview_large(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height: 120px; width: auto; border-radius: 8px;" />',
                obj.logo.url
            )
        return _('لوگویی آپلود نشده')
    logo_preview_large.short_description = _('پیش‌نمایش لوگو')
