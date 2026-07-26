from .models import Campaign, CampaignContent, CampaignTrackingLink, CampaignReport, CampaignClick
from django_jalali.admin.filters import JDateFieldListFilter
from core.utils.admin_utils import RegionalFilterAdminMixin
from influencers.inline_admin import ChannelBookingInline
from core.utils.admin_utils import format_datetime
from advertisers.models import AdvertiserProfile
from .inline_admin import CampaignClickInline
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.contrib import admin
from django.urls import reverse
import os
from campaigns.services.campaigns_notifications import (
    approve_campaign_by_admin,
    reject_campaign_by_admin,
    approve_influencer_report_service,
    reject_influencer_report_service
)


@admin.register(Campaign)
class CampaignAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    inlines = [ChannelBookingInline]

    list_display = (
        "name",
        "advertiser_display",
        "status",
        "influencers_count",
        "is_free",
        "payable_amount",
        "formatted_created_at",
    )

    list_filter = (
        "status",
        "is_free",
        ("created_at", JDateFieldListFilter),
        "advertiser__user__province",
    )

    search_fields = (
        "name",
        "advertiser__user__phone_number",
        "advertiser__business_name",
    )

    ordering = ("-created_at",)

    autocomplete_fields = ("advertiser", "platform",)

    readonly_fields = (
        "created_at",
        "updated_at",
        "influencers_count_display",
        "invoice_total",
        "payable_amount_readonly",
        "commission_display",
        "influencer_cost_display",
        "content_cost_display",
        "advertiser_province",
    )

    fieldsets = (
        ("اطلاعات کمپین", {
            "fields": (
                "name",
                "advertiser",
                "advertiser_province",
                "description",
            )
        }),
        ("نوع تبلیغات", {
            "fields": (
                "platform",
                "content_type",
                "ad_type",
                "content_service_type",
            )
        }),
        ("زمان‌بندی", {
            "fields": (
                "start_date",
                "end_date",
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
        ("وضعیت", {
            "fields": ("status",)
        }),
        ("اینفلوئنسرها", {
            "fields": ("influencers_count_display",),
            "classes": ("collapse",)
        }),
        ("اطلاعات مالی", {
            "fields": (
                "influencer_cost_display",
                "content_cost_display",
                "commission_display",
                "invoice_total",
                "discount_amount",
                "payable_amount_readonly",
            ),
            "classes": ("collapse",)
        }),
        ("کدهای تخفیف", {
            "fields": (
                "influencer_coupon",
                "content_team_coupon",
                "platform_coupon",
            ),
            "classes": ("collapse",)
        }),
    )

    actions = ["approve_campaign", "reject_campaign"]

    # ========== متدهای نمایش ==========

    def advertiser_display(self, obj):
        """نمایش نام تبلیغ‌دهنده با لینک به پروفایل"""

        url = reverse("admin:advertisers_advertiserprofile_change", args=[obj.advertiser.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.advertiser.business_name)

    advertiser_display.short_description = "تبلیغ‌دهنده"
    advertiser_display.admin_order_field = "advertiser__business_name"

    def advertisers_count(self, obj):
        """تعداد اینفلوئنسرهای انتخاب شده"""
        return obj.influencer_bookings.count()

    advertisers_count.short_description = "تعداد اینفلوئنسر"
    advertisers_count.admin_order_field = "influencer_bookings__count"

    def influencers_count(self, obj):
        """تعداد اینفلوئنسرهای انتخاب شده (برای list_display)"""
        count = obj.influencer_bookings.count()
        if count == 0:
            return "❌ هیچ"
        else:
            return count

    influencers_count.short_description = "تعداد ناشران"

    def influencers_count_display(self, obj):
        """نمایش در فرم (فقط خوندنی)"""
        count = obj.influencer_bookings.count()
        active = obj.influencer_bookings.filter(status='accepted').count()
        completed = obj.influencer_bookings.filter(status='completed').count()
        return f"جمع: {count} | فعال: {active} | انجام شده: {completed}"

    influencers_count_display.short_description = "وضعیت اینفلوئنسرها"

    def payable_amount(self, obj):
        if obj.is_free:
            return mark_safe('<span class="text-success">💚 رایگان</span>')
        else:
            if hasattr(obj, "invoice"):
                return f"{obj.invoice.payable_amount:,} تومان"
            else:
                return "_"

    payable_amount.short_description = "مبلغ قابل پرداخت"
    payable_amount.admin_order_field = "invoice__payable_amount"

    def payable_amount_readonly(self, obj):
        """مبلغ قابل پرداخت برای فرم (فقط خوندنی)"""
        if hasattr(obj, "invoice"):
            return f"{obj.invoice.payable_amount:,} تومان"
        return "0 تومان"

    payable_amount_readonly.short_description = "مبلغ قابل پرداخت"

    def invoice_total(self, obj):
        if hasattr(obj, "invoice"):
            return f"{obj.invoice.total_amount:,} تومان"
        return "-"

    invoice_total.short_description = "مبلغ کل"

    def commission_display(self, obj):
        if hasattr(obj, "invoice"):
            return f"{obj.invoice.commission:,} تومان"
        return "-"

    commission_display.short_description = "کمیسیون"

    def influencer_cost_display(self, obj):
        if hasattr(obj, "invoice"):
            return f"{obj.invoice.influencer_cost:,} تومان"
        return "-"

    influencer_cost_display.short_description = "هزینه اینفلوئنسر"

    def content_cost_display(self, obj):
        if hasattr(obj, "invoice"):
            return f"{obj.invoice.content_cost:,} تومان"
        return "-"

    content_cost_display.short_description = "هزینه تولید محتوا"

    def advertiser_province(self, obj):
        """نمایش استان تبلیغ‌دهنده (فقط خوندنی)"""
        province = obj.advertiser.user.province
        return province.name if province else "-"

    advertiser_province.short_description = "استان تبلیغ‌دهنده"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"
    formatted_created_at.admin_order_field = "created_at"

    # ========== اکشن‌ها ==========

    def approve_campaign(self, request, queryset):
        # بررسی می‌کنیم که فقط کمپین‌های در انتظار بررسی آپدیت بشن
        pending_campaigns = queryset.filter(status=Campaign.Status.PENDING)
        updated_count = pending_campaigns.count()

        for campaign in pending_campaigns:
            # استفاده از سرویسِ خودمون تا هم وضعیت عوض شه هم نوتیف بره
            approve_campaign_by_admin(campaign)

        self.message_user(request, f"{updated_count} کمپین با موفقیت تایید و نوتیفیکیشن ارسال شد.")

    approve_campaign.short_description = "تایید کمپین‌های انتخاب شده"

    def reject_campaign(self, request, queryset):
        pending_campaigns = queryset.filter(status=Campaign.Status.PENDING)
        updated_count = pending_campaigns.count()

        for campaign in pending_campaigns:
            # دلیلِ رد شدن رو فعلا یه متن پیش‌فرض می‌ذاریم، یا اگه بخوای میتونی Action با فرم بسازی
            reject_campaign_by_admin(campaign, reason="رد شده توسط مدیریت")

        self.message_user(request, f"{updated_count} کمپین رد شد و نوتیفیکیشن ارسال گردید.")

    reject_campaign.short_description = "رد کمپین‌های انتخاب شده"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            qs = qs.filter(advertiser__user__province=request.user.province)

        return qs.select_related(
            'advertiser',
            'advertiser__user',
            'advertiser__user__province',
            'invoice',
        ).prefetch_related('influencer_bookings')

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.advertiser.user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.advertiser.user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'advertiser' and request.user.is_regional_manager:
            kwargs['queryset'] = AdvertiserProfile.objects.filter(
                user__province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # ۱. بررسی دسترسی مدیر منطقه‌ای (کد قبلی خودت)
        if request.user.is_regional_manager and request.user.province:
            if obj.advertiser.user.province != request.user.province:
                from django.core.exceptions import ValidationError
                raise ValidationError('شما فقط می‌توانید کمپین‌های تبلیغ‌دهندگان استان خودتان را ایجاد کنید.')

        # ۲. منطق هوشمند نوتیفیکیشن برای ویرایش کمپین
        if change:
            # گرفتن وضعیت واقعی و قبلی کمپین از دیتابیس (چون obj وضعیت جدید فرم را دارد)
            old_status = Campaign.objects.get(pk=obj.pk).status
            new_status = obj.status  # وضعیت جدیدی که ادمین انتخاب کرده

            # ابتدا تغییرات را در دیتابیس ذخیره می‌کنیم
            super().save_model(request, obj, form, change)

            # حالا اگر وضعیت قبلاً در انتظار تایید (PENDING) بوده و الان تغییر کرده:
            if old_status == Campaign.Status.PENDING:
                from notifications.utils import notify_advertiser_campaign_approved, notify_advertiser_campaign_rejected

                if new_status == Campaign.Status.APPROVED:
                    notify_advertiser_campaign_approved(obj)

                elif new_status == Campaign.Status.CANCELLED:
                    # استفاده از متد مستقیم نوتیفیکیشن برای فرم ادمین
                    # چون وضعیت قبلاً توسط super().save_model تغییر کرده است
                    notify_advertiser_campaign_rejected(obj, reason="رد/لغو شده توسط مدیریت در پنل ادمین")
        else:
            # اگر کمپین کاملاً جدید بود (ساخت از صفر در ادمین)
            super().save_model(request, obj, form, change)


@admin.register(CampaignContent)
class CampaignContentAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "campaign_link",
        "advertiser_name",
        "media_preview",
        "utm_enabled",
        "formatted_created_at",
    )

    search_fields = (
        "campaign__name",
        "campaign__advertiser__business_name",
        "caption",
    )

    list_filter = (
        "utm_enabled",
        ("created_at", JDateFieldListFilter),
        "campaign__advertiser__user__province",  # فیلتر بر اساس استان تبلیغ‌دهنده
    )

    readonly_fields = (
        "media_preview",
        "formatted_created_at",
        "formatted_updated_at",
    )

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": (
                "campaign",
                "media",
                "media_preview",
                "caption",
                "link",
                "notes",
            )
        }),
        ("UTM Tracking", {
            "classes": ("collapse",),
            "fields": (
                "utm_enabled",
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_content",
                "utm_term",
            )
        }),
        ("سیستم", {
            "fields": (
                "formatted_created_at",
                "formatted_updated_at",
            )
        }),
    )

    # ========== متدهای نمایش ==========

    def campaign_link(self, obj):
        """لینک به کمپین"""
        url = reverse("admin:campaigns_campaign_change", args=[obj.campaign.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.campaign.name[:40])

    campaign_link.short_description = "کمپین"

    def advertiser_name(self, obj):
        """نام تبلیغ‌دهنده"""
        return obj.campaign.advertiser.business_name

    advertiser_name.short_description = "تبلیغ‌دهنده"
    advertiser_name.admin_order_field = "campaign__advertiser__business_name"

    def media_preview(self, obj):
        if not obj.media:
            return "-"

        url = obj.media.url
        ext = os.path.splitext(url)[1].lower()

        image_ext = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        video_ext = ['.mp4', '.webm', '.ogg']

        if ext in image_ext:
            return format_html('<img style="width: 50px; border-radius:6px;" src="{}">', url)
        elif ext in video_ext:
            return format_html("<a href='{}' target='_blank'>🎥 مشاهده ویدیو</a>", url)
        else:
            return format_html("<a href='{}' target='_blank'>📎 دانلود فایل</a>", url)

    media_preview.short_description = "فایل"

    def formatted_created_at(self, obj):
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_updated_at(self, obj):
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین ویرایش"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            # فیلتر از طریق: campaign -> advertiser -> user -> province
            qs = qs.filter(campaign__advertiser__user__province=request.user.province)

        return qs.select_related(
            'campaign',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'campaign__advertiser__user__province',
        )

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign.advertiser.user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign.advertiser.user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'campaign' and request.user.is_regional_manager:
            # فقط کمپین‌های استان خودش
            kwargs['queryset'] = Campaign.objects.filter(
                advertiser__user__province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CampaignTrackingLink)
class CampaignTrackingLinkAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "campaign_name",
        "influencer_channel",
        "tracking_code",
        "clicks",
        "unique_clicks",
        "formatted_created_at",
    )

    search_fields = (
        "campaign_influencer__campaign__name",
        "campaign_influencer__channel__channel_id",
        "campaign_influencer__tracking_code",
    )

    list_filter = (
        ("created_at", JDateFieldListFilter),
        "campaign_influencer__channel__province",  # فیلتر بر اساس استان کانال
    )

    readonly_fields = (
        "campaign_influencer",
        "clicks",
        "unique_clicks",
        "formatted_created_at",
    )

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": (
                "campaign_influencer",
            )
        }),
        ("آمار کلیک", {
            "fields": (
                "clicks",
                "unique_clicks",
            )
        }),
        ("تاریخچه", {
            "fields": ("formatted_created_at",),
            "classes": ("collapse",)
        }),
    )

    inlines = [CampaignClickInline]

    # ========== متدهای نمایش ==========

    def campaign_name(self, obj):
        """نام کمپین با لینک"""
        campaign = obj.campaign_influencer.campaign
        url = reverse("admin:campaigns_campaign_change", args=[campaign.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, campaign.name[:40])

    campaign_name.short_description = "کمپین"
    campaign_name.admin_order_field = "campaign_influencer__campaign__name"

    def influencer_channel(self, obj):
        """کانال اینفلوئنسر با لینک"""
        channel = obj.campaign_influencer.channel
        url = reverse("admin:influencers_Channel_change", args=[channel.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, channel.channel_name)

    influencer_channel.short_description = "کانال"
    influencer_channel.admin_order_field = "campaign_influencer__channel__channel_name"

    def tracking_code(self, obj):
        """کد ردیابی"""
        return obj.campaign_influencer.tracking_code

    tracking_code.short_description = "کد ردیابی"

    def formatted_created_at(self, obj):
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            qs = qs.filter(campaign_influencer__channel__province=request.user.province)

        return qs.select_related(
            'campaign_influencer',
            'campaign_influencer__campaign',
            'campaign_influencer__channel',
            'campaign_influencer__channel__province',
        )

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign_influencer.channel.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign_influencer.channel.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)


@admin.register(CampaignClick)
class CampaignClickAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_code",
        "ip_address",
        "created_at",
    )

    search_fields = (
        "tracking_link__campaign_influencer__tracking_code",
        "ip_address",
    )

    list_filter = (
        "created_at",
    )

    readonly_fields = (
        "tracking_link",
        "ip_address",
        "user_agent",
        "created_at",
    )

    ordering = ("-created_at",)

    def tracking_code(self, obj):
        return obj.tracking_link.campaign_influencer.tracking_code

    tracking_code.short_description = "کد ردیابی"


@admin.register(CampaignReport)
class CampaignReportAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "campaign_link",
        "influencer_link",
        "advertiser_link",
        "status_badge",
        "auto_check_summary",
        "formatted_created_at",
    )

    list_filter = (
        "status",
        ("created_at", JDateFieldListFilter),
        "campaign_influencer__channel__province",
    )

    search_fields = (
        "campaign_influencer__campaign__name",
        "campaign_influencer__channel__channel_id",
        "campaign_influencer__channel__influencer__full_name",
        "campaign_influencer__campaign__advertiser__business_name",
        "post_link",
        "admin_notes",
    )

    autocomplete_fields = ("campaign_influencer",)

    readonly_fields = (
        "screenshot_preview",
        "post_link_display",
        "formatted_created_at",
        "formatted_updated_at",
        "campaign_details",
        "influencer_details",
        "advertiser_details",
        "auto_check_details_display",
    )

    fieldsets = (
        ("اطلاعات سفارش", {
            "fields": ("campaign_influencer", "campaign_details", "influencer_details", "advertiser_details",)
        }),
        ("گزارش ارسالی", {
            "fields": ("post_link_display", "screenshot_preview",)
        }),
        ("بررسی خودکار (n8n)", {
            "fields": ("auto_check_details_display",),
            "classes": ("collapse",)
        }),
        ("بررسی دستی", {
            "fields": ("status", "admin_notes",),
        }),
        ("تاریخ ها", {
            "fields": ("formatted_created_at", "formatted_updated_at",),
            "classes": ("collapse",),
        }),
    )

    actions = ["mark_as_approved", "mark_as_rejected", "mark_as_pending"]

    # ---------- ستون‌های لیست ----------
    def campaign_link(self, obj):
        campaign = obj.campaign_influencer.campaign
        url = reverse("admin:campaigns_campaign_change", args=[campaign.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, campaign.name[:40])

    campaign_link.short_description = "کمپین"

    def influencer_link(self, obj):
        influencer = obj.campaign_influencer.channel.influencer
        url = reverse("admin:influencers_influencerprofile_change", args=[influencer.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, influencer.full_name)

    influencer_link.short_description = "اینفلوئنسر"

    def advertiser_link(self, obj):
        advertiser = obj.campaign_influencer.campaign.advertiser
        url = reverse("admin:advertisers_advertiserprofile_change", args=[advertiser.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, advertiser.business_name)

    advertiser_link.short_description = "تبلیغ‌دهنده"

    def status_badge(self, obj):
        colors = {'pending': '#fdbc31', 'approved': '#07c98b', 'rejected': '#f23c49'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )

    status_badge.short_description = "وضعیت"

    def auto_check_summary(self, obj):
        """خلاصه بررسی خودکار برای نمایش در لیست"""
        details = obj.auto_check_details or {}
        if not details:
            return mark_safe('<span style="color: #6c757d;">—</span>')
        score = details.get('overall_score')
        if score is not None:
            color = "#07c98b" if score >= 70 else "#fdbc31" if score >= 40 else "#f23c49"
            return format_html('<span style="color: {}; font-weight: bold;">{}%</span>', color, score)
        return "✔️" if details.get('approved') else "❌"

    auto_check_summary.short_description = "نتیجه خودکار"

    # ---------- فیلدهای فقط خواندنی در فرم ----------
    def post_link_display(self, obj):
        return format_html('<a href="{}" target="_blank" style="word-break: break-all;">{}</a>', obj.post_link,
                           obj.post_link)

    post_link_display.short_description = "لینک پست"

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<div style="background: #1a1a2e; padding: 10px; border-radius: 12px; display: inline-block;">'
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 200px; border-radius: 8px; border: 1px solid #333;" /></a>'
                '<div style="margin-top: 8px;"><a href="{}" download class="button" style="background: #fd5631; color: #fff; padding: 4px 12px; border-radius: 6px; text-decoration: none; font-size: 12px;">📥 دانلود فایل</a></div>'
                '</div>',
                obj.screenshot.url, obj.screenshot.url, obj.screenshot.url
            )
        return "-"

    screenshot_preview.short_description = "اسکرین‌شات"

    def campaign_details(self, obj):
        campaign = obj.campaign_influencer.campaign
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">'
            '<strong>نام:</strong> {}<br><strong>شروع:</strong> {}<br><strong>پایان:</strong> {}<br><strong>وضعیت:</strong> {}</div>',
            campaign.name,
            campaign.start_date.strftime("%Y/%m/%d"),
            campaign.end_date.strftime("%Y/%m/%d"),
            campaign.get_status_display()
        )

    campaign_details.short_description = "جزئیات کمپین"

    def influencer_details(self, obj):
        channel = obj.campaign_influencer.channel
        province_name = channel.province.name if channel.province else "-"
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">'
            '<strong>کانال:</strong> {}<br><strong>آیدی:</strong> {}<br><strong>پلتفرم:</strong> {}<br><strong>فالوور:</strong> {}<br><strong>استان:</strong> {}</div>',
            channel.channel_name, channel.channel_id, channel.platform.name,
            channel.followers_formatted(), province_name
        )

    influencer_details.short_description = "جزئیات اینفلوئنسر"

    def advertiser_details(self, obj):
        advertiser = obj.campaign_influencer.campaign.advertiser
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">'
            '<strong>کسب‌وکار:</strong> {}<br><strong>وبسایت:</strong> {}</div>',
            advertiser.business_name, advertiser.website or "-"
        )

    advertiser_details.short_description = "جزئیات تبلیغ‌دهنده"

    def auto_check_details_display(self, obj):
        import json
        details = obj.auto_check_details or {}
        if not details:
            return "هنوز بررسی خودکاری انجام نشده است."
        html = '<pre style="background:#2d2d2d; padding:10px; border-radius:8px; color:#f8f8f2; overflow-x:auto;">'
        html += json.dumps(details, indent=2, ensure_ascii=False)
        html += '</pre>'
        return mark_safe(html)

    auto_check_details_display.short_description = "جزئیات بررسی خودکار"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ثبت"

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین بروزرسانی"

    # ---------- اکشن‌ها ----------
    def mark_as_approved(self, request, queryset):
        updated = 0
        for report in queryset:
            if report.status != 'approved':
                approve_influencer_report_service(report)
                updated += 1
        self.message_user(request, f"{updated} گزارش تأیید، نوتیفیکیشن ارسال و پرداخت انجام شد.")

    mark_as_approved.short_description = "تأیید گزارش‌های انتخاب شده"

    def mark_as_rejected(self, request, queryset):
        updated = 0
        for report in queryset:
            if report.status != 'rejected':
                reject_influencer_report_service(report, reason="رد شده توسط ادمین")
                updated += 1
        self.message_user(request, f"{updated} گزارش رد و نوتیفیکیشن ارسال شد.")

    mark_as_rejected.short_description = "رد گزارش‌های انتخاب شده"

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f"{updated} گزارش به حالت در انتظار برگشت.")

    mark_as_pending.short_description = "برگشت به حالت در انتظار"

    # ---------- مدیریت دسترسی منطقه‌ای ----------
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            qs = qs.filter(campaign_influencer__channel__province=request.user.province)
        return qs.select_related(
            'campaign_influencer',
            'campaign_influencer__campaign',
            'campaign_influencer__campaign__advertiser',
            'campaign_influencer__channel',
            'campaign_influencer__channel__province',
            'campaign_influencer__channel__platform',
            'campaign_influencer__channel__influencer',
        )

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign_influencer.channel.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign_influencer.channel.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if change:
            old_status = CampaignReport.objects.get(pk=obj.pk).status
            new_status = obj.status
            super().save_model(request, obj, form, change)
            if old_status != new_status:
                if new_status == 'approved':
                    approve_influencer_report_service(obj)
                elif new_status == 'rejected':
                    reason = obj.admin_notes if obj.admin_notes else "رد شده پس از بررسی مجدد"
                    reject_influencer_report_service(obj, reason=reason)
        else:
            super().save_model(request, obj, form, change)
