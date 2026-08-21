from django.contrib.admin import SimpleListFilter
from django.db import models
from django.utils.safestring import mark_safe

from .models import Invoice, Coupon, Payment, Transaction, Wallet
from core.utils.admin_utils import RegionalFilterAdminMixin, format_datetime
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


# ========== فیلتر سفارشی برای نوع فاکتور ==========
class InvoiceTypeFilter(SimpleListFilter):
    title = 'نوع فاکتور'
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('campaign', 'فاکتور کمپین'),
            ('wallet', 'فاکتور شارژ کیف پول'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())
        return queryset


# ========== ادمین Invoice ==========
@admin.register(Invoice)
class InvoiceAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'invoice_number_display',
        'type_display',
        'user_display',
        'campaign_link',
        'influencer_cost_display',
        'content_cost_display',
        'commission_display',
        'total_vat_display',
        'payable_amount_display',
        'is_paid_display',
        'formatted_created_at',
    )

    list_filter = (
        InvoiceTypeFilter,
        "is_paid",
        ("created_at", JDateFieldListFilter),
        "campaign__advertiser__user__province",
    )

    search_fields = (
        "invoice_number",
        "campaign__name",
        "campaign__advertiser__business_name",
        "campaign__advertiser__user__phone_number",
        "user__phone_number",
        "user__nickname",
        "description",
    )

    readonly_fields = (
        "invoice_number",
        "type",
        "user",
        "campaign",
        "base_influencer_cost",
        "base_content_cost",
        "base_commission",
        "influencer_discount_amount",
        "content_discount_amount",
        "platform_discount_amount",
        "influencer_cost",
        "content_cost",
        "commission",
        "discount_amount",
        "total_amount",
        "payable_amount",
        "influencer_vat",
        "content_vat",
        "commission_vat",
        "total_vat",
        "wallet_deposit_amount",
        "description",
        "formatted_created_at",
        "formatted_updated_at",
        "payments_list",
    )

    fieldsets = (
        ("📋 اطلاعات پایه", {
            "fields": (
                ("type", "invoice_number"),
                ("user", "campaign"),
                "description",
            )
        }),
        ("💰 هزینه‌های پایه (قبل از تخفیف)", {
            "fields": (
                "base_influencer_cost",
                "base_content_cost",
                "base_commission",
            ),
            "classes": ("collapse",)
        }),
        ("🎯 تخفیف‌های اعمال شده", {
            "fields": (
                "influencer_discount_amount",
                "content_discount_amount",
                "platform_discount_amount",
            ),
            "classes": ("collapse",)
        }),
        ("💵 هزینه‌های نهایی (بعد از تخفیف)", {
            "fields": (
                "influencer_cost",
                "content_cost",
                "commission",
                "discount_amount",
            )
        }),
        ("🧾 مالیات بر ارزش افزوده (۱۰٪)", {
            "fields": (
                ("influencer_vat", "content_vat", "commission_vat"),
                "total_vat",
            ),
            "classes": ("collapse",)
        }),
        ("📊 جمع کل", {
            "fields": (
                "total_amount",
                "payable_amount",
            )
        }),
        ("💳 شارژ کیف پول", {
            "fields": ("wallet_deposit_amount",),
            "classes": ("collapse",),
            "description": "فقط برای فاکتورهای شارژ کیف پول"
        }),
        ("وضعیت", {
            "fields": ("is_paid", "paid_at")
        }),
        ("تاریخچه", {
            "fields": ("formatted_created_at", "formatted_updated_at"),
            "classes": ("collapse",)
        }),
        ("پرداخت‌های مرتبط", {
            "fields": ("payments_list",),
            "classes": ("collapse",)
        }),
    )

    # ========== متدهای نمایش ==========

    def invoice_number_display(self, obj):
        return format_html(
            '<span class="fw-bold">{}</span>',
            obj.invoice_number or '---'
        )

    invoice_number_display.short_description = "شماره فاکتور"
    invoice_number_display.admin_order_field = "invoice_number"

    def type_display(self, obj):
        colors = {
            'campaign': 'primary',
            'wallet': 'success',
        }
        labels = {
            'campaign': '📢 کمپین',
            'wallet': '💰 شارژ کیف پول',
        }
        color = colors.get(obj.type, 'secondary')
        label = labels.get(obj.type, obj.type)
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            label
        )

    type_display.short_description = "نوع فاکتور"
    type_display.admin_order_field = "type"

    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                reverse("admin:accounts_customuser_change", args=[obj.user.id]),
                obj.user.phone_number
            )
        return "-"

    user_display.short_description = "کاربر"
    user_display.admin_order_field = "user__phone_number"

    def campaign_link(self, obj):
        if obj.campaign:
            url = reverse("admin:campaigns_campaign_change", args=[obj.campaign.id])
            return format_html(
                '<a href="{}" target="_blank">{} - {}</a>',
                url,
                obj.campaign.name[:40] if obj.campaign.name else f"کمپین #{obj.campaign.id}",
                obj.campaign.get_status_display() if hasattr(obj.campaign, 'get_status_display') else ''
            )
        return "-"

    campaign_link.short_description = "کمپین"
    campaign_link.admin_order_field = "campaign__name"

    def influencer_cost_display(self, obj):
        if obj.type == Invoice.Type.WALLET:
            return "-"
        return f"{obj.influencer_cost:,}" if obj.influencer_cost else "۰"

    influencer_cost_display.short_description = "هزینه ناشران"
    influencer_cost_display.admin_order_field = "influencer_cost"

    def content_cost_display(self, obj):
        if obj.type == Invoice.Type.WALLET:
            return "-"
        return f"{obj.content_cost:,}" if obj.content_cost else "۰"

    content_cost_display.short_description = "هزینه محتوا"
    content_cost_display.admin_order_field = "content_cost"

    def commission_display(self, obj):
        if obj.type == Invoice.Type.WALLET:
            return "-"
        return f"{obj.commission:,}" if obj.commission else "۰"

    commission_display.short_description = "کمیسیون"
    commission_display.admin_order_field = "commission"

    def total_vat_display(self, obj):
        return f"{obj.total_vat:,}" if obj.total_vat else "۰"

    total_vat_display.short_description = "مالیات"
    total_vat_display.admin_order_field = "total_vat"

    def payable_amount_display(self, obj):
        if obj.type == Invoice.Type.WALLET:
            return f"{obj.wallet_deposit_amount:,}"
        return f"{obj.payable_amount:,}"

    payable_amount_display.short_description = "مبلغ قابل پرداخت"
    payable_amount_display.admin_order_field = "payable_amount"

    def is_paid_display(self, obj):
        if obj.is_paid:
            return mark_safe(
                '<span class="badge bg-success">✅ پرداخت شده</span>'
            )
        return mark_safe(
            '<span class="badge bg-danger">❌ پرداخت نشده</span>'
        )

    is_paid_display.short_description = "وضعیت پرداخت"
    is_paid_display.admin_order_field = "is_paid"

    def formatted_created_at(self, obj):
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_updated_at(self, obj):
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین بروزرسانی"

    def payments_list(self, obj):
        payments = obj.payments.all()
        if not payments:
            return "بدون پرداخت"

        html = "<ul style='margin:0; padding-right:20px;'>"
        for payment in payments:
            status_color = 'success' if payment.status == 'success' else 'warning' if payment.status == 'pending' else 'danger'
            html += f"""
                <li>
                    {payment.get_payment_method_display()} - 
                    {payment.amount:,} تومان - 
                    <span class="badge bg-{status_color}">{payment.get_status_display()}</span>
                    {f" - کد پیگیری: {payment.ref_id}" if payment.ref_id else ""}
                </li>
            """
        html += "</ul>"
        return mark_safe(html)

    payments_list.short_description = "پرداخت‌ها"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            qs = qs.filter(
                models.Q(campaign__advertiser__user__province=request.user.province) |
                models.Q(user__province=request.user.province)
            )

        return qs.select_related(
            'user',
            'campaign',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'campaign__advertiser__user__province',
        ).prefetch_related('payments')

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign and obj.campaign.advertiser.user.province != request.user.province:
                return False
            if obj.user and obj.user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.campaign and obj.campaign.advertiser.user.province != request.user.province:
                return False
            if obj.user and obj.user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user_display',
        'invoice_display',
        'amount_display',
        'payment_method_display',
        'status_display',
        'formatted_created_at',
    )

    list_filter = (
        'status',
        'payment_method',
        ('created_at', JDateFieldListFilter),
    )

    search_fields = (
        'user__phone_number',
        'user__nickname',
        'invoice__invoice_number',
        'ref_id',
        'authority',
    )

    readonly_fields = (
        'user',
        'invoice',
        'amount',
        'payment_method',
        'authority',
        'ref_id',
        'status',
        'formatted_created_at',
    )

    fieldsets = (
        ("اطلاعات پایه", {
            "fields": (
                ("user", "invoice"),
                "amount",
                ("payment_method", "status"),
            )
        }),
        ("اطلاعات درگاه", {
            "fields": (
                "authority",
                "ref_id",
            ),
            "classes": ("collapse",)
        }),
        ("تاریخچه", {
            "fields": ("formatted_created_at",),
            "classes": ("collapse",)
        }),
    )

    def user_display(self, obj):
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            reverse("admin:accounts_customuser_change", args=[obj.user.id]),
            obj.user.phone_number
        )
    user_display.short_description = "کاربر"
    user_display.admin_order_field = "user__phone_number"

    def invoice_display(self, obj):
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            reverse("admin:payment_invoice_change", args=[obj.invoice.id]),
            obj.invoice.invoice_number or f"فاکتور #{obj.invoice.id}"
        )
    invoice_display.short_description = "فاکتور"
    invoice_display.admin_order_field = "invoice__invoice_number"

    def amount_display(self, obj):
        return f"{obj.amount:,} تومان"
    amount_display.short_description = "مبلغ"
    amount_display.admin_order_field = "amount"

    def payment_method_display(self, obj):
        labels = {
            'gateway': '🏦 درگاه پرداخت',
            'wallet': '💰 کیف پول',
        }
        return labels.get(obj.payment_method, obj.payment_method)
    payment_method_display.short_description = "روش پرداخت"
    payment_method_display.admin_order_field = "payment_method"

    def status_display(self, obj):
        colors = {
            'pending': 'warning',
            'success': 'success',
            'failed': 'danger',
            'cancelled': 'secondary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = "وضعیت"
    status_display.admin_order_field = "status"

    def formatted_created_at(self, obj):
        from core.utils.admin_utils import format_datetime
        return format_datetime(obj.created_at)
    formatted_created_at.short_description = "تاریخ ایجاد"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'invoice')


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
