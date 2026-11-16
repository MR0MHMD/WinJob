"""مدیریت حرفه‌ای مدل‌های وین فوروارد در پنل ادمین."""

import uuid
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from .models import BroadcastChannel, BroadcastMessage, BroadcastJob, BroadcastTarget, ChannelPreset

# ============ استایل‌های مشترک ============
_BADGE = "display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:500;"
_BADGE_SUCCESS = _BADGE + "background:#07c98b;color:#fff;"
_BADGE_DANGER = _BADGE + "background:#f23c49;color:#fff;"
_BADGE_WARNING = _BADGE + "background:#fdbc31;color:#fff;"
_BADGE_INFO = _BADGE + "background:#3c76f2;color:#fff;"
_BADGE_PRIMARY = _BADGE + "background:#fd5631;color:#fff;"
_BADGE_MUTED = _BADGE + "background:#efecf3;color:#666276;"
_CODE = "background:#f5f4f8;padding:2px 6px;border-radius:4px;font-size:12px;"


# ============================================================
# BroadcastChannel
# ============================================================

@admin.register(BroadcastChannel)
class BroadcastChannelAdmin(admin.ModelAdmin):
    """مدیریت کانال‌های ثبت‌شده در وین فوروارد."""

    list_display = (
    "id_badge", "avatar_preview", "title_link", "user_link", "platform_badge", "chat_id_display", "bot_admin_badge", "active_badge",
    "last_broadcast_display")
    list_display_links = ("id_badge", "title_link")
    list_filter = ("platform", "bot_is_admin", "is_active", ("created_at", admin.DateFieldListFilter))
    search_fields = ("title", "chat_id", "username", "user__phone_number", "user__nickname")
    autocomplete_fields = ("user", "platform")
    readonly_fields = (
    "bot_admin_checked_at", "verification_token", "verification_token_created_at", "verification_token_used_at",
    "token_status_display", "last_broadcast_at", "created_at", "updated_at")
    list_per_page = 50
    list_select_related = ("user", "platform")
    save_on_top = True
    ordering = ("-created_at",)
    actions = ("action_generate_token", "action_mark_bot_admin", "action_mark_bot_not_admin", "action_activate",
               "action_deactivate")
    fieldsets = (
        (_("مالکیت"), {"fields": ("user", "platform")}),
        (_("اطلاعات کانال"), {"fields": ("title", "username", "chat_id", "avatar")}),
        (_("وضعیت ربات"), {"fields": ("bot_is_admin", "bot_admin_checked_at", "last_broadcast_at")}),
        (_("تأیید مالکیت (Deep Link)"), {"fields": (
        "verification_token", "token_status_display", "verification_token_created_at", "verification_token_used_at"),
                                         "classes": ("collapse",)}),
        (_("وضعیت"), {"fields": ("is_active",)}),
        (_("زمان‌ها"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        """بهینه‌سازی کوئری با select_related."""
        return super().get_queryset(request).select_related("user", "platform")


    @admin.display(description=_("عکس"))
    def avatar_preview(self, obj):
        """نمایش تصویر کوچک پروفایل کانال در لیست ادمین."""
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:28px;height:28px;border-radius:50%;object-fit:cover;" />',
                obj.avatar.url,
            )
        return mark_safe('<span style="color:#9691a4;">—</span>')

    @admin.display(description=_("ID"), ordering="id")
    def id_badge(self, obj):
        """نمایش شناسه عددی."""
        return format_html('<code style="{}">#{}</code>', _CODE, obj.pk)

    @admin.display(description=_("عنوان کانال"), ordering="title")
    def title_link(self, obj):
        """نمایش عنوان کانال به عنوان لینک به صفحه ویرایش."""
        url = reverse("admin:broadcast_broadcastchannel_change", args=[obj.pk])
        return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.title)

    @admin.display(description=_("کاربر"), ordering="user__phone_number")
    def user_link(self, obj):
        """لینک به صفحه کاربر در ادمین."""
        url = reverse(f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    @admin.display(description=_("پلتفرم"), ordering="platform__name")
    def platform_badge(self, obj):
        """نمایش نام پلتفرم به صورت نشان."""
        return format_html('<span style="{}">{}</span>', _BADGE_PRIMARY, obj.platform.name)

    @admin.display(description=_("شناسه کانال"))
    def chat_id_display(self, obj):
        """نمایش chat_id با فونت یکنواخت."""
        return format_html('<code style="{}">{}</code>', _CODE, obj.chat_id)

    @admin.display(description=_("ربات ادمین"), ordering="bot_is_admin", boolean=False)
    def bot_admin_badge(self, obj):
        """نشان وضعیت ادمین بودن ربات."""
        style = _BADGE_SUCCESS if obj.bot_is_admin else _BADGE_DANGER
        text = "✓ ادمین" if obj.bot_is_admin else "✗ ادمین نیست"
        return format_html('<span style="{}">{}</span>', style, text)

    @admin.display(description=_("فعال"), ordering="is_active", boolean=False)
    def active_badge(self, obj):
        """نشان فعال/غیرفعال بودن کانال."""
        style = _BADGE_SUCCESS if obj.is_active else _BADGE_MUTED
        text = "✓ فعال" if obj.is_active else "غیرفعال"
        return format_html('<span style="{}">{}</span>', style, text)

    @admin.display(description=_("آخرین ارسال"), ordering="last_broadcast_at")
    def last_broadcast_display(self, obj):
        """نمایش تاریخ آخرین ارسال یا «هرگز»."""
        if not obj.last_broadcast_at:
            return mark_safe('<span style="color:#9691a4;">هرگز</span>')
        return obj.last_broadcast_at.strftime("%Y/%m/%d %H:%M")

    @admin.display(description=_("وضعیت توکن"))
    def token_status_display(self, obj):
        """نشان وضعیت اعتبار توکن تأیید."""
        if not obj.verification_token:
            return format_html('<span style="{}">توکنی وجود ندارد</span>', _BADGE_MUTED)
        if obj.verification_token_used_at:
            return format_html('<span style="{}">استفاده شده ✓</span>', _BADGE_SUCCESS)
        if obj.is_token_valid():
            return format_html('<span style="{}">معتبر (۱۰ دقیقه)</span>', _BADGE_INFO)
        return format_html('<span style="{}">منقضی شده</span>', _BADGE_WARNING)

    @admin.action(description=_("تولید توکن تأیید جدید"))
    def action_generate_token(self, request, queryset):
        """تولید توکن یک‌بارمصرف جدید برای کانال‌های انتخاب‌شده."""
        count = 0
        for obj in queryset:
            obj.verification_token = uuid.uuid4().hex[:12]
            obj.verification_token_created_at = timezone.now()
            obj.verification_token_used_at = None
            obj.save(
                update_fields=["verification_token", "verification_token_created_at", "verification_token_used_at"])
            count += 1
        self.message_user(request, f"توکن جدید برای {count} کانال تولید شد.")

    @admin.action(description=_("علامت‌گذاری ربات به عنوان ادمین"))
    def action_mark_bot_admin(self, request, queryset):
        """تأیید دستی ادمین بودن ربات برای کانال‌های انتخاب‌شده."""
        n = queryset.update(bot_is_admin=True, bot_admin_checked_at=timezone.now())
        self.message_user(request, f"{n} کانال به عنوان ادمین علامت‌گذاری شد.")

    @admin.action(description=_("حذف علامت ادمین بودن ربات"))
    def action_mark_bot_not_admin(self, request, queryset):
        """لغو ادمین بودن ربات."""
        n = queryset.update(bot_is_admin=False, bot_admin_checked_at=timezone.now())
        self.message_user(request, f"{n} کانال از حالت ادمین خارج شد.")

    @admin.action(description=_("فعال‌سازی کانال"))
    def action_activate(self, request, queryset):
        """فعال‌سازی کانال‌های انتخاب‌شده."""
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} کانال فعال شد.")

    @admin.action(description=_("غیرفعال‌سازی کانال"))
    def action_deactivate(self, request, queryset):
        """غیرفعال‌سازی کانال‌های انتخاب‌شده."""
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} کانال غیرفعال شد.")


# ============================================================
# BroadcastMessage
# ============================================================

@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    """مدیریت پیام‌های ارسالی وین فوروارد."""

    list_display = ("id_badge", "user_link", "content_type_badge", "text_preview", "file_badge", "created_at")
    list_display_links = ("id_badge",)
    list_filter = ("content_type", ("created_at", admin.DateFieldListFilter))
    search_fields = ("text", "user__phone_number", "user__nickname")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "file_preview")
    list_per_page = 50
    list_select_related = ("user",)
    save_on_top = True
    ordering = ("-created_at",)
    fieldsets = (
        (_("مالکیت"), {"fields": ("user",)}),
        (_("محتوا"), {"fields": ("content_type", "text", "file", "file_preview")}),
        (_("زمان"), {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    @admin.display(description=_("ID"), ordering="id")
    def id_badge(self, obj):
        """نمایش شناسه عددی."""
        return format_html('<code style="{}">#{}</code>', _CODE, obj.pk)

    @admin.display(description=_("کاربر"), ordering="user__phone_number")
    def user_link(self, obj):
        """لینک به صفحه کاربر."""
        url = reverse(f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    @admin.display(description=_("نوع محتوا"), ordering="content_type")
    def content_type_badge(self, obj):
        """نمایش نوع محتوا با نشان رنگی."""
        color_map = {"text": _BADGE_INFO, "photo": _BADGE_PRIMARY, "video": _BADGE_WARNING, "document": _BADGE_MUTED}
        return format_html('<span style="{}">{}</span>', color_map.get(obj.content_type, _BADGE_MUTED),
                           obj.get_content_type_display())

    @admin.display(description=_("پیش‌نمایش متن"))
    def text_preview(self, obj):
        """نمایش کوتاه‌شده متن با Tooltip کامل."""
        if not obj.text:
            return mark_safe('<span style="color:#9691a4;">—</span>')
        short = obj.text[:60] + ("…" if len(obj.text) > 60 else "")
        return format_html('<span title="{}">{}</span>', obj.text, short)

    @admin.display(description=_("فایل"), boolean=False)
    def file_badge(self, obj):
        """نشان وجود فایل."""
        if not obj.file:
            return format_html('<span style="{}">—</span>', _BADGE_MUTED)
        return format_html('<span style="{}">دارد</span>', _BADGE_SUCCESS)

    @admin.display(description=_("پیش‌نمایش فایل"))
    def file_preview(self, obj):
        """پیش‌نمایش فایل در صفحه ویرایش (عکس) یا لینک دانلود."""
        if not obj.file:
            return "—"
        if obj.content_type == BroadcastMessage.ContentType.PHOTO:
            return format_html('<img src="{}" style="max-height:200px;border-radius:8px;" />', obj.file.url)
        return format_html('<a href="{}" target="_blank">دانلود فایل</a>', obj.file.url)


# ============================================================
# BroadcastJob + Inline Target
# ============================================================

class BroadcastTargetInline(admin.TabularInline):
    """نمایش فشرده مقاصد ارسال در صفحه جاب."""

    model = BroadcastTarget
    fields = ("channel", "status", "platform_message_id", "retry_count", "sent_at", "error_message")
    readonly_fields = ("platform_message_id", "retry_count", "sent_at", "error_message")
    extra = 0
    max_num = 0
    can_delete = False
    show_change_link = True
    classes = ("collapse",)


@admin.register(BroadcastJob)
class BroadcastJobAdmin(admin.ModelAdmin):
    """مدیریت جاب‌های ارسال گروهی."""

    list_display = (
    "id_badge", "message_preview", "status_badge", "progress_bar", "success_badge", "failed_badge", "created_at")
    list_display_links = ("id_badge",)
    list_filter = ("status", ("created_at", admin.DateFieldListFilter))
    search_fields = ("message__text", "message__user__phone_number")
    autocomplete_fields = ("message",)
    readonly_fields = (
    "total_targets", "success_count", "failed_count", "started_at", "finished_at", "created_at", "success_rate_display")
    inlines = (BroadcastTargetInline,)
    list_per_page = 50
    list_select_related = ("message", "message__user")
    save_on_top = True
    ordering = ("-created_at",)
    actions = ("action_recalculate", "action_mark_pending")
    fieldsets = (
        (_("پیام"), {"fields": ("message",)}),
        (_("وضعیت"), {"fields": ("status",)}),
        (_("آمار"), {"fields": ("total_targets", "success_count", "failed_count", "success_rate_display")}),
        (_("زمان‌ها"), {"fields": ("started_at", "finished_at", "created_at"), "classes": ("collapse",)}),
    )

    @admin.display(description=_("ID"), ordering="id")
    def id_badge(self, obj):
        """نمایش شناسه عددی."""
        return format_html('<code style="{}">#{}</code>', _CODE, obj.pk)

    @admin.display(description=_("پیام"))
    def message_preview(self, obj):
        """نمایش کوتاه محتوای پیام."""
        text = obj.message.text or "—"
        short = text[:40] + ("…" if len(text) > 40 else "")
        return format_html('<span title="{}">{}</span>', text, short)

    @admin.display(description=_("وضعیت"), ordering="status")
    def status_badge(self, obj):
        """نشان وضعیت جاب."""
        color_map = {"pending": _BADGE_MUTED, "running": _BADGE_INFO, "done": _BADGE_SUCCESS, "partial": _BADGE_WARNING,
                     "failed": _BADGE_DANGER}
        return format_html('<span style="{}">{}</span>', color_map.get(obj.status, _BADGE_MUTED),
                           obj.get_status_display())

    @admin.display(description=_("پیشرفت"))
    def progress_bar(self, obj):
        """نمایش نوار پیشرفت درصدی."""
        if not obj.total_targets:
            return mark_safe('<span style="color:#9691a4;">—</span>')
        pct = obj.success_rate
        color = "#07c98b" if pct == 100 else ("#fdbc31" if pct > 0 else "#f23c49")
        return format_html(
            '<div style="background:#efecf3;border-radius:6px;height:18px;width:120px;overflow:hidden;"><div style="background:{};height:100%;width:{}%;"></div></div><span style="font-size:11px;margin-right:6px;">{}/{} ({}%)</span>',
            color, pct, obj.success_count, obj.total_targets, pct,
        )

    @admin.display(description=_("موفق"), ordering="success_count")
    def success_badge(self, obj):
        """نمایش تعداد موفق."""
        if obj.success_count == 0:
            return mark_safe('<span style="color:#9691a4;">0</span>')
        return format_html('<strong style="color:#07c98b;">{}</strong>', obj.success_count)

    @admin.display(description=_("ناموفق"), ordering="failed_count")
    def failed_badge(self, obj):
        """نمایش تعداد ناموفق."""
        if obj.failed_count == 0:
            return mark_safe('<span style="color:#9691a4;">0</span>')
        return format_html('<strong style="color:#f23c49;">{}</strong>', obj.failed_count)

    @admin.display(description=_("درصد موفقیت"))
    def success_rate_display(self, obj):
        """نمایش درصد موفقیت با نشان رنگی."""
        pct = obj.success_rate
        style = _BADGE_SUCCESS if pct == 100 else (_BADGE_WARNING if pct > 0 else _BADGE_DANGER)
        return format_html('<span style="{}">{}%</span>', style, pct)

    @admin.action(description=_("بازشماری آمار از مقاصد"))
    def action_recalculate(self, request, queryset):
        """بازشماری تعداد موفق/ناموفق و بروزرسانی وضعیت."""
        for job in queryset:
            job.recalculate_counts()
        self.message_user(request, f"آمار {queryset.count()} جاب بازشماری شد.")

    @admin.action(description=_("بازگردانی به وضعیت در انتظار"))
    def action_mark_pending(self, request, queryset):
        """بازگردانی جاب‌های انتخاب‌شده به وضعیت pending برای اجرای مجدد."""
        n = queryset.update(status=BroadcastJob.Status.PENDING, started_at=None, finished_at=None)
        self.message_user(request, f"{n} جاب به وضعیت در انتظار بازگشت.")


# ============================================================
# BroadcastTarget (standalone)
# ============================================================

@admin.register(BroadcastTarget)
class BroadcastTargetAdmin(admin.ModelAdmin):
    """مدیریت مستقل مقاصد ارسال — برای عیب‌یابی."""

    list_display = ("id_badge", "job_link", "channel_link", "status_badge", "retry_count", "sent_at")
    list_display_links = ("id_badge",)
    list_filter = ("status", ("created_at", admin.DateFieldListFilter))
    search_fields = ("channel__title", "channel__chat_id", "error_message", "job__message__text")
    autocomplete_fields = ("job", "channel")
    readonly_fields = ("platform_message_id", "sent_at", "retry_count", "created_at", "error_message")
    list_per_page = 50
    list_select_related = ("job", "channel")
    ordering = ("-created_at",)

    @admin.display(description=_("ID"), ordering="id")
    def id_badge(self, obj):
        """نمایش شناسه عددی."""
        return format_html('<code style="{}">#{}</code>', _CODE, obj.pk)

    @admin.display(description=_("جاب"), ordering="job_id")
    def job_link(self, obj):
        """لینک به صفحه جاب."""
        url = reverse("admin:broadcast_broadcastjob_change", args=[obj.job_id])
        return format_html('<a href="{}">جاب #{}</a>', url, obj.job_id)

    @admin.display(description=_("کانال"), ordering="channel__title")
    def channel_link(self, obj):
        """لینک به صفحه کانال."""
        url = reverse("admin:broadcast_broadcastchannel_change", args=[obj.channel_id])
        return format_html('<a href="{}">{}</a>', url, obj.channel.title)

    @admin.display(description=_("وضعیت"), ordering="status")
    def status_badge(self, obj):
        """نشان وضعیت ارسال."""
        color_map = {"pending": _BADGE_MUTED, "running": _BADGE_INFO, "success": _BADGE_SUCCESS,
                     "failed": _BADGE_DANGER, "skipped": _BADGE_WARNING}
        return format_html('<span style="{}">{}</span>', color_map.get(obj.status, _BADGE_MUTED),
                           obj.get_status_display())


# ============================================================
# ChannelPreset
# ============================================================


@admin.register(ChannelPreset)
class ChannelPresetAdmin(admin.ModelAdmin):
    """مدیریت پروفایل‌های ارسال (گروه‌بندی کانال‌ها) در پنل ادمین."""

    list_display = (
        "id_badge",
        "name_link",
        "user_link",
        "channels_count_badge",
        "channels_preview",
        "active_badge",
        "created_at",
    )
    list_display_links = ("id_badge", "name_link")
    list_filter = ("is_active", ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "user__phone_number", "user__nickname", "channels__title")
    autocomplete_fields = ("user",)
    filter_horizontal = ("channels",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    list_select_related = ("user",)
    save_on_top = True
    ordering = ("-created_at",)
    actions = ("action_activate", "action_deactivate")
    fieldsets = (
        (_("مالکیت و عنوان"), {"fields": ("user", "name", "is_active")}),
        (_("کانال‌های عضو"), {"fields": ("channels",)}),
        (_("زمان‌ها"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        """بهینه‌سازی کوئری با select_related و prefetch_related."""
        return super().get_queryset(request).select_related("user").prefetch_related("channels__platform")

    @admin.display(description=_("ID"), ordering="id")
    def id_badge(self, obj):
        """نمایش شناسه عددی پروفایل."""
        return format_html('<code style="{}">#{}</code>', _CODE, obj.pk)

    @admin.display(description=_("نام پروفایل"), ordering="name")
    def name_link(self, obj):
        """لینک مستقیم به صفحه ویرایش پروفایل ارسال."""
        url = reverse("admin:broadcast_channelpreset_change", args=[obj.pk])
        return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.name)

    @admin.display(description=_("کاربر"), ordering="user__phone_number")
    def user_link(self, obj):
        """لینک به صفحه کاربر در ادمین."""
        url = reverse(f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    @admin.display(description=_("تعداد کانال"))
    def channels_count_badge(self, obj):
        """نمایش تعداد کانال‌های عضو پروفایل."""
        count = obj.channels.count()
        style = _BADGE_INFO if count > 0 else _BADGE_MUTED
        return format_html('<span style="{}">{} کانال</span>', style, count)

    @admin.display(description=_("کانال‌ها"))
    def channels_preview(self, obj):
        """نمایش خلاصه عناوین کانال‌های عضو پروفایل."""
        titles = [ch.title for ch in obj.channels.all()[:4]]
        if not titles:
            return mark_safe('<span style="color:#9691a4;">—</span>')
        extra = obj.channels.count() - len(titles)
        text = "، ".join(titles)
        if extra > 0:
            text += f" (+{extra})"
        return text

    @admin.display(description=_("وضعیت"), ordering="is_active")
    def active_badge(self, obj):
        """نشان فعال یا غیرفعال بودن پروفایل."""
        style = _BADGE_SUCCESS if obj.is_active else _BADGE_MUTED
        text = "✓ فعال" if obj.is_active else "غیرفعال"
        return format_html('<span style="{}">{}</span>', style, text)

    @admin.action(description=_("فعال‌سازی پروفایل‌ها"))
    def action_activate(self, request, queryset):
        """فعال‌سازی پروفایل‌های انتخاب‌شده."""
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} پروفایل ارسال فعال شد.")

    @admin.action(description=_("غیرفعال‌سازی پروفایل‌ها"))
    def action_deactivate(self, request, queryset):
        """غیرفعال‌سازی پروفایل‌های انتخاب‌شده."""
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} پروفایل ارسال غیرفعال شد.")
