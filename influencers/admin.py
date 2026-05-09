from core.admin_utils import format_datetime, RegionalFilterAdminMixin
from django_jalali.admin.filters import JDateFieldListFilter
from django.utils.safestring import mark_safe
from accounts.models import CustomUser
from .models import InfluencerProfile
from location.models import Province
from django.urls import reverse
from .inline_admin import *


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

    inlines = [InfluencerChannelInline,]

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
                from django.core.exceptions import ValidationError
                raise ValidationError('شما فقط می‌توانید اینفلوئنسرهای استان خودتان را مدیریت کنید.')
        super().save_model(request, obj, form, change)


@admin.register(InfluencerChannel)
class InfluencerChannelAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "channel_display",
        "influencer",
        "platform",
        "is_active",
        "status",
        "formatted_created_at",
    )
    list_filter = ('platform', 'province', "is_active", 'created_at',)
    search_fields = ("channel_id", "channel_name", "influencer__full_name", "influencer__user__phone_number",)
    autocomplete_fields = ("influencer", "platform", "category", "province", "city",)
    ordering = ("created_at", 'followers_count')
    inlines = [InfluencerServiceRateInline, InfluencerReviewInline]
    actions = ['mark_as_approved', 'mark_as_rejected']
    readonly_fields = (
        "followers_formatted_display", "formatted_created_at", "formatted_updated_at", "rates_count_display",)

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
            "fields": ("province", "city"),
            "classes": ("collapse",)
        }),
        ("دسته‌بندی", {
            "fields": ("category",),
            "classes": ("collapse",)
        }),
        ("آمار و تصویر", {
            "fields": ("followers_count", "avatar"),
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

    def channel_display(self, obj):
        return obj.channel_id

    channel_display.short_description = "آیدی کانال"

    def channel_province(self, obj):
        """استان کانال (از فیلد province خود مدل)"""
        return obj.province.name if obj.province else "-"

    channel_province.short_description = "استان کانال"
    channel_province.admin_order_field = "province__name"

    def location_city(self, obj):
        """نمایش شهر کانال"""
        return obj.city.name if obj.city else "-"

    location_city.short_description = "شهر"
    location_city.admin_order_field = "city__name"

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
        """فقط کانال‌هایی که استانشون با استان مدیر یکی هست"""
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            return qs.filter(province=request.user.province)

        return qs

    def has_change_permission(self, request, obj=None):
        """بررسی دسترسی ویرایش بر اساس استان کانال"""
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """بررسی دسترسی حذف بر اساس استان کانال"""
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """محدود کردن انتخاب‌ها در فرم"""
        if db_field.name == 'province' and request.user.is_regional_manager:
            kwargs['queryset'] = Province.objects.filter(id=request.user.province.id)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """موقع ذخیره، استان کانال رو خودکار ست کن برای مدیر استانی"""
        if request.user.is_regional_manager and request.user.province:
            obj.province = request.user.province
        super().save_model(request, obj, form, change)

    def mark_as_approved(modeladmin, request, queryset):
        queryset.update(status='approved')

    mark_as_approved.short_description = "تایید کانال‌های انتخاب شده"

    def mark_as_rejected(modeladmin, request, queryset):
        queryset.update(status='rejected')

    mark_as_rejected.short_description = "رد کانال‌های انتخاب شده"


@admin.register(InfluencerServiceRate)
class InfluencerServiceRateAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
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
            kwargs['queryset'] = InfluencerChannel.objects.filter(
                province=request.user.province
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(InfluencerReview)
class InfluencerReviewAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
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
        from core.admin_utils import format_datetime
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


@admin.register(CampaignReport)
class CampaignReportAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
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
    )

    fieldsets = (
        ("اطلاعات سفارش", {
            "fields": ("campaign_influencer", "campaign_details", "influencer_details", "advertiser_details",)
        }),
        ("گزارش ارسالی", {
            "fields": ("post_link_display", "screenshot_preview",)
        }),
        ("بررسی خودکار", {
            "fields": ("link_valid", "hashtag_match_percent", "text_match_percent",),
            "classes": ("collapse",)
        }),
        ("بررسی دستی", {
            "fields": ("status", "admin_notes",),
            "classes": ("collapse",)
        }),
        ("تاریخ ها", {
            "fields": ("formatted_created_at", "formatted_updated_at",),
            "classes": ("collapse",)
        }),
    )

    actions = ["mark_as_approved", "mark_as_rejected", "mark_as_pending"]

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
        colors = {'pending': '#fdbc31', 'approved': '#07c98b', 'rejected': '#f23c49', 'partial': '#17a2b8'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px;">{}</span>',
            color, obj.get_status_display())

    status_badge.short_description = "وضعیت"

    def match_percentage(self, obj):
        if obj.link_valid and obj.text_match_percent > 0:
            total = (obj.text_match_percent + obj.hashtag_match_percent) / 2
            color = "#07c98b" if total >= 70 else "#fdbc31" if total >= 40 else "#f23c49"
            return format_html('<span style="color: {}; font-weight: bold;">{}%</span>', color, int(total))
        elif obj.link_valid:
            return mark_safe('<span style="color: #fdbc31;">لینک OK</span>')
        return mark_safe('<span style="color: #f23c49;">نامعتبر</span>')

    match_percentage.short_description = "تطابق"

    def post_link_display(self, obj):
        return format_html('<a href="{}" target="_blank" style="word-break: break-all;">{}</a>', obj.post_link,
                           obj.post_link)

    post_link_display.short_description = "لینک پست"

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<div style="background: #1a1a2e; padding: 10px; border-radius: 12px; display: inline-block;"><a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 200px; border-radius: 8px; border: 1px solid #333;" /></a><div style="margin-top: 8px;"><a href="{}" download class="button" style="background: #fd5631; color: #fff; padding: 4px 12px; border-radius: 6px; text-decoration: none; font-size: 12px;">📥 دانلود فایل</a></div></div>',
                obj.screenshot.url, obj.screenshot.url, obj.screenshot.url)
        return "-"

    screenshot_preview.short_description = "اسکرین‌شات"

    def campaign_details(self, obj):
        campaign = obj.campaign_influencer.campaign
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;"><strong>نام:</strong> {}<br><strong>شروع:</strong> {}<br><strong>پایان:</strong> {}<br><strong>وضعیت:</strong> {}</div>',
            campaign.name, obj.campaign_influencer.campaign.start_date.strftime("%Y/%m/%d %H:%M"),
            obj.campaign_influencer.campaign.end_date.strftime("%Y/%m/%d %H:%M"), campaign.get_status_display())

    campaign_details.short_description = "جزئیات کمپین"

    def influencer_details(self, obj):
        channel = obj.campaign_influencer.channel
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;"><strong>کانال:</strong> {}<br><strong>آیدی:</strong> {}<br><strong>پلتفرم:</strong> {}<br><strong>فالوور:</strong> {}<br><strong>استان کانال:</strong> {}</div>',
            channel.channel_name, channel.channel_id, channel.platform.name, channel.followers_formatted(),
            channel.province.name if channel.province else "-")

    influencer_details.short_description = "جزئیات اینفلوئنسر"

    def advertiser_details(self, obj):
        advertiser = obj.campaign_influencer.campaign.advertiser
        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;"><strong>کسب‌وکار:</strong> {}<br><strong>وبسایت:</strong> {}</div>',
            advertiser.business_name, advertiser.website or "-")

    advertiser_details.short_description = "جزئیات تبلیغ‌دهنده"

    def formatted_created_at(self, obj):
        from core.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ثبت"

    def formatted_updated_at(self, obj):
        from core.admin_utils import format_datetime
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین بروزرسانی"

    def mark_as_approved(self, request, queryset):
        updated = 0
        for report in queryset:
            if report.status != 'approved':
                report.status = 'approved'
                report.save()
                updated += 1
        self.message_user(request, f"{updated} گزارش تأیید و پرداخت انجام شد.")

    mark_as_approved.short_description = "تأیید گزارش‌های انتخاب شده"

    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f"{updated} گزارش رد شد.")

    mark_as_rejected.short_description = "رد گزارش‌های انتخاب شده"

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f"{updated} گزارش به حالت در انتظار برگشت.")

    mark_as_pending.short_description = "برگشت به حالت در انتظار"

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
