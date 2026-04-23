# core/admin_utils.py
from django.utils import timezone
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


def format_datetime(dt):
    """
    فرمت مرکزی برای تاریخ و زمان
    """
    try:
        if dt:
            # تبدیل به زمان محلی
            local_dt = timezone.localtime(dt)
            return local_dt.strftime('%Y/%m/%d | %H:%M')
        return "-"
    except:
        return "نامشخص"


def format_date_only(dt):
    """
    تابع کمکی برای نمایش فقط تاریخ
    """
    try:
        if dt:
            # تبدیل به زمان محلی
            local_dt = timezone.localtime(dt)
            return local_dt.strftime('%Y/%m/%d')
        return "-"
    except:
        return "نامشخص"


def format_time_only(dt):
    """
    تابع کمکی برای نمایش فقط زمان
    """
    if not dt:
        return "-"

    try:
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        return dt.strftime('%H:%M:%S')
    except (AttributeError, ValueError, TypeError):
        return "-"


class RegionalFilterAdminMixin:
    """
    میکسین برای محدود کردن دسترسی مدیران استانی
    با فرض اینکه استان در CustomUser.province است
    """

    def get_queryset(self, request):
        """فقط آیتم‌هایی که کاربرشون در استان مدیر استانی هست"""
        qs = super().get_queryset(request)

        # اگه کاربر مدیر استانی هست
        if request.user.is_regional_manager and request.user.province:
            # برای مدل‌هایی که فیلد user دارند (مثل AdvertiserProfile)
            if hasattr(qs.model, 'user'):
                return qs.filter(user__province=request.user.province)

        return qs

    def has_change_permission(self, request, obj=None):
        """بررسی دسترسی ویرایش"""
        if obj and request.user.is_regional_manager and request.user.province:
            # سعی کن user آبجکت رو پیدا کنی
            user = self._get_user_from_obj(obj)
            if user and user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """بررسی دسترسی حذف"""
        if obj and request.user.is_regional_manager and request.user.province:
            user = self._get_user_from_obj(obj)
            if user and user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """محدود کردن انتخاب‌ها در فرم"""
        # برای فیلدهایی که به CustomUser اشاره دارن
        if db_field.name == 'user' and request.user.is_regional_manager:
            kwargs['queryset'] = CustomUser.objects.filter(
                province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def _get_user_from_obj(self, obj):
        """دریافت user از آبجکت‌های مختلف"""
        if hasattr(obj, 'user'):
            return obj.user
        elif hasattr(obj, 'advertiser') and hasattr(obj.advertiser, 'user'):
            return obj.advertiser.user
        elif hasattr(obj, 'influencer') and hasattr(obj.influencer, 'user'):
            return obj.influencer.user
        return None
