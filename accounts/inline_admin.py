from django.utils.translation import gettext_lazy as _
from advertisers.models import AdvertiserProfile
from influencers.models import InfluencerProfile
from core.admin_utils import format_datetime
from django.contrib import admin
from .models import Transaction


class AdvertiserProfileInline(admin.StackedInline):
    model = AdvertiserProfile
    can_delete = False
    verbose_name = _('پروفایل تبلیغ‌دهنده')
    verbose_name_plural = _('اطلاعات تبلیغ‌دهنده')
    fields = [
        'business_name',
        'category',
        'description',
        'website',
        'is_verified',
        'formatted_created_at',
        'formatted_updated_at'
    ]
    readonly_fields = ['formatted_created_at', 'formatted_updated_at']
    extra = 0
    max_num = 1
    classes = ['collapse']

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_created_at.short_description = "تاریخ ایجاد"
    formatted_updated_at.short_description = "تاریخ ویرایش"


class InfluencerProfileInline(admin.StackedInline):
    model = InfluencerProfile
    can_delete = False
    verbose_name = _('پروفایل اینفلوئنسر')
    verbose_name_plural = _('اطلاعات اینفلوئنسر')

    fields = [
        'full_name',
        'description',
        'is_active',
        'formatted_created_at',
        'formatted_updated_at'
    ]

    readonly_fields = [
        'formatted_created_at',
        'formatted_updated_at'
    ]

    extra = 0
    max_num = 1
    classes = ['collapse']

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_created_at.short_description = "تاریخ ایجاد"
    formatted_updated_at.short_description = "تاریخ ویرایش"


class TransactionInline(admin.TabularInline):
    """نمایش تراکنش‌های کاربر در صفحه ادمین"""
    model = Transaction
    extra = 0
    can_delete = False
    max_num = 5
    fields = ('amount', 'type', 'status', 'sign_display', 'formatted_created_at')
    readonly_fields = ('amount', 'type', 'status', 'sign_display', 'formatted_created_at')
    classes = ['collapse']

    def sign_display(self, obj):
        return obj.sign_display

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    sign_display.short_description = "مبلغ"
    formatted_created_at.short_description = "تاریخ"
