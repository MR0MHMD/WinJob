from .models import Invoice, Coupon, Payment, Transaction, Wallet, BankAccount, WithdrawalRequest
from core.utils.admin_utils import RegionalFilterAdminMixin, format_datetime
from django_jalali.admin.filters import JDateFieldListFilter
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.db import models



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


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    """
    مدیریت حساب‌های بانکی کاربران
    """

    list_display = (
        'id',
        'user_display',
        'sheba_display',
        'bank_logo_and_name',  # ✅ تغییر: نمایش لوگو و نام بانک
        'account_holder_name_display',
        'is_default',
        'is_verified',
        'formatted_created_at',
    )

    list_filter = (
        'is_default',
        'is_verified',
        ('created_at', JDateFieldListFilter),
        'user__province',
    )

    search_fields = (
        'user__phone_number',
        'user__nickname',
        'sheba_code',
        'account_holder_name',
    )

    autocomplete_fields = ('user',)

    readonly_fields = (
        'formatted_created_at',
        'formatted_updated_at',
        'user_display',
        'sheba_full_display',
        'bank_logo_and_name_display',  # ✅ جدید
    )

    fieldsets = (
        ('👤 اطلاعات کاربر', {
            'fields': ('user', 'user_display')
        }),
        ('🏦 اطلاعات حساب بانکی', {
            'fields': (
                'sheba_code',
                'sheba_full_display',
                'bank_logo_and_name_display',  # ✅ جدید
                'account_holder_name',
            )
        }),
        ('⚙️ وضعیت', {
            'fields': (
                'is_default',
                'is_verified',
            )
        }),
        ('📅 تاریخ‌ها', {
            'fields': ('formatted_created_at', 'formatted_updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ========== متدهای نمایش ==========

    def user_display(self, obj):
        """نمایش کاربر با لینک به ادمین"""
        if obj.user:
            url = reverse("admin:accounts_customuser_change", args=[obj.user.id])
            return format_html(
                '<a href="{}" target="_blank"><strong>{}</strong><br><span style="color: #666; font-size: 11px;">{}</span></a>',
                url,
                obj.user.nickname or obj.user.phone_number,
                obj.user.phone_number
            )
        return "-"

    user_display.short_description = "کاربر"
    user_display.admin_order_field = "user__phone_number"

    def sheba_display(self, obj):
        """نمایش شبا به صورت فرمت شده"""
        if not obj.sheba_code:
            return "-"
        raw = obj.sheba_code.replace(" ", "").strip()
        if len(raw) >= 2:
            first_two = raw[:2]
            rest = raw[2:]
            formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))
            return f"IR {first_two} {formatted_rest}"
        return obj.sheba_code

    sheba_display.short_description = "شماره شبا"
    sheba_display.admin_order_field = "sheba_code"

    def sheba_full_display(self, obj):
        """نمایش کامل شبا برای صفحه جزئیات"""
        if not obj.sheba_code:
            return "-"
        raw = obj.sheba_code.replace(" ", "").strip()
        if len(raw) >= 2:
            first_two = raw[:2]
            rest = raw[2:]
            formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))
            return format_html(
                '<code style="font-size: 1.1rem; padding: 0.3rem 0.8rem; border-radius: 4px;">IR {}</code>',
                f"{first_two} {formatted_rest}"
            )
        return obj.sheba_code

    sheba_full_display.short_description = "شماره شبا (فرمت شده)"

    # ✅ جدید: نمایش لوگو و نام بانک در لیست
    def bank_logo_and_name(self, obj):
        """نمایش لوگو و نام بانک در لیست"""
        if not obj.bank:
            return "-"

        # اگر لوگو وجود داشته باشد
        if obj.bank.logo and hasattr(obj.bank.logo, 'url'):
            return format_html(
                '<div style="display: flex; align-items: center; gap: 8px;">'
                '<img src="{}" alt="{}" style="width: 30px; height: 30px; object-fit: contain; border-radius: 4px; padding: 2px;">'
                '</div>',
                obj.bank.logo.url,
                obj.bank.name,
            )
        else:
            # اگر لوگو وجود نداشته باشد، فقط نام بانک نمایش داده شود
            return format_html(
                '<span>🏦 {}</span>',
                obj.bank.name
            )

    bank_logo_and_name.short_description = "بانک"
    bank_logo_and_name.admin_order_field = "bank__name"

    # ✅ جدید: نمایش لوگو و نام بانک در صفحه جزئیات
    def bank_logo_and_name_display(self, obj):
        """نمایش لوگو و نام بانک در صفحه جزئیات"""
        if not obj.bank:
            return "-"

        # اگر لوگو وجود داشته باشد
        if obj.bank.logo and hasattr(obj.bank.logo, 'url'):
            return format_html(
                '<div style="display: flex; align-items: center; gap: 12px; padding: 8px 12px;">'
                '<img src="{}" alt="{}" style="width: 30px; height: 30px; object-fit: contain; border-radius: 8px; padding: 4px;">'
                '{}'
                '</div>',
                obj.bank.logo.url,
                obj.bank.name,
                obj.bank.name,
            )
        else:
            return format_html(
                '<div style="padding: 8px 12px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e9ecef;">'
                '<span style="font-size: 1.2rem; font-weight: 600; color: #1a1a1a;">🏦 {}</span>'
                '<div style="font-size: 0.85rem; color: #6c757d;">کد بانک: {}</div>'
                '</div>',
                obj.bank.name,
                obj.bank.code
            )

    bank_logo_and_name_display.short_description = "اطلاعات بانک"

    # متدهای قبلی
    def account_holder_name_display(self, obj):
        """نمایش نام صاحب حساب"""
        if not obj.account_holder_name:
            return "-"
        return format_html(
            '<span style="font-weight: 500;">{}</span>',
            obj.account_holder_name
        )

    account_holder_name_display.short_description = "نام صاحب حساب"
    account_holder_name_display.admin_order_field = "account_holder_name"

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = "تاریخ ایجاد"

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = "آخرین بروزرسانی"

    # ========== اکشن‌ها ==========

    actions = ['mark_as_verified', 'mark_as_unverified', 'mark_as_default']

    def mark_as_verified(self, request, queryset):
        """تأیید حساب‌های بانکی انتخاب شده"""
        updated = queryset.update(is_verified=True)
        self.message_user(
            request,
            f'✅ {updated} حساب بانکی با موفقیت تأیید شدند.',
            messages.SUCCESS
        )

    mark_as_verified.short_description = "تأیید حساب‌های بانکی انتخاب شده"

    def mark_as_unverified(self, request, queryset):
        """لغو تأیید حساب‌های بانکی انتخاب شده"""
        updated = queryset.update(is_verified=False)
        self.message_user(
            request,
            f'⏳ تأیید {updated} حساب بانکی لغو شد.',
            messages.WARNING
        )

    mark_as_unverified.short_description = "لغو تأیید حساب‌های بانکی انتخاب شده"

    def mark_as_default(self, request, queryset):
        """تنظیم به عنوان پیش‌فرض برای هر کاربر"""
        for bank in queryset:
            BankAccount.objects.filter(user=bank.user).update(is_default=False)
            bank.is_default = True
            bank.save()
        self.message_user(
            request,
            f'✅ {queryset.count()} حساب بانکی به عنوان پیش‌فرض تنظیم شد.',
            messages.SUCCESS
        )

    mark_as_default.short_description = "تنظیم به عنوان حساب پیش‌فرض"


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    """
    مدیریت درخواست‌های تسویه حساب
    """

    list_display = (
        'id',
        'tracking_code_display',
        'user_display',
        'withdrawal_type_badge',
        'amount_display',
        'bank_account_info',
        'status_badge',
        'formatted_requested_at',
        'action_buttons',
    )

    list_filter = (
        'status',
        'withdrawal_type',
        ('requested_at', JDateFieldListFilter),
        ('processed_at', JDateFieldListFilter),
        ('completed_at', JDateFieldListFilter),
        'user__province',  # فیلتر بر اساس استان
    )

    search_fields = (
        'tracking_code',
        'user__phone_number',
        'user__nickname',
        'bank_account__sheba_code',
        'bank_account__bank_name',
        'description',
        'admin_note',
    )

    autocomplete_fields = ('user', 'bank_account')
    raw_id_fields = ('transaction',)

    readonly_fields = (
        'tracking_code',
        'formatted_requested_at',
        'formatted_processed_at',
        'formatted_completed_at',
        'user_display',
        'bank_account_full_info',
        'amount_display',
        'status_badge',
        'transaction_link',
    )

    fieldsets = (
        ('📋 اطلاعات درخواست', {
            'fields': (
                ('tracking_code', 'user', 'user_display'),
                ('withdrawal_type', 'amount', 'amount_display'),
            )
        }),
        ('🏦 اطلاعات حساب بانکی', {
            'fields': (
                ('bank_account', 'bank_account_full_info'),
            )
        }),
        ('📊 وضعیت', {
            'fields': (
                ('status', 'status_badge'),
            )
        }),
        ('📝 توضیحات', {
            'fields': (
                'description',
                'admin_note',
            ),
            'classes': ('collapse',)
        }),
        ('🔗 ارتباط با تراکنش', {
            'fields': ('transaction', 'transaction_link'),
            'classes': ('collapse',)
        }),
        ('📅 تاریخ‌ها', {
            'fields': (
                'formatted_requested_at',
                'formatted_processed_at',
                'formatted_completed_at',
            ),
            'classes': ('collapse',)
        }),
    )

    # ========== متدهای نمایش ==========

    def tracking_code_display(self, obj):
        """نمایش کد پیگیری با استایل"""
        if obj.tracking_code:
            return format_html(
                '<code style="font-size: 0.9rem; background: #1a1a2e; color: #ff6b35; padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: bold;">{}</code>',
                obj.tracking_code
            )
        return "-"

    tracking_code_display.short_description = "کد پیگیری"
    tracking_code_display.admin_order_field = "tracking_code"

    def user_display(self, obj):
        """نمایش کاربر با لینک"""
        if obj.user:
            url = reverse("admin:accounts_customuser_change", args=[obj.user.id])
            return format_html(
                '<a href="{}" target="_blank"><strong>{}</strong><br><span style="color: #666; font-size: 11px;">{}</span></a>',
                url,
                obj.user.nickname or obj.user.phone_number,
                obj.user.phone_number
            )
        return "-"

    user_display.short_description = "کاربر"
    user_display.admin_order_field = "user__phone_number"

    def withdrawal_type_badge(self, obj):
        """نوع تسویه با بج"""
        colors = {
            'influencer': 'primary',
            'content_team': 'success',
        }
        labels = {
            'influencer': '📢 ناشر',
            'content_team': '🎯 تیم محتوا',
        }
        color = colors.get(obj.withdrawal_type, 'secondary')
        label = labels.get(obj.withdrawal_type, obj.withdrawal_type)
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            label
        )

    withdrawal_type_badge.short_description = "نوع تسویه"
    withdrawal_type_badge.admin_order_field = "withdrawal_type"

    def amount_display(self, obj):
        """نمایش مبلغ با رنگ و فرمت"""
        formatted_amount = f"{obj.amount:,}"
        return format_html(
            '<span style="font-size: 1.1rem; font-weight: bold; color: #ff6b35;">{}</span> <span style="color: #888;">تومان</span>',
            formatted_amount
        )

    amount_display.short_description = "مبلغ"
    amount_display.admin_order_field = "amount"

    def bank_account_info(self, obj):
        """اطلاعات مختصر حساب بانکی"""
        if obj.bank_account:
            return format_html(
                '<div style="font-size: 0.85rem;">'
                '<span style="color: #fff;">{}</span><br>'
                '<span style="color: #888; font-family: monospace;">IR {}</span>'
                '</div>',
                obj.bank_account.bank_name or 'بانک',
                obj.bank_account.sheba_code or '---'
            )
        return "-"

    bank_account_info.short_description = "حساب بانکی"

    def bank_account_full_info(self, obj):
        """اطلاعات کامل حساب بانکی برای صفحه جزئیات"""
        if not obj.bank_account:
            return "-"

        account = obj.bank_account
        # فرمت شبا
        sheba = account.sheba_code or '---'
        if len(sheba) >= 2:
            first_two = sheba[:2]
            rest = sheba[2:]
            formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))
            sheba_formatted = f"IR {first_two} {formatted_rest}"
        else:
            sheba_formatted = sheba

        return format_html(
            '<div style="background: rgba(255,255,255,0.05); padding: 0.8rem 1rem; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);">'
            '<div><strong>🏦 بانک:</strong> {}</div>'
            '<div><strong>👤 صاحب حساب:</strong> {}</div>'
            '<div><strong>🔢 شماره شبا:</strong> <code style="background: #1a1a2e; padding: 0.2rem 0.5rem; border-radius: 3px;">{}</code></div>'
            '<div><strong>✅ وضعیت:</strong> {}</div>'
            '</div>',
            account.bank_name or '---',
            account.account_holder_name or '---',
            sheba_formatted,
            '✅ تأیید شده' if account.is_verified else '⏳ در انتظار تأیید'
        )

    bank_account_full_info.short_description = "اطلاعات کامل حساب بانکی"

    def status_badge(self, obj):
        """وضعیت درخواست با بج رنگی"""
        colors = {
            'pending': 'warning',
            'processing': 'info',
            'completed': 'success',
            'rejected': 'danger',
            'cancelled': 'secondary',
        }
        icons = {
            'pending': '⏳',
            'processing': '🔄',
            'completed': '✅',
            'rejected': '❌',
            'cancelled': '🚫',
        }
        color = colors.get(obj.status, 'secondary')
        icon = icons.get(obj.status, '')
        return format_html(
            '<span class="badge bg-{}" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )

    status_badge.short_description = "وضعیت"
    status_badge.admin_order_field = "status"

    def formatted_requested_at(self, obj):
        return format_datetime(obj.requested_at)

    formatted_requested_at.short_description = "تاریخ درخواست"

    def formatted_processed_at(self, obj):
        if obj.processed_at:
            return format_datetime(obj.processed_at)
        return "-"

    formatted_processed_at.short_description = "تاریخ پردازش"

    def formatted_completed_at(self, obj):
        if obj.completed_at:
            return format_datetime(obj.completed_at)
        return "-"

    formatted_completed_at.short_description = "تاریخ تسویه"

    def transaction_link(self, obj):
        """لینک به تراکنش مرتبط"""
        if obj.transaction:
            url = reverse("admin:payment_transaction_change", args=[obj.transaction.id])
            return format_html(
                '<a href="{}" target="_blank">تراکنش #{}</a>',
                url,
                obj.transaction.id
            )
        return "بدون تراکنش"

    transaction_link.short_description = "تراکنش مرتبط"

    def action_buttons(self, obj):
        """دکمه‌های عملیات سریع در لیست"""
        buttons = []

        # فقط برای درخواست‌های در انتظار
        if obj.status == WithdrawalRequest.Status.PENDING:
            process_url = reverse("admin:payment_withdrawalrequest_change", args=[obj.id])
            buttons.append(
                f'<a href="{process_url}" class="button" style="background: #ff6b35; color: #fff; padding: 2px 10px; border-radius: 4px; text-decoration: none; font-size: 11px;">🔍 بررسی</a>'
            )

        if obj.transaction:
            trx_url = reverse("admin:payment_transaction_change", args=[obj.transaction.id])
            buttons.append(
                f'<a href="{trx_url}" target="_blank" class="button" style="background: #17a2b8; color: #fff; padding: 2px 10px; border-radius: 4px; text-decoration: none; font-size: 11px;">💰 تراکنش</a>'
            )

        return mark_safe(" ".join(buttons))

    action_buttons.short_description = "عملیات"

    # ========== اکشن‌ها ==========

    actions = [
        'mark_as_processing',
        'mark_as_completed',
        'mark_as_rejected',
        'mark_as_cancelled',
    ]

    def mark_as_processing(self, request, queryset):
        """تغییر وضعیت به در حال پردازش"""
        updated = queryset.filter(status=WithdrawalRequest.Status.PENDING).update(
            status=WithdrawalRequest.Status.PROCESSING,
            processed_at=timezone.now()
        )
        self.message_user(
            request,
            f'🔄 {updated} درخواست به وضعیت "در حال پردازش" تغییر یافت.',
            messages.SUCCESS
        )

    mark_as_processing.short_description = "تغییر وضعیت به در حال پردازش"

    def mark_as_completed(self, request, queryset):
        """تغییر وضعیت به انجام شده (با احتیاط)"""
        from django.utils import timezone

        count = 0
        for withdrawal in queryset.filter(
                status__in=[WithdrawalRequest.Status.PENDING, WithdrawalRequest.Status.PROCESSING]
        ):
            # بررسی موجودی کیف پول
            if withdrawal.user.wallet.balance < withdrawal.amount:
                self.message_user(
                    request,
                    f'⚠️ موجودی کیف پول کاربر {withdrawal.user} کافی نیست!',
                    messages.ERROR
                )
                continue

            # ایجاد تراکنش
            from .models import Transaction
            transaction = Transaction.objects.create(
                user=withdrawal.user,
                amount=withdrawal.amount,
                type=(
                    Transaction.Type.INFLUENCER_WITHDRAWAL
                    if withdrawal.withdrawal_type == WithdrawalRequest.Type.INFLUENCER
                    else Transaction.Type.CONTENT_TEAM_WITHDRAWAL
                ),
                status=Transaction.Status.SUCCESS,
                description=f'تسویه حساب - کد پیگیری: {withdrawal.tracking_code}',
                reference_id=f'WDL-{withdrawal.id}-{int(timezone.now().timestamp())}',
            )

            # تکمیل تسویه
            withdrawal.status = WithdrawalRequest.Status.COMPLETED
            withdrawal.processed_at = timezone.now()
            withdrawal.completed_at = timezone.now()
            withdrawal.transaction = transaction
            withdrawal.save()

            # کاهش موجودی کیف پول
            wallet = withdrawal.user.wallet
            wallet.balance -= withdrawal.amount
            wallet.save()

            count += 1

        self.message_user(
            request,
            f'✅ {count} درخواست با موفقیت تسویه شد.',
            messages.SUCCESS
        )

    mark_as_completed.short_description = "تأیید و تسویه (ایجاد تراکنش)"

    def mark_as_rejected(self, request, queryset):
        """رد درخواست‌ها"""
        updated = queryset.filter(
            status__in=[WithdrawalRequest.Status.PENDING, WithdrawalRequest.Status.PROCESSING]
        ).update(
            status=WithdrawalRequest.Status.REJECTED,
            processed_at=timezone.now(),
            admin_note='رد شده توسط ادمین'
        )
        self.message_user(
            request,
            f'❌ {updated} درخواست رد شد.',
            messages.WARNING
        )

    mark_as_rejected.short_description = "رد درخواست‌های انتخاب شده"

    def mark_as_cancelled(self, request, queryset):
        """لغو درخواست‌ها"""
        updated = queryset.filter(
            status__in=[WithdrawalRequest.Status.PENDING, WithdrawalRequest.Status.PROCESSING]
        ).update(
            status=WithdrawalRequest.Status.CANCELLED
        )
        self.message_user(
            request,
            f'🚫 {updated} درخواست لغو شد.',
            messages.WARNING
        )

    mark_as_cancelled.short_description = "لغو درخواست‌های انتخاب شده"

    # ========== اورراید متدهای میکسین ==========

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # محدودیت برای مدیران استانی
        if request.user.is_regional_manager and request.user.province:
            qs = qs.filter(user__province=request.user.province)

        return qs.select_related(
            'user',
            'user__wallet',
            'bank_account',
            'transaction',
            'user__province',
        )

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    # ========== ذخیره‌سازی با اعتبارسنجی ==========

    def save_model(self, request, obj, form, change):
        """ذخیره با اعتبارسنجی"""
        if change and obj.status == WithdrawalRequest.Status.COMPLETED:
            # اگر وضعیت به completed تغییر کرده، حتماً تراکنش باید داشته باشد
            if not obj.transaction:
                from django.contrib import messages
                messages.error(
                    request,
                    '⚠️ برای تسویه کامل، ابتدا باید تراکنش ایجاد شود!'
                )
                return

        # اگر پردازش شد و زمان پردازش ثبت نشده
        if obj.status in [WithdrawalRequest.Status.COMPLETED, WithdrawalRequest.Status.REJECTED]:
            if not obj.processed_at:
                obj.processed_at = timezone.now()

        super().save_model(request, obj, form, change)

    # ========== تغییر وضعیت با سیگنال ==========

    def response_change(self, request, obj):
        """پس از تغییر وضعیت در صفحه ادمین"""
        msg = None

        if obj.status == WithdrawalRequest.Status.COMPLETED:
            msg = f'✅ درخواست تسویه #{obj.tracking_code} با موفقیت تکمیل شد.'

        elif obj.status == WithdrawalRequest.Status.REJECTED:
            msg = f'❌ درخواست تسویه #{obj.tracking_code} رد شد.'

        elif obj.status == WithdrawalRequest.Status.CANCELLED:
            msg = f'🚫 درخواست تسویه #{obj.tracking_code} لغو شد.'

        if msg:
            self.message_user(request, msg, messages.SUCCESS)

        return super().response_change(request, obj)