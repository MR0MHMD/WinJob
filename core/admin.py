# core/admin.py
from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count
from django.contrib import messages
from django.utils import timezone
from .models import Category


class CategoryLevelFilter(admin.SimpleListFilter):
    """
    فیلتر سفارشی برای سطح دسته‌بندی
    """
    title = _('سطح دسته‌بندی')
    parameter_name = 'level'

    def lookups(self, request, model_admin):
        return (
            ('root', _('ریشه (سطح ۰)')),
            ('level1', _('سطح ۱')),
            ('level2', _('سطح ۲')),
            ('level3', _('سطح ۳+')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'root':
            return queryset.filter(parent__isnull=True)
        elif self.value() == 'level1':
            return queryset.filter(parent__isnull=False, parent__parent__isnull=True)
        elif self.value() == 'level2':
            return queryset.filter(parent__parent__isnull=False, parent__parent__parent__isnull=True)
        elif self.value() == 'level3':
            return queryset.filter(parent__parent__parent__isnull=False)
        return queryset


class HasChildrenFilter(admin.SimpleListFilter):
    """
    فیلتر سفارشی برای دسته‌بندی‌های دارای زیرمجموعه
    """
    title = _('دارای زیرمجموعه')
    parameter_name = 'has_children'

    def lookups(self, request, model_admin):
        return (
            ('yes', _('دارد')),
            ('no', _('ندارد')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(child_count=Count('children')).filter(child_count__gt=0)
        elif self.value() == 'no':
            return queryset.annotate(child_count=Count('children')).filter(child_count=0)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    ادمین پیشرفته برای دسته‌بندی‌های سلسله‌مراتبی
    """

    # ==================== تنظیمات اصلی ====================
    list_display = [
        'tree_display',
        'slug',
        'parent_link',
        'children_count',
        'is_active_badge',
        'order',
        'created_at_formatted',
    ]

    list_display_links = ['tree_display']

    list_filter = [
        'is_active',
        CategoryLevelFilter,
        HasChildrenFilter,
        'parent',
    ]

    search_fields = [
        'name',
        'slug',
        'description',
        'icon',
    ]

    ordering = ['order', 'name']

    list_per_page = 50

    list_select_related = ['parent']

    # ==================== فیلدهای فرم ====================
    fieldsets = (
        (_('اطلاعات اصلی'), {
            'fields': ('name', 'slug', 'parent', 'description'),
            'classes': ('wide',),
        }),
        (_('تنظیمات نمایش'), {
            'fields': ('icon', 'order'),
            'classes': ('collapse',),
        }),
        (_('وضعیت'), {
            'fields': ('is_active',),
            'classes': ('collapse',),
        }),
        (_('اطلاعات سیستمی'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse', 'wide'),
        }),
    )

    readonly_fields = ['created_at', 'updated_at', 'hierarchy_info']

    prepopulated_fields = {'slug': ('name',)}

    autocomplete_fields = ['parent']

    # ==================== اکشن‌های سفارشی ====================
    actions = [
        'activate_categories',
        'deactivate_categories',
        'make_root_categories',
        'duplicate_categories',
    ]

    # ==================== متدهای نمایش لیست ====================

    def tree_display(self, obj):
        """
        نمایش درختواره دسته‌بندی
        """
        level = obj.get_level()
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * level

        # آیکون بر اساس سطح
        if level == 0:
            icon = "🌳"  # ریشه
        elif obj.is_leaf():
            icon = "🍃"  # برگ
        else:
            icon = "🌿"  # شاخه

        # آیکون دسته‌بندی
        category_icon = f"<i class='{obj.icon}'></i>" if obj.icon else "📁"

        # وضعیت فعال/غیرفعال
        status = "✅" if obj.is_active else "❌"

        # ساخت HTML
        html = f"""
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="color: #666;">{indent}</span>
            <span style="font-size: 16px;">{icon}</span>
            <span style="font-size: 14px;">{category_icon}</span>
            <strong>{obj.name}</strong>
            <span style="font-size: 12px; color: #888;">{status}</span>
        </div>
        """
        return mark_safe(html)

    tree_display.short_description = _('نام دسته‌بندی')
    tree_display.admin_order_field = 'name'

    def parent_link(self, obj):
        """
        نمایش لینک به والد
        """
        if obj.parent:
            url = reverse('admin:core_category_change', args=[obj.parent.id])
            return mark_safe(f'<a href="{url}">{obj.parent.name}</a>')
        return mark_safe('<span style="color: #4CAF50; font-weight: bold;">🏁 ریشه</span>')

    parent_link.short_description = _('والد')
    parent_link.admin_order_field = 'parent__name'

    def children_count(self, obj):
        """
        نمایش تعداد زیرمجموعه‌ها
        """
        count = obj.get_children_count()
        if count > 0:
            url = reverse('admin:core_category_changelist') + f'?parent__id__exact={obj.id}'
            return mark_safe(f'<a href="{url}" style="color: #2196F3;">{count} زیرمجموعه</a>')
        return mark_safe('<span style="color: #9E9E9E;">بدون زیرمجموعه</span>')

    children_count.short_description = _('زیرمجموعه‌ها')

    def is_active_badge(self, obj):
        """
        نمایش وضعیت فعال/غیرفعال با بج
        """
        if obj.is_active:
            return mark_safe(
                '<span style="background-color: #4CAF50; color: white; padding: 3px 8px; '
                'border-radius: 12px; font-size: 12px;">فعال</span>'
            )
        else:
            return mark_safe(
                '<span style="background-color: #F44336; color: white; padding: 3px 8px; '
                'border-radius: 12px; font-size: 12px;">غیرفعال</span>'
            )

    is_active_badge.short_description = _('وضعیت')
    is_active_badge.admin_order_field = 'is_active'

    def created_at_formatted(self, obj):
        """
        نمایش تاریخ ایجاد با فرمت زیبا
        """
        if obj.created_at:
            local_time = timezone.localtime(obj.created_at)
            date_str = local_time.strftime('%Y/%m/%d')
            time_str = local_time.strftime('%H:%M')
            return mark_safe(f"""
                <div style="text-align: center;">
                    <div style="font-weight: bold; color: #333;">{date_str}</div>
                    <div style="font-size: 11px; color: #666;">{time_str}</div>
                </div>
            """)
        return "-"

    created_at_formatted.short_description = _('تاریخ ایجاد')
    created_at_formatted.admin_order_field = 'created_at'

    # ==================== متدهای فرم ====================

    def hierarchy_info(self, obj):
        """
        نمایش اطلاعات سلسله‌مراتبی در فرم
        """
        if obj.pk:
            info = [f"<strong>سطح:</strong> {obj.get_level()}", f"<strong>مسیر کامل:</strong> {obj.get_full_path()}",
                    f"<strong>تعداد زیرمجموعه:</strong> {obj.get_children_count()}",
                    f"<strong>نوع:</strong> {'ریشه' if obj.is_root() else 'برگ' if obj.is_leaf() else 'شاخه'}"]

            return mark_safe("<br>".join(info))
        return "پس از ذخیره‌سازی نمایش داده می‌شود"

    hierarchy_info.short_description = _('اطلاعات سلسله‌مراتبی')

    # ==================== اکشن‌های سفارشی ====================

    def activate_categories(self, request, queryset):
        """
        فعال کردن دسته‌بندی‌های انتخاب شده
        """
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} دسته‌بندی با موفقیت فعال شدند.',
            messages.SUCCESS
        )

    activate_categories.short_description = _('فعال کردن دسته‌بندی‌های انتخاب شده')

    def deactivate_categories(self, request, queryset):
        """
        غیرفعال کردن دسته‌بندی‌های انتخاب شده
        """
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} دسته‌بندی با موفقیت غیرفعال شدند.',
            messages.SUCCESS
        )

    deactivate_categories.short_description = _('غیرفعال کردن دسته‌بندی‌های انتخاب شده')

    def make_root_categories(self, request, queryset):
        """
        تبدیل دسته‌بندی‌ها به ریشه (حذف والد)
        """
        updated = queryset.update(parent=None)
        self.message_user(
            request,
            f'{updated} دسته‌بندی به ریشه تبدیل شدند.',
            messages.SUCCESS
        )

    make_root_categories.short_description = _('تبدیل به ریشه (حذف والد)')

    def duplicate_categories(self, request, queryset):
        """
        کپی کردن دسته‌بندی‌های انتخاب شده
        """
        for category in queryset:
            # ایجاد کپی
            new_category = Category.objects.create(
                name=f"{category.name} (کپی)",
                slug=f"{category.slug}-copy-{timezone.now().timestamp()}",
                description=category.description,
                icon=category.icon,
                parent=category.parent,
                order=category.order + 1,
                is_active=category.is_active,
            )

        self.message_user(
            request,
            f'{queryset.count()} دسته‌بندی با موفقیت کپی شدند.',
            messages.SUCCESS
        )

    duplicate_categories.short_description = _('کپی کردن دسته‌بندی‌ها')

    # ==================== متدهای کمکی ====================

    def get_queryset(self, request):
        """
        بهینه‌سازی کوئری‌ست با prefetch_related
        """
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related('children')
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        محدود کردن انتخاب والد به دسته‌بندی‌های غیر از خودش
        """
        if db_field.name == "parent":
            # جلوگیری از انتخاب خود به عنوان والد
            if 'object_id' in request.resolver_match.kwargs:
                obj_id = request.resolver_match.kwargs['object_id']
                kwargs["queryset"] = Category.objects.exclude(id=obj_id)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        اعتبارسنجی اضافی قبل از ذخیره
        """
        # جلوگیری از ایجاد حلقه
        if obj.parent and obj.parent == obj:
            from django.core.exceptions import ValidationError
            raise ValidationError('یک دسته‌بندی نمی‌تواند والد خودش باشد.')

        super().save_model(request, obj, form, change)

    # ==================== تغییرات ظاهری ====================

    class Media:
        css = {
            'all': (
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
            )
        }

    def changelist_view(self, request, extra_context=None):
        """
        اضافه کردن اطلاعات آماری به صفحه لیست
        """
        extra_context = extra_context or {}

        # آمار کلی
        total_categories = Category.objects.count()
        active_categories = Category.objects.filter(is_active=True).count()
        root_categories = Category.objects.filter(parent__isnull=True).count()

        extra_context['stats'] = {
            'total': total_categories,
            'active': active_categories,
            'root': root_categories,
            'inactive': total_categories - active_categories,
        }

        return super().changelist_view(request, extra_context=extra_context)
