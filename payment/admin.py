# payment/admin
from .models import CampaignInvoice, Coupon, Payment, Transaction, Wallet
from core.admin_utils import RegionalFilterAdminMixin, format_datetime
from django_jalali.admin.filters import JDateFieldListFilter
from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse



class TransactionInline(admin.TabularInline):
    """نمایش تراکنش‌های کاربر در صفحه ادمین"""
    model = Transaction
    extra = 0
    can_delete = False
    max_num = 5
    fields = ('amount', 'type', 'status', 'sign_display', 'formatted_created_at')
    readonly_fields = ('amount', 'type', 'status', 'sign_display', 'formatted_created_at')
    classes = ['collapse']

    def sign_display(self, obj):
        return obj.sign_display

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    sign_display.short_description = "مبلغ"
    formatted_created_at.short_description = "تاریخ"


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


@admin.register(CampaignInvoice)
class CampaignInvoiceAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        'id',
        "campaign_link",
        "payable_amount",
        "is_paid",
        "formatted_created_at",
    )

    list_filter = (
        "is_paid",
        ("created_at", JDateFieldListFilter),
        "campaign__advertiser__user__province",  # فیلتر بر اساس استان تبلیغ‌دهنده
    )

    search_fields = (
        "campaign__name",
        "campaign__advertiser__business_name",
        "campaign__advertiser__user__phone_number",
    )

    readonly_fields = (
        "campaign",
        "influencer_cost",
        "content_cost",
        "commission",
        "total_amount",
        "payable_amount",
        "discount_amount",
        "formatted_created_at",
    )

    fieldsets = (
        ("اطلاعات کمپین", {
            "fields": (
                "campaign",
            )
        }),
        ("هزینه‌ها", {
            "fields": (
                "influencer_cost",
                "content_cost",
                "commission",
                "discount_amount",
                "total_amount",
                "payable_amount",
            )
        }),
        ("وضعیت", {
            "fields": ("is_paid",)
        }),
        ("تاریخچه", {
            "fields": ("formatted_created_at",),
            "classes": ("collapse",)
        }),
    )

    # ========== متدهای نمایش ==========

    def campaign_link(self, obj):
        """لینک به کمپین"""
        url = reverse("admin:campaigns_campaign_change", args=[obj.campaign.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.campaign.name[:40])

    campaign_link.short_description = "کمپین"
    campaign_link.admin_order_field = "campaign__name"

    def formatted_created_at(self, obj):
        from core.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
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


@admin.register(Payment)
class PaymentAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "invoice_link",
        "campaign_name",
        "user_display",
        "amount_display",
        "status_badge",
        "formatted_created_at",
    )

    list_filter = (
        "status",
        ("created_at", JDateFieldListFilter),
        "invoice__campaign__advertiser__user__province",  # فیلتر بر اساس استان تبلیغ‌دهنده
    )

    search_fields = (
        "user__phone_number",
        "user__nickname",
        "ref_id",
        "invoice__campaign__name",
    )

    readonly_fields = (
        "user",
        "invoice",
        "amount",
        "authority",
        "ref_id",
        "status",
        "formatted_created_at",
        "campaign_link_display",
    )

    fieldsets = (
        ("اطلاعات پرداخت", {
            "fields": (
                "user",
                "invoice",
                "campaign_link_display",
                "amount",
            )
        }),
        ("درگاه پرداخت", {
            "fields": (
                "authority",
                "ref_id",
                "status",
            )
        }),
        ("تاریخچه", {
            "fields": ("formatted_created_at",),
            "classes": ("collapse",)
        }),
    )

    # ========== متدهای نمایش ==========

    def user_display(self, obj):
        """نمایش کاربر با لینک"""
        url = reverse("admin:accounts_customuser_change", args=[obj.user.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    user_display.short_description = "کاربر"
    user_display.admin_order_field = "user__phone_number"

    def invoice_link(self, obj):
        """لینک به فاکتور"""
        url = reverse("admin:campaigns_campaigninvoice_change", args=[obj.invoice.id])
        return format_html('<a href="{}" target="_blank">فاکتور #{}</a>', url, obj.invoice.id)

    invoice_link.short_description = "فاکتور"

    def campaign_name(self, obj):
        """نام کمپین"""
        return obj.invoice.campaign.name

    campaign_name.short_description = "کمپین"
    campaign_name.admin_order_field = "invoice__campaign__name"

    def campaign_link_display(self, obj):
        """لینک به کمپین"""
        url = reverse("admin:campaigns_campaign_change", args=[obj.invoice.campaign.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.invoice.campaign.name)

    campaign_link_display.short_description = "کمپین"

    def amount_display(self, obj):
        """نمایش مبلغ فرمت شده"""
        return f"{obj.amount:,} تومان"

    amount_display.short_description = "مبلغ"

    def status_badge(self, obj):
        """بج وضعیت رنگی"""
        colors = {
            'pending': '#fdbc31',
            'success': '#07c98b',
            'failed': '#f23c49',
        }
        color = colors.get(obj.status, '#6c757d')
        texts = {
            'pending': 'در انتظار',
            'success': 'موفق',
            'failed': 'ناموفق',
        }
        text = texts.get(obj.status, obj.status)
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px;">{}</span>',
            color, text
        )

    status_badge.short_description = "وضعیت"

    def formatted_created_at(self, obj):
        from core.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            # مسیر: payment -> invoice -> campaign -> advertiser -> user -> province
            qs = qs.filter(
                invoice__campaign__advertiser__user__province=request.user.province
            )

        return qs.select_related(
            'user',
            'user__province',
            'invoice',
            'invoice__campaign',
            'invoice__campaign__advertiser',
            'invoice__campaign__advertiser__user',
        )

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.invoice.campaign.advertiser.user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.invoice.campaign.advertiser.user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'balance_display', 'formatted_created_at', 'formatted_updated_at')
    search_fields = ('user__phone_number', 'user__nickname')
    list_select_related = ('user',)
    readonly_fields = ('formatted_created_at', 'formatted_updated_at', 'balance_display')

    def balance_display(self, obj):
        color = '#4CAF50' if obj.balance > 0 else '#f44336'
        return format_html('<span style="color: {}; font-weight: bold;">{} تومان</span>', color, f"{obj.balance:,}")

    balance_display.short_description = 'موجودی'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = 'آخرین بروزرسانی'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user_display',
        'amount_display',
        'type_badge',
        'status_badge',
        'campaign_link',
        'formatted_created_at',
    )

    list_filter = (
        'type',
        'status',
        ('created_at', JDateFieldListFilter),
    )

    search_fields = (
        'user__phone_number',
        'user__nickname',
        'campaign__name',
        'invoice__id',
        'reference_id',
        'description',
    )

    autocomplete_fields = ('user', )

    raw_id_fields = ('campaign', 'invoice', 'payment')

    readonly_fields = (
        'formatted_created_at',
        'amount_display',
        'sign_display',
    )

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('user', 'amount_display', 'type', 'status')
        }),
        ('ارتباط با سایر مدل‌ها', {
            'fields': ('campaign', 'invoice', 'payment', 'reference_id'),
            'classes': ('collapse',)
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('تاریخ', {
            'fields': ('formatted_created_at',),
            'classes': ('collapse',)
        }),
    )

    def user_display(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:accounts_customuser_change', args=[obj.user.id]),
            obj.user.phone_number
        )

    user_display.short_description = 'کاربر'

    def amount_display(self, obj):
        color = '#4CAF50' if obj.is_income else '#f44336'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} تومان</span>',
            color,
            f"{obj.amount:,}"
        )

    amount_display.short_description = 'مبلغ'

    def sign_display(self, obj):
        return obj.sign_display

    sign_display.short_description = 'علامت'

    def type_badge(self, obj):
        colors = {
            Transaction.Type.DEPOSIT: '#4CAF50',
            Transaction.Type.WITHDRAW: '#f44336',
            Transaction.Type.CAMPAIGN_PAYMENT: '#ff9800',
            Transaction.Type.CAMPAIGN_REFUND: '#2196F3',
            Transaction.Type.GATEWAY_PAYMENT: '#9c27b0',
            Transaction.Type.GATEWAY_REFUND: '#00bcd4',
        }
        color = colors.get(obj.type, '#757575')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_type_display())

    type_badge.short_description = 'نوع تراکنش'

    def status_badge(self, obj):
        colors = {
            Transaction.Status.PENDING: '#ff9800',
            Transaction.Status.SUCCESS: '#4CAF50',
            Transaction.Status.FAILED: '#f44336',
            Transaction.Status.CANCELLED: '#757575',
        }
        color = colors.get(obj.status, '#757575')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())

    status_badge.short_description = 'وضعیت'

    def campaign_link(self, obj):
        if obj.campaign:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:campaigns_campaign_change', args=[obj.campaign.id]),
                obj.campaign.name[:30]
            )
        return '-'

    campaign_link.short_description = 'کمپین'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'

    actions = ['mark_as_success', 'mark_as_failed', 'mark_as_pending']

    def mark_as_success(self, request, queryset):
        updated = queryset.update(status=Transaction.Status.SUCCESS)
        self.message_user(request, f'✅ {updated} تراکنش با موفقیت تأیید شد.', messages.SUCCESS)

    mark_as_success.short_description = 'تغییر وضعیت به موفق'

    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status=Transaction.Status.FAILED)
        self.message_user(request, f'❌ {updated} تراکنش ناموفق علامت‌گذاری شد.', messages.SUCCESS)

    mark_as_failed.short_description = 'تغییر وضعیت به ناموفق'

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status=Transaction.Status.PENDING)
        self.message_user(request, f'⏳ {updated} تراکنش به حالت در انتظار برگشت.', messages.SUCCESS)

    mark_as_pending.short_description = 'برگشت به حالت در انتظار'
