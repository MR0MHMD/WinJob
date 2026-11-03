"""مدیریت حرفه‌ای کاربران ربات در پنل ادمین."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from .models import BotUser

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

    list_display = (
        "id_badge", "user_link", "platform_badge", "chat_id_display", "username_display", "verification_badge",
        "linked_at_display", "last_seen_display"
    )
    list_display_links = ("id_badge", "user_link")
    list_filter = ("is_verified", "platform", ("linked_at", admin.DateFieldListFilter))
    search_fields = ("user__phone_number", "user__nickname", "chat_id", "username")
    autocomplete_fields = ("user", "platform")
    readonly_fields = ("linked_at", "last_seen_at", "linked_at_display", "last_seen_display")
    list_per_page = 50
    list_select_related = ("user", "platform")
    ordering = ("-linked_at",)
    actions = ("action_mark_verified", "action_mark_unverified", "action_touch_last_seen")
    fieldsets = (
        (_("کاربر و پلتفرم"), {"fields": ("user", "platform")}),
        (_("اطلاعات ربات"), {"fields": ("chat_id", "username")}),
        (_("وضعیت"), {"fields": ("is_verified",)}),
        (_("زمان‌ها"),
         {"fields": ("linked_at", "linked_at_display", "last_seen_at", "last_seen_display"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        """بهینه‌سازی کوئری با select_related برای جلوگیری از N+1."""
        return super().get_queryset(request).select_related("user", "platform")

    @admin.display(description=_("ID"), ordering="id")
    def id_badge(self, obj):
        """نمایش شناسه عددی با فونت یکنواخت."""
        return format_html('<code style="{}">#{}</code>', _CODE, obj.pk)

    @admin.display(description=_("کاربر"), ordering="user__phone_number")
    def user_link(self, obj):
        """لینک به صفحه ویرایش کاربر در ادمین."""
        url = reverse(f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    @admin.display(description=_("پلتفرم"), ordering="platform__name")
    def platform_badge(self, obj):
        """نمایش نام پلتفرم به صورت نشان رنگی."""
        return format_html('<span style="{}">{}</span>', _BADGE_PRIMARY, obj.platform.name)

    @admin.display(description=_("شناسه چت"))
    def chat_id_display(self, obj):
        """نمایش chat_id با فونت یکنواخت."""
        return format_html('<code style="{}">{}</code>', _CODE, obj.chat_id)

    @admin.display(description=_("نام کاربری"))
    def username_display(self, obj):
        """نمایش نام کاربری با @ در صورت وجود."""
        return f"@{obj.username}" if obj.username else "—"

    @admin.display(description=_("وضعیت"), ordering="is_verified", boolean=False)
    def verification_badge(self, obj):
        """نمایش نشان تأیید/عدم تأیید با رنگ مناسب."""
        style = _BADGE_SUCCESS if obj.is_verified else _BADGE_DANGER
        text = "✓ تأیید شده" if obj.is_verified else "✗ تأیید نشده"
        return format_html('<span style="{}">{}</span>', style, text)

    @admin.display(description=_("تاریخ اتصال"), ordering="linked_at")
    def linked_at_display(self, obj):
        """نمایش تاریخ اتصال به فرمت خوانا."""
        return obj.linked_at.strftime("%Y/%m/%d %H:%M") if obj.linked_at else "—"

    @admin.display(description=_("آخرین فعالیت"), ordering="last_seen_at")
    def last_seen_display(self, obj):
        """نمایش آخرین فعالیت یا «هرگز»."""
        if not obj.last_seen_at:
            return mark_safe('<span style="color:#9691a4;">هرگز</span>')
        return obj.last_seen_at.strftime("%Y/%m/%d %H:%M")

    @admin.action(description=_("علامت‌گذاری به عنوان تأیید شده"))
    def action_mark_verified(self, request, queryset):
        """تأیید گروهی رکوردهای انتخاب‌شده."""
        n = queryset.update(is_verified=True)
        self.message_user(request, f"{n} رکورد تأیید شد.")

    @admin.action(description=_("علامت‌گذاری به عنوان تأیید نشده"))
    def action_mark_unverified(self, request, queryset):
        """لغو تأیید گروهی رکوردهای انتخاب‌شده."""
        n = queryset.update(is_verified=False)
        self.message_user(request, f"{n} رکورد از حالت تأیید خارج شد.")

    @admin.action(description=_("بروزرسانی آخرین فعالیت به زمان حال"))
    def action_touch_last_seen(self, request, queryset):
        """بروزرسانی گروهی last_seen_at به زمان جاری."""
        from django.utils import timezone
        n = queryset.update(last_seen_at=timezone.now())
        self.message_user(request, f"{n} رکورد بروزرسانی شد.")
