# advertisers/admin.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_jalali.admin.filters import JDateFieldListFilter

from core.admin_utils import format_datetime
from .models import AdvertiserProfile


@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):

    list_display = [
        'business_name',
        'user',
        'get_user_type',
        'province',
        'city',
        'is_verified',
        'formatted_created_at'
    ]

    list_filter = [
        'is_verified',
        'province',
        'category',
        ('created_at', JDateFieldListFilter)
    ]

    search_fields = [
        'business_name',
        'user__phone_number',
        'user__nickname',
        'province',
        'city'
    ]

    readonly_fields = ['formatted_created_at', 'formatted_updated_at']

    # ✅ سینک شده با مدل بدون user_type
    def get_user_type(self, obj):

        user = obj.user

        if hasattr(user, 'advertiser_profile'):
            return "🏢 تبلیغ‌دهنده"

        elif hasattr(user, 'influencer_profile'):
            return "🌟 اینفلوئنسر"

        elif user.is_superuser:
            return "👑 مدیر سیستم"

        return "-"

    get_user_type.short_description = 'نوع کاربر'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'
    formatted_updated_at.short_description = 'تاریخ ویرایش'
