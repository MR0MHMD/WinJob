"""مدیریت حرفه‌ای کاربران ربات در پنل ادمین."""

from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from .models import BotUser, ConnectToken
from django.contrib import admin
from django.urls import reverse

# استایل مشترک badge
_BADGE = "display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:500;"
_BADGE_SUCCESS = _BADGE + "background:#07c98b;color:#fff;"
_BADGE_DANGER = _BADGE + "background:#f23c49;color:#fff;"
_BADGE_PRIMARY = _BADGE + "background:#fd5631;color:#fff;"
_BADGE_MUTED = _BADGE + "background:#efecf3;color:#666276;"
_CODE = "background:#f5f4f8;padding:2px 6px;border-radius:4px;font-size:12px;"


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    """مدیریت اتصال کاربران سایت به ربات‌های پیام‌رسان."""

    # 🔑 اضافه شدن ستون توکن به لیست
    list_display = (
        "id", "user_link", "platform_badge", "chat_id_display",
        "api_token_status_badge", "verification_badge", "linked_at_display"
    )
    list_display_links = ("id", "user_link")
    list_filter = ("is_verified", "platform", ("linked_at", admin.DateFieldListFilter))
    search_fields = ("user__phone_number", "user__nickname", "chat_id", "username")
    autocomplete_fields = ("user", "platform")
    readonly_fields = ("linked_at", "last_seen_at", "linked_at_display", "last_seen_display", "masked_token_display")
    list_per_page = 50
    list_select_related = ("user", "platform")
    ordering = ("-linked_at",)
    actions = ("action_mark_verified", "action_mark_unverified", "action_touch_last_seen", "action_clear_token")

    # 🔑 اضافه شدن api_token به فرم ویرایش (فیلدست)
    fieldsets = (
        (_("کاربر و پلتفرم"), {"fields": ("user", "platform")}),
        (_("اطلاعات ربات"), {"fields": ("chat_id", "username")}),
        (_("توکن ایتایار / اختصاصی"), {"fields": ("api_token", "masked_token_display"), "classes": ("collapse",)}),
        (_("وضعیت"), {"fields": ("is_verified",)}),
        (_("زمان‌ها"),
         {"fields": ("linked_at", "linked_at_display", "last_seen_at", "last_seen_display"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        """بهینه‌سازی کوئری با select_related برای جلوگیری از N+1."""
        return super().get_queryset(request).select_related("user", "platform")

    @admin.display(description=_("ID"), ordering="id")
    def id_badge(self, obj):
        return format_html('<code style="{}">#{}</code>', _CODE, obj.pk)

    @admin.display(description=_("کاربر"), ordering="user__phone_number")
    def user_link(self, obj):
        url = reverse(f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    @admin.display(description=_("پلتفرم"), ordering="platform__name")
    def platform_badge(self, obj):
        return format_html('<span style="{}">{}</span>', _BADGE_PRIMARY, obj.platform.name)

    @admin.display(description=_("شناسه چت"))
    def chat_id_display(self, obj):
        return format_html('<code style="{}">{}</code>', _CODE, obj.chat_id)

    # 🔑 نمایش وضعیت توکن در لیست
    @admin.display(description=_("توکن API"), boolean=False)
    def api_token_status_badge(self, obj):
        """نشان می‌دهد توکن ذخیره شده است یا خیر."""
        if obj.api_token:
            return format_html('<span style="{}">✓ دارد</span>', _BADGE_SUCCESS)
        return format_html('<span style="{}">✗ ندارد</span>', _BADGE_DANGER)

    # 🔑 نمایش توکن ماسک شده در صفحه ویرایش
    @admin.display(description=_("پیش‌نمایش توکن (ماسک شده)"))
    def masked_token_display(self, obj):
        if not obj.api_token:
            return mark_safe('<span style="color:#9691a4;">توکنی ثبت نشده است</span>')
        masked = f"{obj.api_token[:6]}...{obj.api_token[-6:]}"
        return format_html('<code style="{}" title="{}">{}</code>', _CODE, obj.api_token, masked)

    @admin.display(description=_("وضعیت"), ordering="is_verified", boolean=False)
    def verification_badge(self, obj):
        style = _BADGE_SUCCESS if obj.is_verified else _BADGE_DANGER
        text = "✓ تأیید شده" if obj.is_verified else "✗ تأیید نشده"
        return format_html('<span style="{}">{}</span>', style, text)

    @admin.display(description=_("تاریخ اتصال"), ordering="linked_at")
    def linked_at_display(self, obj):
        return obj.linked_at.strftime("%Y/%m/%d %H:%M") if obj.linked_at else "—"

    @admin.display(description=_("آخرین فعالیت"), ordering="last_seen_at")
    def last_seen_display(self, obj):
        if not obj.last_seen_at:
            return mark_safe('<span style="color:#9691a4;">هرگز</span>')
        return obj.last_seen_at.strftime("%Y/%m/%d %H:%M")

    @admin.action(description=_("علامت‌گذاری به عنوان تأیید شده"))
    def action_mark_verified(self, request, queryset):
        n = queryset.update(is_verified=True)
        self.message_user(request, f"{n} رکورد تأیید شد.")

    @admin.action(description=_("علامت‌گذاری به عنوان تأیید نشده"))
    def action_mark_unverified(self, request, queryset):
        n = queryset.update(is_verified=False)
        self.message_user(request, f"{n} رکورد از حالت تأیید خارج شد.")

    @admin.action(description=_("بروزرسانی آخرین فعالیت به زمان حال"))
    def action_touch_last_seen(self, request, queryset):
        from django.utils import timezone
        n = queryset.update(last_seen_at=timezone.now())
        self.message_user(request, f"{n} رکورد بروزرسانی شد.")

    # 🔑 اکشن برای پاک کردن دستی توکن (برای تست)
    @admin.action(description=_("پاک کردن توکن API"))
    def action_clear_token(self, request, queryset):
        n = queryset.update(api_token=None, is_verified=False)
        self.message_user(request, f"توکن {n} رکورد پاک شد.")


@admin.register(ConnectToken)
class ConnectTokenAdmin(admin.ModelAdmin):
    """مدیریت توکن‌های اتصال (Deep Link)."""

    list_display = ("id", "user_link", "platform_badge", "token_display", "status_badge", "created_at")
    list_filter = ("platform", ("created_at", admin.DateFieldListFilter))
    search_fields = ("user__phone_number", "user__nickname", "token")
    readonly_fields = ("token", "created_at", "used_at")
    autocomplete_fields = ("user", "platform")

    @admin.display(description=_("ID"))
    def id_badge(self, obj):
        """نمایش شناسه عددی."""
        return format_html('<code style="background:#f5f4f8;padding:2px 6px;border-radius:4px;">#{}</code>', obj.pk)

    @admin.display(description=_("کاربر"))
    def user_link(self, obj):
        """لینک به پروفایل کاربر."""
        url = reverse(f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    @admin.display(description=_("پلتفرم"))
    def platform_badge(self, obj):
        """نمایش نام پلتفرم."""
        return obj.platform.name

    @admin.display(description=_("توکن"))
    def token_display(self, obj):
        """نمایش بخشی از توکن."""
        return format_html('<code>{}</code>', obj.token[:12])

    @admin.display(description=_("وضعیت"))
    def status_badge(self, obj):
        """نمایش وضعیت استفاده از توکن."""
        if obj.used_at:
            return mark_safe('<span style="color:#f23c49;">استفاده شده</span>')
        if obj.is_valid():
            return mark_safe('<span style="color:#07c98b;">معتبر (۱۰ دقیقه)</span>')
        return mark_safe('<span style="color:#fdbc31;">منقضی شده</span>')
