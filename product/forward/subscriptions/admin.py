"""پنل ادمین سیستم توکنی وین فوروارد — ویرایش مستقیم موجودی توکن هر کاربر + نرخ‌ها + تراکنش‌ها."""

from django.contrib import admin
from django.db import transaction

from .models import (
    ForwardSubscriptionAccount,
    ForwardSubscriptionOrder,
    ForwardSubscriptionPlan,
    ForwardTokenPricing,
    ForwardTokenTransaction,
)
from .services import credit_tokens_atomic


@admin.register(ForwardSubscriptionPlan)
class ForwardSubscriptionPlanAdmin(admin.ModelAdmin):
    """مدیریت بسته‌های فروش توکن در پنل ادمین."""

    list_display = ("name", "code", "tokens_amount", "price_per_platform", "discount_percent", "is_trial", "is_featured", "is_active", "position")
    list_editable = ("tokens_amount", "price_per_platform", "discount_percent", "is_featured", "is_active", "position")
    list_filter = ("is_trial", "is_active", "is_featured")
    search_fields = ("name", "code")
    ordering = ("position", "tokens_amount")


@admin.register(ForwardSubscriptionAccount)
class ForwardSubscriptionAccountAdmin(admin.ModelAdmin):
    """مدیریت کیف توکن کاربران — امکان افزایش یا کاهش مستقیم توکن هر کاربر با ثبت خودکار سند."""

    list_display = ("user", "token_balance", "total_tokens_earned", "total_tokens_spent", "trial_used_at", "first_paid_at")
    search_fields = ("user__phone_number", "user__nickname", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    actions = ("action_add_500_tokens", "action_add_2000_tokens", "action_reset_balance")

    def save_model(self, request, obj, form, change):
        """ثبت خودکار تراکنش admin_adjust در صورت تغییر دستی موجودی توکن کاربر توسط مدیر."""
        old_balance = 0
        if change and obj.pk:
            prev = ForwardSubscriptionAccount.objects.filter(pk=obj.pk).only("token_balance").first()
            if prev:
                old_balance = int(prev.token_balance)
        new_balance = int(obj.token_balance or 0)
        delta = new_balance - old_balance
        if delta > 0:
            obj.total_tokens_earned = int(obj.total_tokens_earned or 0) + delta
        super().save_model(request, obj, form, change)
        if delta != 0:
            ForwardTokenTransaction.objects.create(
                user=obj.user,
                tx_type=ForwardTokenTransaction.TxType.ADMIN_ADJUST,
                amount=delta,
                balance_after=obj.token_balance,
                description=f"ویرایش دستی توسط ادمین ({request.user})",
            )

    @admin.action(description="🎁 افزودن ۵۰۰ توکن هدیه به کاربران انتخاب‌شده")
    def action_add_500_tokens(self, request, queryset):
        for acc in queryset.select_related("user"):
            credit_tokens_atomic(
                acc.user,
                500,
                ForwardTokenTransaction.TxType.ADMIN_ADJUST,
                description=f"هدیه ۵۰۰ توکنی توسط ادمین ({request.user})",
            )
        self.message_user(request, f"۵۰۰ توکن به {queryset.count()} کاربر اضافه شد.")

    @admin.action(description="🎁 افزودن ۲,۰۰۰ توکن هدیه به کاربران انتخاب‌شده")
    def action_add_2000_tokens(self, request, queryset):
        for acc in queryset.select_related("user"):
            credit_tokens_atomic(
                acc.user,
                2000,
                ForwardTokenTransaction.TxType.ADMIN_ADJUST,
                description=f"هدیه ۲,۰۰۰ توکنی توسط ادمین ({request.user})",
            )
        self.message_user(request, f"۲,۰۰۰ توکن به {queryset.count()} کاربر اضافه شد.")

    @admin.action(description="🔄 صفر کردن موجودی توکن کاربران انتخاب‌شده")
    @transaction.atomic
    def action_reset_balance(self, request, queryset):
        for acc in queryset.select_related("user").select_for_update():
            old_b = int(acc.token_balance)
            if old_b > 0:
                acc.token_balance = 0
                acc.save(update_fields=["token_balance"])
                ForwardTokenTransaction.objects.create(
                    user=acc.user,
                    tx_type=ForwardTokenTransaction.TxType.ADMIN_ADJUST,
                    amount=-old_b,
                    balance_after=0,
                    description=f"صفر کردن موجودی توسط ادمین ({request.user})",
                )
        self.message_user(request, "موجودی کاربران انتخاب‌شده صفر شد.")


@admin.register(ForwardTokenPricing)
class ForwardTokenPricingAdmin(admin.ModelAdmin):
    """ویرایش نرخ مصرف توکن هر نوع پیام، حجم فایل، هاب و هوش مصنوعی."""

    list_display = (
        "text_cost",
        "photo_cost",
        "caption_extra_cost",
        "sticker_gif_cost",
        "media_under_5mb_cost",
        "media_5_to_10mb_cost",
        "media_10_to_20mb_cost",
        "hub_extra_cost",
        "ai_watermark_extra_cost",
        "free_gift_tokens",
        "max_file_size_mb",
    )


@admin.register(ForwardTokenTransaction)
class ForwardTokenTransactionAdmin(admin.ModelAdmin):
    """دفترکل کامل تراکنش‌های توکن کاربران."""

    list_display = ("id", "user", "tx_type", "amount", "balance_after", "broadcast_job_id", "description", "created_at")
    list_filter = ("tx_type", "created_at")
    search_fields = ("user__phone_number", "user__nickname", "description")
    readonly_fields = ("user", "tx_type", "amount", "balance_after", "description", "broadcast_job_id", "created_at")


@admin.register(ForwardSubscriptionOrder)
class ForwardSubscriptionOrderAdmin(admin.ModelAdmin):
    """مدیریت سفارش‌های خرید بسته‌های توکن."""

    list_display = ("id", "user", "plan", "tokens_amount", "total_amount", "status", "paid_at", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("user__phone_number", "user__nickname")
    readonly_fields = ("created_at", "paid_at")
