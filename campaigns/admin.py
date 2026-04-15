import os

from django.contrib import admin, messages
from django.utils.html import format_html
from django_jalali.admin.filters import JDateFieldListFilter

from influencers.admin import CampaignReportInline
from .models import (
    ContentType,
    AdType,
    Campaign,
    CampaignContent,
    CampaignInfluencer,
    CampaignInvoice,
    Coupon,
    Payment,
)


# -----------------------------
# Campaign Influencer Inline
# -----------------------------

class CampaignInfluencerInline(admin.TabularInline):
    model = CampaignInfluencer
    extra = 0
    autocomplete_fields = ("channel", "service_rate")
    fields = (
        "channel",
        "service_rate",
        "price",
        "status",
        "created_at",
    )
    readonly_fields = ("created_at",)


# -----------------------------
# CampaignInfluencer
# -----------------------------


@admin.register(CampaignInfluencer)
class CampaignInfluencerAdmin(admin.ModelAdmin):
    search_fields = (
        "campaign__title",
        "influencer_channel__channel_id",
    )

    inlines = [CampaignReportInline]


# -----------------------------
# ContentType
# -----------------------------

@admin.register(ContentType)
class ContentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


# -----------------------------
# AdType
# -----------------------------

@admin.register(AdType)
class AdTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "platform", "slug", "is_active")
    list_filter = ("platform", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


# -----------------------------
# Coupon
# -----------------------------

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "scope",
        "discount_type",
        "value",
        "used_count",
        "max_uses",
        "expires_at",
        "is_active",
    )

    list_filter = (
        "scope",
        "discount_type",
        "is_active",
        ("expires_at", JDateFieldListFilter),
    )

    search_fields = (
        "code",
        "channel__name",
    )

    readonly_fields = (
        "used_count",
    )

    fieldsets = (
        ("اطلاعات کد", {
            "fields": (
                "code",
                "scope",
                "discount_type",
                "value",
                "is_active",
            )
        }),
        ("محدودیت‌ها", {
            "fields": (
                "max_uses",
                "used_count",
                "expires_at",
            )
        }),
        ("محدوده استفاده", {
            "fields": (
                "channel",
                "team",
            ),
            "classes": ("collapse",)
        }),
    )


# -----------------------------
# Campaign Admin
# -----------------------------

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    inlines = [CampaignInfluencerInline]

    list_display = (
        "name",
        "advertiser",
        "status",
        "influencers_display",
        "invoice_total",
        "payable_amount",
        "created_at",
    )

    list_filter = (
        "status",
        ("created_at", JDateFieldListFilter),
    )

    search_fields = (
        "name",
        "advertiser__user__username",
    )

    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "updated_at",
        "influencers_display",
        "invoice_total",
        "payable_amount",
        "commission_display",
        "influencer_cost_display",
        "content_cost_display",
    )

    fieldsets = (
        ("اطلاعات کمپین", {
            "fields": (
                "name",
                "advertiser",
                "description",
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
            "fields": (
                "status",
            )
        }),

        ("اینفلوئنسرها", {
            "fields": (
                "influencers_display",
            ),
            "classes": ("collapse",)
        }),

        ("اطلاعات مالی", {
            "fields": (
                "influencer_cost_display",
                "content_cost_display",
                "commission_display",
                "invoice_total",
                "discount_amount",
                "payable_amount",
                "coupon",
            ),
            "classes": ("collapse",)
        }),
    )

    actions = ["approve_campaign", "reject_campaign"]

    # -------------------------
    # Influencer display
    # -------------------------

    def influencers_display(self, obj):
        bookings = obj.influencer_bookings.all()
        if not bookings:
            return "-"

        names = [
            str(b.channel)
            for b in bookings
        ]
        return ", ".join(names)

    influencers_display.short_description = "اینفلوئنسرها"

    # -------------------------
    # Invoice helpers
    # -------------------------

    def invoice_total(self, obj):
        if hasattr(obj, "invoice"):
            return obj.invoice.total_amount
        return "-"

    invoice_total.short_description = "مبلغ کل"

    def payable_amount(self, obj):
        if hasattr(obj, "invoice"):
            return obj.invoice.payable_amount
        return "-"

    payable_amount.short_description = "قابل پرداخت"

    def commission_display(self, obj):
        if hasattr(obj, "invoice"):
            return obj.invoice.commission
        return "-"

    commission_display.short_description = "کمیسیون"

    def influencer_cost_display(self, obj):
        if hasattr(obj, "invoice"):
            return obj.invoice.influencer_cost
        return "-"

    influencer_cost_display.short_description = "هزینه اینفلوئنسر"

    def content_cost_display(self, obj):
        if hasattr(obj, "invoice"):
            return obj.invoice.content_cost
        return "-"

    content_cost_display.short_description = "هزینه تولید محتوا"

    # -------------------------
    # Actions
    # -------------------------

    def approve_campaign(self, request, queryset):
        updated = queryset.update(status=Campaign.Status.APPROVED)
        self.message_user(request, f"{updated} کمپین تایید شد.")

    approve_campaign.short_description = "تایید کمپین"

    def reject_campaign(self, request, queryset):
        updated = queryset.update(status=Campaign.Status.CANCELLED)
        self.message_user(request, f"{updated} کمپین رد شد.")

    reject_campaign.short_description = "رد کمپین"


# -----------------------------
# CampaignContent
# -----------------------------


@admin.register(CampaignContent)
class CampaignContentAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "media_preview",
        "utm_enabled",
        "created_at",
    )

    search_fields = (
        "campaign__title",
        "caption",
    )

    list_filter = (
        "utm_enabled",
        "created_at",
    )

    readonly_fields = (
        "media_preview",
        "created_at",
        "updated_at",
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
                "created_at",
                "updated_at",
            )
        }),

    )

    def media_preview(self, obj):
        if not obj.media:
            return "_"

        url = obj.media.url
        ext = os.path.splitext(url)[1].lower()

        image_ext = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        video_ext = ['.mp4', '.webm', '.ogg']

        if ext in image_ext:
            return format_html('<img style="width: 50px; border-radius:6px;" src="{}">', url)
        elif ext in video_ext:
            return format_html("<a href='{}' target='blank'>مشاهده فایل</a>", url)
        else:
            return "فایل ناشناخته"



    media_preview.allow_tags = True
    media_preview.short_description = "فایل"


# -----------------------------
# Campaign Invoice
# -----------------------------

@admin.register(CampaignInvoice)
class CampaignInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "influencer_cost",
        "content_cost",
        "commission",
        "total_amount",
        "payable_amount",
        "is_paid",
        "created_at",
    )

    list_filter = (
        "is_paid",
        ("created_at", JDateFieldListFilter),
    )

    search_fields = (
        "campaign__name",
    )


# -----------------------------
# Payment
# -----------------------------

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "invoice",
        "amount",
        "status",
        "ref_id",
        "created_at",
    )

    list_filter = (
        "status",
        ("created_at", JDateFieldListFilter),
    )

    search_fields = (
        "user__username",
        "ref_id",
    )


from .models import CampaignTrackingLink, CampaignClick


# -----------------------------
# CampaignClick Inline
# -----------------------------

class CampaignClickInline(admin.TabularInline):
    model = CampaignClick
    extra = 0
    readonly_fields = (
        "ip_address",
        "user_agent",
        "created_at",
    )
    can_delete = False
    ordering = ("-created_at",)


# -----------------------------
# CampaignTrackingLink
# -----------------------------

@admin.register(CampaignTrackingLink)
class CampaignTrackingLinkAdmin(admin.ModelAdmin):

    list_display = (
        "campaign",
        "influencer_channel",
        "tracking_code",
        "clicks",
        "unique_clicks",
        "created_at",
    )

    search_fields = (
        "campaign_influencer__campaign__name",
        "campaign_influencer__channel__channel_id",
        "campaign_influencer__tracking_code",
    )

    list_filter = (
        "created_at",
    )

    readonly_fields = (
        "campaign_influencer",
        "clicks",
        "unique_clicks",
        "created_at",
    )

    inlines = [
        CampaignClickInline
    ]

    def campaign(self, obj):
        return obj.campaign_influencer.campaign

    campaign.short_description = "کمپین"

    def influencer_channel(self, obj):
        return obj.campaign_influencer.channel

    influencer_channel.short_description = "کانال"

    def tracking_code(self, obj):
        return obj.campaign_influencer.tracking_code

    tracking_code.short_description = "کد ردیابی"


# -----------------------------
# CampaignClick
# -----------------------------

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
