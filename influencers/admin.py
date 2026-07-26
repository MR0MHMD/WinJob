from .models import InfluencerProfile, Channel, ChannelServiceRate, ChannelReview, ChannelBooking
from .inline_admin import ChannelServiceRateInline, ChannelInline, ChannelReviewInline
from core.utils.admin_utils import format_datetime, RegionalFilterAdminMixin
from django_jalali.admin.filters import JDateFieldListFilter
from campaigns.inline_admin import CampaignReportInline
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from accounts.models import CustomUser
from campaigns.models import Campaign
from django.utils import timezone
from django.contrib import admin
from core.models import Province
from django.urls import reverse


@admin.register(InfluencerProfile)
class InfluencerProfileAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "full_name",
        "user_phone_display",
        "user_province",
        "channels_count",
        "is_active",
        "formatted_created_at",
    )

    list_filter = (
        "is_active",
        ("created_at", JDateFieldListFilter),
    )

    search_fields = (
        "full_name",
        "user__phone_number",
        "user__nickname",
        "description",
    )

    autocomplete_fields = (
        "user",
    )

    inlines = [ChannelInline, ]

    readonly_fields = (
        "formatted_created_at",
        "formatted_updated_at",
        "channels_count_display",
    )

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": (
                "user",
                "full_name",
                "description",
            )
        }),
        ("وضعیت", {
            "fields": (
                "is_active",
                "channels_count_display",
            ),
            'classes': ('collapse',)
        }),
        ("تاریخ ها", {
            "fields": (
                "formatted_created_at",
                "formatted_updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    def user_phone_display(self, obj):
        return obj.user.phone_number

    user_phone_display.short_description = "شماره تماس"
    user_phone_display.admin_order_field = "user__phone_number"

    def user_province(self, obj):
        return obj.user.province.name if obj.user.province else "-"

    user_province.short_description = "استان"
    user_province.admin_order_field = "user__province__name"

    def channels_count(self, obj):
        return obj.channels.count()

    channels_count.short_description = "تعداد کانال"

    def channels_count_display(self, obj):
        total = obj.channels.count()
        active = obj.channels.filter(is_active=True).count()
        return f"{total} کانال ({active} فعال)"

    channels_count_display.short_description = "وضعیت کانال ها"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین ویرایش"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            return qs.filter(user__province=request.user.province)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user' and request.user.is_regional_manager:
            kwargs['queryset'] = CustomUser.objects.filter(
                province=request.user.province,
                influencer_profile__isnull=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if request.user.is_regional_manager and request.user.province:
            if obj.user.province != request.user.province:
                raise ValidationError('شما فقط می‌توانید اینفلوئنسرهای استان خودتان را مدیریت کنید.')
        super().save_model(request, obj, form, change)


@admin.register(Channel)
class ChannelAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "channel_display",
        "influencer",
        "platform",
        "is_active",
        "status",
        "formatted_created_at",
        "qr_code_preview",  # اضافه شد
    )
    list_filter = ('platform', 'province', "is_active", 'created_at',)
    search_fields = ("channel_id", "channel_name", "influencer__full_name", "influencer__user__phone_number",)
    autocomplete_fields = ("influencer", "platform", "category", "province",)
    ordering = ("created_at", 'followers_count')
    inlines = [ChannelServiceRateInline, ChannelReviewInline]
    actions = ['mark_as_approved', 'mark_as_rejected', 'regenerate_qr']  # اکشن جدید
    readonly_fields = (
        "followers_formatted_display",
        "formatted_created_at",
        "formatted_updated_at",
        "rates_count_display",
        "qr_code_preview_large",  # اضافه شد
    )

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": (
                "influencer",
                "platform",
                "channel_id",
                "channel_name",
                "url",
            )
        }),
        ("موقعیت مکانی کانال", {
            "fields": ("province",),
            "classes": ("collapse",)
        }),
        ("دسته‌بندی", {
            "fields": ("category",),
            "classes": ("collapse",)
        }),
        ("آمار و تصویر", {
            "fields": ("followers_count", "avatar", "qr_code"),  # QR Code اضافه شد
            "classes": ("collapse",)
        }),
        ("پیش‌نمایش QR Code", {
            "fields": ("qr_code_preview_large",),
            "classes": ("collapse",)
        }),
        ("وضعیت", {
            "fields": ("is_active", "status"),
            "classes": ("collapse",)
        }),
        ("تاریخچه", {
            "fields": ("formatted_created_at", "formatted_updated_at"),
            "classes": ("collapse",)
        }),
    )

    # ========== متدهای نمایش QR Code ==========

    def qr_code_preview(self, obj):
        """نمایش QR Code در لیست"""
        if obj.qr_code:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius: 8px; object-fit: cover;" />',
                obj.qr_code.url
            )
        return mark_safe(
            '<span style="color: #999; font-size: 12px;">بدون QR</span>'
        )

    qr_code_preview.short_description = "QR Code"

    def qr_code_preview_large(self, obj):
        """نمایش QR Code بزرگ در صفحه جزئیات"""
        if obj.qr_code:
            return format_html(
                '''
                <div style="display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 10px 0;">
                    <img src="{}" width="200" height="200" style="border-radius: 16px; object-fit: cover; border: 2px solid #e0e0e0;" />
                    <div style="display: flex; gap: 10px;">
                        <a href="{}" download class="button" style="padding: 6px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 6px;">
                            ⬇️ دانلود QR Code
                        </a>
                    </div>
                </div>
                ''',
                obj.qr_code.url,
                obj.qr_code.url,
            )
        return mark_safe(
            '<span style="color: #999;">QR Code تولید نشده است. از اکشن "باز تولید QR Code" استفاده کنید.</span>'
        )

    qr_code_preview_large.short_description = "پیش‌نمایش QR Code"

    # ========== اکشن بازتولید QR Code ==========

    def regenerate_qr(self, request, queryset):
        """بازتولید QR Code برای کانال‌های انتخاب شده"""
        count = 0
        for channel in queryset:
            try:
                channel.generate_qr(force=True)
                count += 1
            except Exception as e:
                self.message_user(request, f"خطا در تولید QR برای {channel.channel_name}: {e}", level='ERROR')

        if count > 0:
            self.message_user(request, f"✅ QR Code برای {count} کانال بازتولید شد.")

    regenerate_qr.short_description = "♻️ بازتولید QR Code برای کانال‌های انتخاب شده"

    # ========== متدهای قبلی ==========

    def channel_display(self, obj):
        return obj.channel_id

    channel_display.short_description = "آیدی کانال"

    def channel_province(self, obj):
        return obj.province.name if obj.province else "-"

    channel_province.short_description = "استان کانال"
    channel_province.admin_order_field = "province__name"

    def followers_formatted_display(self, obj):
        return obj.followers_formatted()

    followers_formatted_display.short_description = "فالوورها"

    def rates_count(self, obj):
        return obj.service_rates.count()

    rates_count.short_description = "نرخ تبلیغ"

    def rates_count_display(self, obj):
        total = obj.service_rates.count()
        active = obj.service_rates.filter(is_active=True).count()
        return f"{total} نرخ ({active} فعال)"

    rates_count_display.short_description = "نرخ های تبلیغ"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین ویرایش"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            return qs.filter(province=request.user.province)
        return qs

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'province' and request.user.is_regional_manager:
            kwargs['queryset'] = Province.objects.filter(id=request.user.province.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if request.user.is_regional_manager and request.user.province:
            obj.province = request.user.province
        super().save_model(request, obj, form, change)

    def mark_as_approved(modeladmin, request, queryset):
        queryset.update(status='approved')

    mark_as_approved.short_description = "✅ تایید کانال‌های انتخاب شده"

    def mark_as_rejected(modeladmin, request, queryset):
        queryset.update(status='rejected')

    mark_as_rejected.short_description = "❌ رد کانال‌های انتخاب شده"


@admin.register(ChannelServiceRate)
class ChannelServiceRateAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_filter = ("is_active", "ad_type", "channel__platform", "channel__province",)
    search_fields = ("channel__channel_id", "channel__channel_name", "channel__influencer__full_name", "ad_type__name",)
    autocomplete_fields = ("channel", "ad_type",)
    readonly_fields = ("formatted_price", "formatted_created_at", "formatted_updated_at",)
    list_display = (
        "channel_display",
        "influencer_name",
        "ad_type",
        "formatted_price",
        "is_active",
        "formatted_created_at",
    )
    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": ("channel", "ad_type", "price")
        }),
        ("وضعیت", {
            "fields": ("is_active",),
            "classes": ("collapse",)
        }),
        ("تاریخچه", {
            "fields": ("formatted_created_at", "formatted_updated_at"),
            "classes": ("collapse",)
        }),
    )

    def channel_display(self, obj):
        return f"{obj.channel.channel_name} ({obj.channel.channel_id})"

    channel_display.short_description = "کانال"

    def influencer_name(self, obj):
        return obj.channel.influencer.full_name

    influencer_name.short_description = "اینفلوئنسر"
    influencer_name.admin_order_field = "channel__influencer__full_name"

    def formatted_price(self, obj):
        return obj.formatted_price()

    formatted_price.short_description = "قیمت"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین ویرایش"

    def get_queryset(self, request):
        """فقط نرخ‌هایی که کانالش در استان مدیر است"""
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            return qs.filter(channel__province=request.user.province)

        return qs

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.channel.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.channel.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """محدود کردن انتخاب کانال در فرم"""
        if db_field.name == 'channel' and request.user.is_regional_manager:
            kwargs['queryset'] = Channel.objects.filter(
                province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ChannelReview)
class ChannelReviewAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "channel",
        "advertiser",
        "rating",
        "campaign_booking",
        "short_comment",
        "formatted_created_at",
    )

    list_filter = ("rating", ("created_at", JDateFieldListFilter), "channel__influencer__user__province",)

    search_fields = (
        "channel__channel_name",
        "channel__influencer__full_name",
        "channel__influencer__user__phone_number",
        "advertiser__user__phone_number",
        "advertiser__user__nickname",
        "comment",
    )

    autocomplete_fields = (
        "channel",
        "advertiser",
        "campaign_booking",
    )

    readonly_fields = (
        "formatted_created_at",
    )

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": ("channel", "advertiser", "campaign_booking",)
        }),
        ("امتیاز و نظر", {
            "fields": ("rating", "comment",)
        }),
        ("تاریخ", {
            "fields": ("formatted_created_at",),
            "classes": ("collapse",)
        }),
    )

    def influencer_province_display(self, obj):
        """نمایش استان اینفلوئنسر در فرم (فقط خوندنی)"""
        province = obj.influencer.user.province
        return province.name if province else "-"

    influencer_province_display.short_description = "استان اینفلوئنسر"

    def short_comment(self, obj):
        if not obj.comment:
            return "-"
        return obj.comment[:40] + ("..." if len(obj.comment) > 40 else "")

    short_comment.short_description = "نظر"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ثبت"

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            return qs.filter(channel__influencer__user__province=request.user.province)

        return qs.select_related(
            'channel',
            'channel__influencer',
            'channel__influencer__user',
            'channel__influencer__user__province',
            'advertiser',
            'advertiser__user',
            'campaign_booking',
        )

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.influencer.user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.influencer.user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """محدود کردن انتخاب اینفلوئنسر در فرم"""
        if db_field.name == 'channel' and request.user.is_regional_manager:
            kwargs['queryset'] = InfluencerProfile.objects.filter(
                user__province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ChannelBooking)
class ChannelBookingAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "campaign_link",
        "channel_link",
        "price",
        "status",
        "is_paid",
        "has_report_status",
        "formatted_created_at",
    )

    list_filter = (
        "status",
        "is_paid",
        ("created_at", JDateFieldListFilter),
        "channel__province",  # فیلتر بر اساس استان کانال
    )

    search_fields = (
        "campaign__name",
        "channel__channel_id",
        "channel__channel_name",
        "channel__influencer__full_name",
        "tracking_code",
    )

    readonly_fields = (
        "tracking_code",
        "formatted_created_at",
        "formatted_paid_at",
        "uniq_url_display",
    )

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": (
                "campaign",
                "channel",
                "service_rate",
                "price",
            )
        }),
        ("وضعیت", {
            "fields": (
                "status",
                "is_seen",
                "is_paid",
            )
        }),
        ("کد ردیابی", {
            "fields": (
                "tracking_code",
                "uniq_url_display",
            )
        }),
        ("تاریخ‌ها", {
            "fields": (
                "formatted_created_at",
                "formatted_paid_at",
            ),
            "classes": ("collapse",)
        }),
    )

    inlines = [CampaignReportInline]

    actions = ["mark_as_accepted", "mark_as_completed", "mark_as_paid"]

    # ========== متدهای نمایش ==========

    def campaign_link(self, obj):
        """لینک به کمپین"""
        url = reverse("admin:campaigns_campaign_change", args=[obj.campaign.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.campaign.name[:40])

    campaign_link.short_description = "کمپین"

    def channel_link(self, obj):
        """لینک به کانال اینفلوئنسر"""
        url = reverse("admin:influencers_Channel_change", args=[obj.channel.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.channel.channel_name)

    channel_link.short_description = "کانال"

    def has_report_status(self, obj):
        """وضعیت گزارش"""
        if hasattr(obj, 'report'):
            status = obj.report.status
            if status == 'approved':
                return "✅ تأیید شده"
            elif status == 'pending':
                return "⏳ در انتظار"
            elif status == 'rejected':
                return "❌ رد شده"
            return "📋 ثبت شده"
        return "❌ ثبت نشده"

    has_report_status.short_description = "گزارش"

    def uniq_url_display(self, obj):
        """نمایش لینک یکتا"""
        return format_html(
            '<a href="{}" target="_blank" style="direction: ltr; display: block; word-break: break-all;">{}</a>',
            obj.uniq_url(),
            obj.uniq_url()
        )

    uniq_url_display.short_description = "لینک ردیابی"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_paid_at(self, obj):
        return format_datetime(obj.paid_at) if obj.paid_at else "-"

    formatted_paid_at.short_description = "تاریخ پرداخت"

    # ========== اکشن‌ها ==========

    def mark_as_accepted(self, request, queryset):
        updated = queryset.update(status=ChannelBooking.Status.ACCEPTED)
        self.message_user(request, f"{updated} رزرو پذیرفته شد.")

    mark_as_accepted.short_description = "پذیرفتن رزروهای انتخاب شده"

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status=ChannelBooking.Status.COMPLETED)
        self.message_user(request, f"{updated} رزرو انجام شد.")

    mark_as_completed.short_description = "انجام شدن رزروهای انتخاب شده"

    def mark_as_paid(self, request, queryset):
        updated = queryset.update(is_paid=True, paid_at=timezone.now())
        self.message_user(request, f"{updated} رزرو به عنوان پرداخت شده علامت خورد.")

    mark_as_paid.short_description = "علامت زدن به عنوان پرداخت شده"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            # فیلتر بر اساس استان کانال
            qs = qs.filter(channel__province=request.user.province)

        return qs.select_related(
            'campaign',
            'channel',
            'channel__province',
            'service_rate',
        )

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.channel.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.channel.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'campaign' and request.user.is_regional_manager:
            # فقط کمپین‌های استان خودش
            kwargs['queryset'] = Campaign.objects.filter(
                advertiser__user__province=request.user.province
            )
        if db_field.name == 'channel' and request.user.is_regional_manager:
            # فقط کانال‌های استان خودش
            kwargs['queryset'] = Channel.objects.filter(
                province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
