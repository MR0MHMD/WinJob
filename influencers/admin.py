# influencers/admin.py

from django.utils.safestring import mark_safe
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django_jalali.admin.filters import JDateFieldListFilter
from core.admin_utils import format_datetime
from .models import (
    InfluencerProfile,
    InfluencerChannel,
    InfluencerServiceRate,
    InfluencerReview,
    CampaignReport
)


# =========================
# Service Rate Inline
# =========================

class InfluencerServiceRateInline(admin.TabularInline):
    model = InfluencerServiceRate
    extra = 0

    fields = (
        "ad_type",
        "price",
        "formatted_price",
        "is_active",
        "created_at",
    )

    readonly_fields = (
        "formatted_price",
        "created_at",
    )

    autocomplete_fields = (
        "ad_type",
    )


# =========================
# Channel Inline
# =========================

class InfluencerChannelInline(admin.TabularInline):
    model = InfluencerChannel
    extra = 0

    fields = (
        "platform",
        "channel_id",
        "followers_count",
        "followers_formatted_display",
        "is_active",
        "created_at",
    )

    readonly_fields = (
        "followers_formatted_display",
        "created_at",
    )

    show_change_link = True

    def followers_formatted_display(self, obj):
        return obj.followers_formatted()

    followers_formatted_display.short_description = "فالوورها"


# =========================
# review Inline
# =========================

class InfluencerReviewInline(admin.TabularInline):
    model = InfluencerReview
    extra = 0

    fields = (
        "advertiser",
        "campaign_booking",
        "rating",
        "comment",
        "created_at",
    )

    readonly_fields = (
        "created_at",
    )

    autocomplete_fields = (
        "advertiser",
        "campaign_booking",
    )

    show_change_link = True


# =========================
# Influencer Profile
# =========================

@admin.register(InfluencerProfile)
class InfluencerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
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

    inlines = [InfluencerChannelInline, InfluencerReviewInline]

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
            )
        }),

        ("تاریخ ها", {
            "fields": (
                "formatted_created_at",
                "formatted_updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    # ---------- helpers ----------

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

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_created_at.short_description = "تاریخ ایجاد"
    formatted_updated_at.short_description = "آخرین ویرایش"


# =========================
# Channel Admin
# =========================

@admin.register(InfluencerChannel)
class InfluencerChannelAdmin(admin.ModelAdmin):
    list_display = (
        "channel_display",
        "influencer",
        "platform",
        "followers_formatted_display",
        "location",
        "rates_count",
        "is_active",
        "formatted_created_at",
    )

    list_filter = (
        "platform",
        "is_active",
        ("created_at", JDateFieldListFilter),
    )

    search_fields = (
        "channel_id",
        "influencer__full_name",
        "influencer__user__phone_number",
    )

    autocomplete_fields = (
        "influencer",
        "platform",
        "category",
        "province",
        "city",
    )

    inlines = [
        InfluencerServiceRateInline
    ]

    readonly_fields = (
        "followers_formatted_display",
        "formatted_created_at",
        "formatted_updated_at",
        "rates_count_display",
    )

    def channel_display(self, obj):
        return obj.channel_id

    channel_display.short_description = "آیدی کانال"

    def location(self, obj):
        if obj.city:
            return f"{obj.city.name} - {obj.province.name}"
        if obj.province:
            return obj.province.name
        return "-"

    location.short_description = "موقعیت"

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

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_created_at.short_description = "تاریخ ایجاد"
    formatted_updated_at.short_description = "آخرین ویرایش"


# =========================
# Service Rate Admin
# =========================

@admin.register(InfluencerServiceRate)
class InfluencerServiceRateAdmin(admin.ModelAdmin):
    list_display = (
        "channel",
        "influencer",
        "ad_type",
        "formatted_price",
        "is_active",
        "formatted_created_at",
    )

    list_filter = (
        "is_active",
        "ad_type",
        "channel__platform",
    )

    search_fields = (
        "channel__channel_id",
        "channel__influencer__full_name",
        "ad_type__name",
    )

    autocomplete_fields = (
        "channel",
        "ad_type",
    )

    readonly_fields = (
        "formatted_price",
        "formatted_created_at",
        "formatted_updated_at",
    )

    def influencer(self, obj):
        return obj.channel.influencer

    influencer.short_description = "اینفلوئنسر"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_created_at.short_description = "تاریخ ایجاد"
    formatted_updated_at.short_description = "آخرین ویرایش"


# =========================
# Influencer Review Admin
# =========================

@admin.register(InfluencerReview)
class InfluencerReviewAdmin(admin.ModelAdmin):
    list_display = (
        "influencer",
        "advertiser",
        "rating",
        "campaign_booking",
        "short_comment",
        "formatted_created_at",
    )

    list_filter = (
        "rating",
        ("created_at", JDateFieldListFilter),
    )

    search_fields = (
        "influencer__full_name",
        "advertiser__user__phone_number",
        "advertiser__user__nickname",
        "comment",
    )

    autocomplete_fields = (
        "influencer",
        "advertiser",
        "campaign_booking",
    )

    readonly_fields = (
        "formatted_created_at",
    )

    fieldsets = (

        ("اطلاعات اصلی", {
            "fields": (
                "influencer",
                "advertiser",
                "campaign_booking",
            )
        }),

        ("امتیاز و نظر", {
            "fields": (
                "rating",
                "comment",
            )
        }),

        ("تاریخ", {
            "fields": (
                "formatted_created_at",
            ),
            "classes": ("collapse",)
        }),
    )

    # ---------- helpers ----------

    def short_comment(self, obj):
        if not obj.comment:
            return "-"
        return obj.comment[:40]

    short_comment.short_description = "نظر"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ثبت"


# =========================
# Inline برای نمایش در CampaignInfluencer Admin
# =========================

class CampaignReportInline(admin.StackedInline):
    """
    اینلاین برای نمایش گزارش در صفحه جزئیات CampaignInfluencer
    """
    model = CampaignReport
    extra = 0
    can_delete = False
    max_num = 1
    min_num = 0

    fields = (
        "post_link",
        "screenshot_preview",
        "screenshot",
        "link_valid",
        "hashtag_match_percent",
        "text_match_percent",
        "status",
        "admin_notes",
        "created_at",
        "updated_at",
    )

    readonly_fields = (
        "screenshot_preview",
        "created_at",
        "updated_at",
    )

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" width="150" height="auto" style="border-radius: 8px;" />'
                '</a>',
                obj.screenshot.url,
                obj.screenshot.url
            )
        return "-"

    screenshot_preview.short_description = "پیش‌نمایش اسکرین‌شات"


# =========================
# Report Admin (اصلی)
# =========================

@admin.register(CampaignReport)
class CampaignReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "campaign_link",
        "influencer_link",
        "advertiser_link",
        "status_badge",
        "match_percentage",
        "formatted_created_at",
    )

    list_filter = (
        "status",
        "link_valid",
        ("created_at", JDateFieldListFilter),
    )

    search_fields = (
        "campaign_influencer__campaign__name",
        "campaign_influencer__channel__channel_id",
        "campaign_influencer__channel__influencer__full_name",
        "campaign_influencer__campaign__advertiser__business_name",
        "post_link",
        "admin_notes",
    )

    autocomplete_fields = (
        "campaign_influencer",
    )

    readonly_fields = (
        "screenshot_preview",
        "post_link_display",
        "formatted_created_at",
        "formatted_updated_at",
        "campaign_details",
        "influencer_details",
        "advertiser_details",
    )

    fieldsets = (

        ("اطلاعات سفارش", {
            "fields": (
                "campaign_influencer",
                "campaign_details",
                "influencer_details",
                "advertiser_details",
            )
        }),

        ("گزارش ارسالی", {
            "fields": (
                "post_link_display",
                "screenshot_preview",
            )
        }),

        ("بررسی خودکار", {
            "fields": (
                "link_valid",
                "hashtag_match_percent",
                "text_match_percent",
            ),
            "classes": ("collapse",)
        }),

        ("بررسی دستی", {
            "fields": (
                "status",
                "admin_notes",
            )
        }),

        ("تاریخ ها", {
            "fields": (
                "formatted_created_at",
                "formatted_updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    actions = ["mark_as_approved", "mark_as_rejected", "mark_as_pending"]

    # ========== نمایش‌های سفارشی ==========

    def campaign_link(self, obj):
        """لینک به کمپین"""
        campaign = obj.campaign_influencer.campaign
        url = reverse("admin:campaigns_campaign_change", args=[campaign.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, campaign.name[:40])

    campaign_link.short_description = "کمپین"

    def influencer_link(self, obj):
        """لینک به اینفلوئنسر"""
        influencer = obj.campaign_influencer.channel.influencer
        url = reverse("admin:influencers_influencerprofile_change", args=[influencer.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, influencer.full_name)

    influencer_link.short_description = "اینفلوئنسر"

    def advertiser_link(self, obj):
        """لینک به تبلیغ‌دهنده"""
        advertiser = obj.campaign_influencer.campaign.advertiser
        url = reverse("admin:advertisers_advertiserprofile_change", args=[advertiser.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, advertiser.business_name)

    advertiser_link.short_description = "تبلیغ‌دهنده"

    def status_badge(self, obj):
        """بج وضعیت رنگی"""
        colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'partial': 'info',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span style="background-color: var(--fi-{}); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = "وضعیت"

    def match_percentage(self, obj):
        """درصد تطابق کلی"""
        if obj.link_valid and obj.text_match_percent > 0:
            total = (obj.text_match_percent + obj.hashtag_match_percent) / 2
            color = "#07c98b" if total >= 70 else "#fdbc31" if total >= 40 else "#f23c49"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}%</span>',
                color,
                int(total)
            )
        elif obj.link_valid:
            return mark_safe('<span style="color: #fdbc31;">لینک OK</span>')
        return mark_safe('<span style="color: #f23c49;">نامعتبر</span>')

    match_percentage.short_description = "تطابق"

    def post_link_display(self, obj):
        """نمایش لینک پست به صورت قابل کلیک"""
        return format_html(
            '<a href="{}" target="_blank" style="word-break: break-all;">{}</a>',
            obj.post_link,
            obj.post_link
        )

    post_link_display.short_description = "لینک پست"

    def screenshot_preview(self, obj):
        """پیش‌نمایش اسکرین‌شات"""
        if obj.screenshot:
            return format_html(
                '<div style="background: #1a1a2e; padding: 10px; border-radius: 12px; display: inline-block;">'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 300px; max-height: 200px; border-radius: 8px; border: 1px solid '
                '#333;" />'
                '</a>'
                '<div style="margin-top: 8px;">'
                '<a href="{}" download class="button" style="background: #fd5631; color: #fff; padding: 4px 12px; '
                'border-radius: 6px; text-decoration: none; font-size: 12px;">'
                '📥 دانلود فایل'
                '</a>'
                '</div>'
                '</div>',
                obj.screenshot.url,
                obj.screenshot.url,
                obj.screenshot.url
            )
        return "-"

    screenshot_preview.short_description = "اسکرین‌شات"

    def campaign_details(self, obj):
        """نمایش جزئیات کمپین"""
        campaign = obj.campaign_influencer.campaign
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">'
            '<strong>نام:</strong> {}<br>'
            '<strong>شروع:</strong> {}<br>'
            '<strong>پایان:</strong> {}<br>'
            '<strong>وضعیت:</strong> {}'
            '</div>',
            campaign.name,
            obj.campaign_influencer.campaign.start_date.strftime("%Y/%m/%d %H:%M"),
            obj.campaign_influencer.campaign.end_date.strftime("%Y/%m/%d %H:%M"),
            campaign.get_status_display()
        )

    campaign_details.short_description = "جزئیات کمپین"

    def influencer_details(self, obj):
        """نمایش جزئیات اینفلوئنسر"""
        channel = obj.campaign_influencer.channel
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">'
            '<strong>کانال:</strong> {}<br>'
            '<strong>آیدی:</strong> {}<br>'
            '<strong>پلتفرم:</strong> {}<br>'
            '<strong>فالوور:</strong> {}'
            '</div>',
            channel.channel_name,
            channel.channel_id,
            channel.platform.name,
            channel.followers_formatted()
        )

    influencer_details.short_description = "جزئیات اینفلوئنسر"

    def advertiser_details(self, obj):
        """نمایش جزئیات تبلیغ‌دهنده"""
        advertiser = obj.campaign_influencer.campaign.advertiser
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">'
            '<strong>کسب‌وکار:</strong> {}<br>'
            '<strong>وبسایت:</strong> {}<br>'
            '</div>',
            advertiser.business_name,
            advertiser.website or "-"
        )

    advertiser_details.short_description = "جزئیات تبلیغ‌دهنده"

    def formatted_created_at(self, obj):
        from core.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    def formatted_updated_at(self, obj):
        from core.admin_utils import format_datetime
        return format_datetime(obj.updated_at)

    formatted_created_at.short_description = "تاریخ ثبت"
    formatted_updated_at.short_description = "آخرین بروزرسانی"

    # ========== اکشن‌های گروهی ==========

    def mark_as_approved(self, request, queryset):
        """تغییر وضعیت به تأیید شده"""
        updated = queryset.update(status='approved')
        self.message_user(request, f"{updated} گزارش تأیید شد.")

    mark_as_approved.short_description = "تأیید گزارش‌های انتخاب شده"

    def mark_as_rejected(self, request, queryset):
        """تغییر وضعیت به رد شده"""
        updated = queryset.update(status='rejected')
        self.message_user(request, f"{updated} گزارش رد شد.")

    mark_as_rejected.short_description = "رد گزارش‌های انتخاب شده"

    def mark_as_pending(self, request, queryset):
        """تغییر وضعیت به در انتظار"""
        updated = queryset.update(status='pending')
        self.message_user(request, f"{updated} گزارش به حالت در انتظار برگشت.")

    mark_as_pending.short_description = "برگشت به حالت در انتظار"
