from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_jalali.admin.filters import JDateFieldListFilter
from core.admin_utils import format_datetime, RegionalFilterAdminMixin
from .models import AdvertiserProfile
from accounts.models import CustomUser


@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = [
        'business_name',
        'user_phone_display',
        'get_user_type',
        'user_province',
        'is_verified',
        'formatted_created_at'
    ]

    list_filter = [
        'is_verified',
        'category',
        ('created_at', JDateFieldListFilter),
    ]

    search_fields = [
        'business_name',
        'user__phone_number',
        'user__nickname',
        'user__province__name',
    ]

    readonly_fields = [
        'formatted_created_at',
        'formatted_updated_at',
        'user_province_display',
    ]

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': (
                'user',
                'business_name',
                'category',
                'description',
                'website',
            )
        }),
        ('موقعیت مکانی', {
            'fields': ('user_province_display', ),
            'classes': ('collapse',)
        }),
        ('وضعیت', {
            'fields': ('is_verified',),
            'classes': ('collapse',)
        }),
        ('تاریخچه', {
            'fields': ('formatted_created_at', 'formatted_updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_phone_display(self, obj):
        """نمایش شماره تلفن کاربر"""
        return obj.user.phone_number

    def get_user_type(self, obj):
        """نوع کاربر را مشخص میکند"""
        user = obj.user

        if user.is_superuser:
            return "👑 مدیر سیستم"
        elif hasattr(user, 'advertiser_profile') and hasattr(user, 'influencer_profile'):
            return "🎯 تبلیغ‌دهنده + اینفلوئنسر"
        elif hasattr(user, 'advertiser_profile'):
            return "🏢 تبلیغ‌دهنده"
        elif hasattr(user, 'influencer_profile'):
            return "🌟 اینفلوئنسر"
        elif user.is_regional_manager:
            return "📍 مدیر استانی"

        return "👤 کاربر عادی"

    def user_province(self, obj):
        """نمایش استان کاربر در لیست"""
        return obj.user.province.name if obj.user.province else "-"

    def user_province_display(self, obj):
        """نسخه فقط خوندنی برای نمایش در فرم"""
        return obj.user.province.name if obj.user.province else "-"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    def get_queryset(self, request):
        """فقط تبلیغ‌دهندگانی که استانشون با استان مدیر یکی هست"""
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            return qs.filter(user__province=request.user.province)

        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """محدود کردن انتخاب کاربر در فرم"""
        if db_field.name == 'user' and request.user.is_regional_manager:
            kwargs['queryset'] = CustomUser.objects.filter(
                province=request.user.province,
                advertiser_profile__isnull=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """ذخیره با اعتبارسنجی استان"""
        if request.user.is_regional_manager and request.user.province:
            if obj.user.province != request.user.province:
                from django.core.exceptions import ValidationError
                raise ValidationError('شما فقط می‌توانید تبلیغ‌دهندگانی را مدیریت کنید که در استان شما هستند.')
        super().save_model(request, obj, form, change)

    user_phone_display.short_description = _('شماره تماس')
    user_phone_display.admin_order_field = _('user__phone_number')
    get_user_type.short_description = _('نوع کاربر')
    user_province.short_description = _('استان')
    user_province.admin_order_field = 'user__province__name'
    user_province_display.short_description = _('استان')
    formatted_created_at.short_description = _('تاریخ ایجاد')
    formatted_updated_at.short_description = _('تاریخ ویرایش')
