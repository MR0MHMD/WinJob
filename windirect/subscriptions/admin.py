"""مدیریت پلن‌ها و نمایش سوابق مالی و دسترسی اشتراک."""

from django.contrib import admin
from django_jalali.admin.filters import JDateFieldListFilter
from core.utils.admin_utils import format_datetime
from ..models import (
    SubscriptionPlan,
    SubscriptionOffer,
    SubscriptionAccount,
    SubscriptionOrder,
    UserSubscription,
    ReferralCode,
    ReferralRedemption,
    SubscriptionGift,
)


class OfferInline(admin.TabularInline):
    """قیمت سه دوره را در صفحهٔ پلن قابل مدیریت می‌کند."""

    model = SubscriptionOffer
    extra = 0
    fields = ("duration_days", "price", "is_active")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """مدیریت امکانات، سقف پیج و عرضهٔ پلن."""

    list_display = (
        "name",
        "code",
        "level",
        "is_trial",
        "max_pages",
        "is_active",
        "is_featured",
    )
    list_filter = ("is_active", "is_trial", "forms", "showcases")
    search_fields = ("name", "code")
    prepopulated_fields = {"code": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = (OfferInline,)
    fieldsets = (
        (
            "اطلاعات پلن",
            {"fields": ("name", "code", "description", "level", "is_trial")},
        ),
        (
            "امکانات",
            {
                "fields": (
                    "smart_comments",
                    "smart_direct",
                    "showcases",
                    "forms",
                    "max_pages",
                )
            },
        ),
        ("عرضه", {"fields": ("is_active", "is_featured", "position")}),
        ("تاریخچه", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(SubscriptionOffer)
class SubscriptionOfferAdmin(admin.ModelAdmin):
    """مدیریت قیمت دوره‌های پلن؛ قیمت صفر فقط برای دورهٔ رایگان فعال است."""

    list_display = ("plan", "duration_days", "price", "is_active")
    list_filter = ("is_active", "duration_days", "plan")
    search_fields = ("plan__name", "plan__code")
    autocomplete_fields = ("plan",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    """تخصیص کد معرف به یک کاربر و کنترل فعال بودن آن."""

    list_display = ("code", "owner", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "owner__phone_number", "owner__nickname")
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at",)

    def get_readonly_fields(self, request, obj=None):
        """مالک و متن کد مصرف‌شده را ثابت نگه می‌دارد."""
        if obj and (obj.redemptions.exists() or obj.subscriptionorder_set.exists()):
            return self.readonly_fields + ("code", "owner")
        return self.readonly_fields


class SubscriptionRecordAdmin(admin.ModelAdmin):
    """سوابق پرداخت، هدیه و بازه‌ها توسط سرویس ثبت می‌شوند؛ ادمین فقط مشاهده می‌کند."""

    list_per_page = 25

    def has_add_permission(self, request):
        """ایجاد دستی سابقه مجاز نیست."""
        return False

    def has_change_permission(self, request, obj=None):
        """ویرایش دستی سابقه مجاز نیست."""
        return False

    def has_delete_permission(self, request, obj=None):
        """حذف سابقه مجاز نیست."""
        return False

    @admin.display(description="تاریخ ثبت", ordering="created_at")
    def registered_at(self, obj):
        """تاریخ را با قالب ادمین پروژه نمایش می‌دهد."""
        return format_datetime(obj.created_at)


@admin.register(SubscriptionAccount)
class SubscriptionAccountAdmin(SubscriptionRecordAdmin):
    """نمایش وضعیت مصرف رایگان، خرید اول و روزهای ذخیره‌شده."""

    list_display = (
        "user",
        "trial_used_at",
        "first_paid_at",
        "highest_level",
        "banked_gift_days",
    )
    search_fields = ("user__phone_number",)
    list_select_related = ("user",)


@admin.register(SubscriptionOrder)
class SubscriptionOrderAdmin(SubscriptionRecordAdmin):
    """نمایش سفارش‌ها و قیمت قطعی آن‌ها."""

    list_display = ("id", "user", "offer", "kind", "status", "registered_at")
    list_filter = ("kind", "status", ("created_at", JDateFieldListFilter))
    search_fields = ("user__phone_number", "offer__plan__name")
    list_select_related = ("user", "offer__plan")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(SubscriptionRecordAdmin):
    """نمایش بازه‌ها و نسخهٔ امکانات هر خرید."""

    list_display = (
        "account",
        "plan_name",
        "kind",
        "starts_at",
        "ends_at",
        "is_superseded",
    )
    list_filter = ("kind", "is_superseded", ("ends_at", JDateFieldListFilter))
    search_fields = ("account__user__phone_number", "plan_name")
    list_select_related = ("account__user",)


@admin.register(ReferralRedemption)
class ReferralRedemptionAdmin(SubscriptionRecordAdmin):
    """مرور معرفی‌های موفق و پاداش ثبت‌شده."""

    list_display = (
        "buyer",
        "referral",
        "order",
        "buyer_days",
        "owner_days",
        "registered_at",
    )
    search_fields = ("buyer__phone_number", "referral__code")
    list_select_related = ("buyer", "referral", "order")


@admin.register(SubscriptionGift)
class SubscriptionGiftAdmin(SubscriptionRecordAdmin):
    """پیگیری تخصیص روزهای هدیه به دوره یا ذخیره برای خرید بعدی."""

    list_display = ("account", "days", "period", "registered_at")
    search_fields = ("account__user__phone_number", "redemption__referral__code")
    list_select_related = ("account__user", "period")
