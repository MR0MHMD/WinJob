from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import AdvertiserScore, ChannelScore, TeamScore, PointLog, Badge
from core.admin_utils import format_datetime


class BaseScoreAdmin(admin.ModelAdmin):
    list_display = ('get_owner_name', 'points', 'display_badge', 'formatted_updated_at')
    list_filter = ('badge', 'highest_badge')
    search_fields = ('points',)
    readonly_fields = ('formatted_updated_at',)

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین بروزرسانی"
    formatted_updated_at.admin_order_field = "updated_at"

    def display_badge(self, obj):
        if obj.badge:
            url = reverse('admin:gamification_badge_change', args=[obj.badge.id])
            return mark_safe(f'<a href="{url}"><img width="30" src="{obj.badge.icon.url}" alt="{obj.badge.name}"></a>')
        return '-'
    display_badge.short_description = 'نشان فعلی'

@admin.register(AdvertiserScore)
class AdvertiserScoreAdmin(BaseScoreAdmin):
    def get_owner_name(self, obj):
        return obj.profile.business_name or obj.profile.user.nickname
    get_owner_name.short_description = 'تبلیغ‌دهنده'

    list_display = ('get_owner_name', 'points', 'display_badge', 'updated_at')


@admin.register(ChannelScore)
class ChannelScoreAdmin(BaseScoreAdmin):
    def get_owner_name(self, obj):
        return obj.channel.channel_name
    get_owner_name.short_description = 'نام کانال'


@admin.register(TeamScore)
class TeamScoreAdmin(BaseScoreAdmin):
    def get_owner_name(self, obj):
        return obj.team.name
    get_owner_name.short_description = 'نام تیم'


@admin.register(PointLog)
class PointLogAdmin(admin.ModelAdmin):
    list_display = ('score_profile', 'points_changed', 'action_key', 'formatted_created_at')
    list_filter = ('action_key', 'created_at')
    search_fields = ('description', 'action_key')
    readonly_fields = (
        'formatted_created_at', 'content_type', 'object_id', 'score_profile',
        'points_changed', 'action_key', 'description'
    )

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ثبت"
    formatted_created_at.admin_order_field = "created_at"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("id", 'display_icon', 'slug', 'name', 'min_points', 'order', 'is_active',)
    list_filter = ('is_active', 'order')
    search_fields = ('name', 'slug', 'description')
    ordering = ('order', 'min_points')
    actions = ['make_inactive']
    list_per_page = 25

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('slug', 'name', 'min_points', 'order', 'is_active')
        }),
        ('تصویر و توضیحات', {
            'fields': ('icon', 'description'),
            'classes': ('wide',),
        }),
    )

    def display_icon(self, obj):
        if obj.icon:
            return format_html(
                '<img src="{}" width="32" height="32" style="border-radius: 50%; object-fit: cover;" />',
                obj.icon.url
            )
        return mark_safe(
            '<div style="width:32px; height:32px; background:#eee; border-radius:50%; text-align:center; line-height:32px;">-</div>'
        )
    display_icon.short_description = 'آیکون'

    @admin.action(description='غیرفعال کردن سطوح انتخاب شده')
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} سطح غیرفعال شدند.')
