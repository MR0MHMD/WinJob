from django.contrib import admin
from .models import Notification, NotificationPreference
from django.utils.translation import gettext_lazy as _


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'type', 'is_read', 'created_at']
    list_filter = ['type', 'is_read', 'created_at']
    search_fields = ['user__phone_number', 'title', 'message']
    readonly_fields = ['created_at', 'read_at']




@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    # ۱. مشخص کردن ستون‌های کلیدی در لیست اصلی ادمین
    list_display = (
        'get_user_phone',
        'receive_in_bale',
        'ticket_replies',
        'financial_alerts',
        'adv_campaign_status',  # وضعیت تبلیغ دهنده
        'inf_new_orders',       # وضعیت اینفلوئنسر
        'team_new_orders',      # وضعیت تیم محتوا
    )

    # ۲. فیلترهای هوشمند تفکیک شده بر اساس کانال و نقش‌ها
    list_filter = (
        'receive_in_bale',
        'ticket_replies',
        'financial_alerts',
        'adv_campaign_status',
        'inf_new_orders',
        'team_new_orders',
    )

    # ۳. قابلیت جستجو بر اساس شماره تلفن یا شناسه کاربر
    search_fields = ('user__phone_number', 'user__id', 'user__username')

    # ۴. بهینه‌سازی کوئری‌ها برای جلوگیری از باگ N+1 (افزایش سرعت لود)
    list_select_related = ('user',)

    # ۵. شیک‌سازی و دسته‌بندی فیلدها با فیلدست بر اساس نقش‌های جدید
    fieldsets = (
        (_('اطلاعات پایه کاربر'), {
            'fields': ('user',),
            'description': _('کاربری که این تنظیمات متعلق به اوست.')
        }),
        (_('⚙️ تنظیمات عمومی و بسترها'), {
            'fields': ('receive_in_bale', 'ticket_replies', 'financial_alerts', 'marketing_messages'),
        }),
        (_('🎯 اعلان‌های اختصاصی تبلیغ دهنده'), {
            'fields': ('adv_campaign_status', 'adv_influencer_actions', 'adv_content_orders'),
            'classes': ('collapse',),  # به صورت کشویی باز و بسته می‌شود
        }),
        (_('🌟 اعلان‌های اختصاصی ناشر (اینفلوئنسر)'), {
            'fields': ('inf_new_orders', 'inf_report_status'),
            'classes': ('collapse',),
        }),
        (_('🎨 اعلان‌های اختصاصی تیم تولید محتوا'), {
            'fields': ('team_new_orders', 'team_revisions', 'team_financial'),
            'classes': ('collapse',),
        }),
    )

    # ۶. نمایش ستون شماره تلفن کاربر به جای متن پیش‌فرض دیتابیس
    @admin.display(ordering='user__phone_number', description=_('شماره تماس کاربر'))
    def get_user_phone(self, obj):
        return obj.user.phone_number if obj.user.phone_number else f"User ID: {obj.user.id}"

    # ۷. اکشن‌های دسته‌جمعی برای مدیریت سریع وضعیت بله
    actions = ['enable_bale_notifications', 'disable_bale_notifications']

    @admin.action(description=_('فعال‌سازی دریافت نوتیفیکیشن بله برای انتخاب‌شده‌ها'))
    def enable_bale_notifications(self, request, queryset):
        updated = queryset.update(receive_in_bale=True)
        self.message_user(request, f'✅ تنظیمات {updated} کاربر با موفقیت بروزرسانی شد و نوتیفیکیشن بله فعال گردید.')

    @admin.action(description=_('غیرفعال‌سازی دریافت نوتیفیکیشن بله برای انتخاب‌شده‌ها'))
    def disable_bale_notifications(self, request, queryset):
        updated = queryset.update(receive_in_bale=False)
        self.message_user(request, f'❌ تنظیمات {updated} کاربر با موفقیت بروزرسانی شد و نوتیفیکیشن بله غیرفعال گردید.')
