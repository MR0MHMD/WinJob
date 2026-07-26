# campaigns/admin
from campaigns.services.campaigns_notifications import approve_campaign_by_admin, reject_campaign_by_admin
from .models import ContentType, Campaign, CampaignContent, CampaignTrackingLink
from django_jalali.admin.filters import JDateFieldListFilter
from influencers.inline_admin import CampaignReportInline
from core.utils.admin_utils import RegionalFilterAdminMixin
from influencers.models import InfluencerChannel
from advertisers.models import AdvertiserProfile
from django.utils.safestring import mark_safe
from core.utils.admin_utils import format_datetime
from django.utils.html import format_html
from django.urls import reverse
from .inline_admin import *
import os


@admin.register(Campaign)
class CampaignAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    inlines = [CampaignInfluencerInline]

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

    autocomplete_fields = ("advertiser", "platform", "content_type")

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


@admin.register(CampaignInfluencer)
class CampaignInfluencerAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
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

    autocomplete_fields = ("campaign", "channel", "service_rate")

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
        url = reverse("admin:influencers_influencerchannel_change", args=[obj.channel.id])
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
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_paid_at(self, obj):
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.paid_at) if obj.paid_at else "-"

    formatted_paid_at.short_description = "تاریخ پرداخت"

    # ========== اکشن‌ها ==========

    def mark_as_accepted(self, request, queryset):
        updated = queryset.update(status=CampaignInfluencer.Status.ACCEPTED)
        self.message_user(request, f"{updated} رزرو پذیرفته شد.")

    mark_as_accepted.short_description = "پذیرفتن رزروهای انتخاب شده"

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status=CampaignInfluencer.Status.COMPLETED)
        self.message_user(request, f"{updated} رزرو انجام شد.")

    mark_as_completed.short_description = "انجام شدن رزروهای انتخاب شده"

    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
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
            kwargs['queryset'] = InfluencerChannel.objects.filter(
                province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ContentType)
class ContentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


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
        url = reverse("admin:influencers_influencerchannel_change", args=[channel.id])
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
