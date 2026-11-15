"""تنظیمات پنل ادمین جنگو برای مدل‌های اشتراک وین فوروارد."""

from django.contrib import admin

from .models import (
    ForwardPlatformAccess,
    ForwardSubscriptionAccount,
    ForwardSubscriptionOrder,
    ForwardSubscriptionPlan,
)


@admin.register(ForwardSubscriptionPlan)
class ForwardSubscriptionPlanAdmin(admin.ModelAdmin):
    """مدیریت پلن‌های اشتراک وین فوروارد در ادمین."""

    list_display = ("name", "code", "duration_days", "price_per_platform", "is_trial", "is_active", "position")
    list_filter = ("is_trial", "is_active")
    ordering = ("position", "duration_days")


@admin.register(ForwardSubscriptionAccount)
class ForwardSubscriptionAccountAdmin(admin.ModelAdmin):
    """مدیریت حساب‌های اشتراک وین فوروارد و وضعیت دوره رایگان کاربران."""

    list_display = ("user", "trial_used_at", "first_paid_at", "created_at")
    search_fields = ("user__phone_number",)


@admin.register(ForwardPlatformAccess)
class ForwardPlatformAccessAdmin(admin.ModelAdmin):
    """مدیریت دسترسی و تاریخ انقضای پلتفرم‌های کاربران در ادمین."""

    list_display = ("user", "platform_slug", "plan", "expires_at", "is_active")
    list_filter = ("platform_slug", "is_active")
    search_fields = ("user__phone_number",)


@admin.register(ForwardSubscriptionOrder)
class ForwardSubscriptionOrderAdmin(admin.ModelAdmin):
    """مدیریت سفارش‌های اشتراک وین فوروارد در ادمین."""

    list_display = ("id", "user", "plan", "order_kind", "total_amount", "status", "paid_at", "created_at")
    list_filter = ("status", "order_kind", "plan")
    search_fields = ("user__phone_number",)
