# market/admin.py
import uuid
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.urls import reverse
from django.db.models import Sum
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django_jalali.admin.filters import JDateFieldListFilter

from .models import (
    SupplierProfile, Product, ProductImage, Feature,
    ProductFeature, Variant, Cart, CartItem, Order, OrderItem, Category, Review, OrderAddress, ShippingMethod,
    OrderShipping, SupportOrderRequest
)


# ============================================================
#                        Mixins
# ============================================================

class ImagePreviewMixin:
    """پیش‌نمایش تصویر توی ادمین"""

    @admin.display(description=_("پیش‌نمایش"))
    def image_preview(self, obj):
        if hasattr(obj, 'image') and obj.image:
            return format_html(
                '<img src="{}" style="width:60px;height:60px;'
                'object-fit:cover;border-radius:8px;'
                'box-shadow:0 2px 6px rgba(0,0,0,0.15);" />',
                obj.image.url
            )
        if hasattr(obj, 'main_image') and obj.main_image:
            return format_html(
                '<img src="{}" style="width:60px;height:60px;'
                'object-fit:cover;border-radius:8px;'
                'box-shadow:0 2px 6px rgba(0,0,0,0.15);" />',
                obj.main_image.url
            )
        return mark_safe(
            '<div style="width:60px;height:60px;background:#f0f0f0;'
            'border-radius:8px;display:flex;align-items:center;'
            'justify-content:center;color:#999;font-size:11px;">بدون تصویر</div>'
        )


class JalaliDateFilterMixin:
    """فیلتر تاریخ شمسی"""
    pass


# ============================================================
#                    SupplierProfile Admin
# ============================================================

@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = (
        'brand_name', 'user_link', 'contact_phone',
        'products_count', 'total_sales', 'is_active', 'created_at'
    )
    list_filter = ('is_active', 'created_at')
    search_fields = (
        'brand_name', 'contact_phone',
        'user__phone_number', 'user__nickname', 'user__email'
    )
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'stats_display')
    autocomplete_fields = ('user',)

    fieldsets = (
        (_("اطلاعات اصلی"), {
            'fields': ('user', 'brand_name', 'contact_phone', 'is_active')
        }),
        (_("اطلاعات تکمیلی"), {
            'fields': ('address', 'description'),
            'classes': ('collapse',)
        }),
        (_("آمار"), {
            'fields': ('stats_display',),
            'classes': ('collapse',)
        }),
        (_("زمان"), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_("کاربر"))
    def user_link(self, obj):
        url = reverse('admin:accounts_customuser_change', args=[obj.user.pk])
        return format_html(
            '<a href="{}" style="color:#2563eb;font-weight:600;">{}</a>',
            url, obj.user.phone_number
        )

    @admin.display(description=_("تعداد محصولات"))
    def products_count(self, obj):
        count = obj.products.count()
        color = '#10b981' if count > 0 else '#9ca3af'
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            color, count
        )

    @admin.display(description=_("مجموع فروش"))
    def total_sales(self, obj):
        total = OrderItem.objects.filter(
            supplier=obj,
            order__status__in=[Order.Status.PAID, Order.Status.DELIVERED]
        ).aggregate(s=Sum('subtotal'))['s'] or 0
        return format_html(
            '<span style="font-weight:700;color:#059669;">{} تومان</span>',
            f"{total:,}"
        )

    @admin.display(description=_("آمار کامل"))
    def stats_display(self, obj):
        if not obj.pk:
            return "-"
        products = obj.products.count()
        active_products = obj.products.filter(status=Product.Status.ACTIVE).count()
        sold = OrderItem.objects.filter(supplier=obj).aggregate(
            s=Sum('quantity')
        )['s'] or 0
        revenue = OrderItem.objects.filter(
            supplier=obj,
            order__status__in=[Order.Status.PAID, Order.Status.DELIVERED]
        ).aggregate(s=Sum('subtotal'))['s'] or 0

        return mark_safe(f"""
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">
            <div style="background:#eff6ff;padding:12px;border-radius:8px;">
                <div style="color:#1e40af;font-size:12px;">کل محصولات</div>
                <div style="font-size:22px;font-weight:700;color:#1e3a8a;">{products}</div>
            </div>
            <div style="background:#f0fdf4;padding:12px;border-radius:8px;">
                <div style="color:#166534;font-size:12px;">محصولات فعال</div>
                <div style="font-size:22px;font-weight:700;color:#14532d;">{active_products}</div>
            </div>
            <div style="background:#fef3c7;padding:12px;border-radius:8px;">
                <div style="color:#92400e;font-size:12px;">تعداد فروش</div>
                <div style="font-size:22px;font-weight:700;color:#78350f;">{sold}</div>
            </div>
            <div style="background:#fce7f3;padding:12px;border-radius:8px;">
                <div style="color:#9d174d;font-size:12px;">درآمد کل</div>
                <div style="font-size:18px;font-weight:700;color:#831843;">{revenue:,} ت</div>
            </div>
        </div>
        """)


# ============================================================
#                    Product Inlines
# ============================================================

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'preview', 'alt_text', 'order')
    readonly_fields = ('preview',)
    ordering = ('order',)

    @admin.display(description=_("پیش‌نمایش"))
    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:80px;height:80px;'
                'object-fit:cover;border-radius:6px;" />',
                obj.image.url
            )
        return "-"


class ProductFeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 1
    fields = ('feature', 'value')
    autocomplete_fields = ('feature',)


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 1
    fields = ('attributes', 'sku', 'price', 'stock', 'image_preview', 'is_active')
    readonly_fields = ('image_preview',)
    classes = ('collapse',)

    @admin.display(description=_("تصویر"))
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:50px;height:50px;'
                'object-fit:cover;border-radius:6px;" />',
                obj.image.url
            )
        return "-"


# ============================================================
#                       Product Admin
# ============================================================

@admin.register(Product)
class ProductAdmin(ImagePreviewMixin, admin.ModelAdmin):
    list_display = (
        "image_preview", "title", "category", "supplier", "price_display",
        "stock_display", "status_badge", "campaign_timer",
        "sold_count", "view_count",
    )
    list_filter = (
        "status", "category", "supplier", "created_at",
        ("campaign_start", JDateFieldListFilter),
    )
    autocomplete_fields = ("supplier", "category")
    search_fields = ('title', 'slug', 'description', 'supplier__brand_name')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = (
        'view_count', 'sold_count', 'created_at', 'updated_at',
        'campaign_status_display', 'image_preview'  # ← اضافه شد
    )
    inlines = [ProductImageInline, ProductFeatureInline, VariantInline]
    list_per_page = 20

    fieldsets = (
        (_("اطلاعات اصلی"), {
            "fields": (
                "title", "slug", "category", "supplier",
                "short_description", "description",
                "main_image", "image_preview",
            )
        }),
        (_("قیمت و موجودی"), {
            'fields': ('base_price', 'discount_price', 'stock')
        }),
        (_("کمپین ۳ روزه"), {
            'fields': ('campaign_start', 'campaign_end', 'campaign_status_display'),
            'description': _(
                '⚠️ توجه: در هر لحظه فقط یک محصول می‌تواند ACTIVE باشد. '
                'با فعال کردن این محصول، محصول فعال قبلی به صورت خودکار غیرفعال می‌شود.'
            )
        }),
        (_("وضعیت و آمار"), {
            'fields': ('status', 'view_count', 'sold_count')
        }),
        (_("روش‌های ارسال"), {
            'fields': ('shipping_methods',),
            'description': _('روش‌هایی که این محصول ازشون پشتیبانی می‌کنه')
        }),
        (_("زمان"), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ---------- Columns ----------

    @admin.display(description=_("قیمت"), ordering='base_price')
    def price_display(self, obj):
        if obj.discount_price:
            return format_html(
                '<div style="line-height:1.4;">'
                '<div style="text-decoration:line-through;color:#9ca3af;'
                'font-size:11px;">{}</div>'
                '<div style="color:#dc2626;font-weight:700;">{}</div>'
                '<div style="background:#fef2f2;color:#dc2626;'
                'font-size:10px;padding:1px 6px;border-radius:8px;'
                'display:inline-block;">{}٪ تخفیف</div>'
                '</div>',
                f"{obj.base_price:,}",
                f"{obj.final_price:,}",
                obj.discount_percent
            )
        return format_html(
            '<span style="font-weight:700;color:#111827;">{} ت</span>',
            f"{obj.base_price:,}"
        )

    @admin.display(description=_("موجودی"), ordering='stock')
    def stock_display(self, obj):
        stock = obj.stock
        if stock == 0:
            color, bg = '#991b1b', '#fef2f2'
            label = 'ناموجود'
        elif stock < 5:
            color, bg = '#92400e', '#fef3c7'
            label = f'{stock} (کم)'
        else:
            color, bg = '#166534', '#f0fdf4'
            label = str(stock)
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            bg, color, label
        )

    @admin.display(description=_("وضعیت"), ordering='status')
    def status_badge(self, obj):
        colors = {
            'draft': ('#6b7280', '#f3f4f6'),
            'active': ('#065f46', '#d1fae5'),
            'scheduled': ('#1e40af', '#dbeafe'),
            'inactive': ('#991b1b', '#fee2e2'),
            'sold_out': ('#92400e', '#fef3c7'),
        }
        color, bg = colors.get(obj.status, ('#374151', '#f3f4f6'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 12px;'
            'border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            bg, color, obj.get_status_display()
        )

    @admin.display(description=_("تایمر کمپین"))
    def campaign_timer(self, obj):
        if not obj.campaign_end:
            return mark_safe('<span style="color:#9ca3af;">-</span>')

        now = timezone.now()
        if obj.campaign_start and now < obj.campaign_start:
            diff = obj.campaign_start - now
            return format_html(
                '<span style="color:#1e40af;font-weight:600;">'
                'شروع در {}</span>',
                self._format_duration(diff)
            )

        if now > obj.campaign_end:
            return mark_safe(
                '<span style="color:#991b1b;font-weight:600;">'
                'پایان یافته</span>'
            )

        diff = obj.campaign_end - now
        total_seconds = int(diff.total_seconds())
        # اگه کمتر از ۶ ساعت مونده، قرمز بشه
        color = '#dc2626' if total_seconds < 6 * 3600 else '#059669'
        return format_html(
            '<span style="color:{};font-weight:700;">⏱ {}</span>',
            color, self._format_duration(diff)
        )

    @admin.display(description=_("وضعیت کمپین"))
    def campaign_status_display(self, obj):
        if not obj.pk:
            return "-"
        if obj.is_on_campaign:
            remaining = obj.remaining_time
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            return format_html(
                '<div style="background:#d1fae5;color:#065f46;'
                'padding:12px;border-radius:8px;font-weight:600;">'
                '✅ این محصول الان فعال است — '
                '{} ساعت و {} دقیقه تا پایان'
                '</div>',
                hours, minutes
            )
        return mark_safe(
            '<div style="background:#f3f4f6;color:#6b7280;'
            'padding:12px;border-radius:8px;">'
            'این محصول در حال حاضر فعال نیست.'
            '</div>'
        )

    @staticmethod
    def _format_duration(delta):
        total = int(delta.total_seconds())
        days = total // 86400
        hours = (total % 86400) // 3600
        minutes = (total % 3600) // 60
        if days > 0:
            return f"{days} روز و {hours} ساعت"
        if hours > 0:
            return f"{hours} ساعت و {minutes} دقیقه"
        return f"{minutes} دقیقه"

    # ---------- Actions ----------

    actions = ['activate_campaign', 'deactivate_products', 'duplicate_products']

    @admin.action(description=_("🚀 فعال‌سازی کمپین ۳ روزه"))
    def activate_campaign(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                _("فقط یک محصول را می‌توانید برای فعال‌سازی انتخاب کنید."),
                level=messages.ERROR
            )
            return

        product = queryset.first()
        now = timezone.now()
        product.status = Product.Status.ACTIVE
        product.campaign_start = now
        product.campaign_end = now + timezone.timedelta(days=3)
        product.save()

        self.message_user(
            request,
            _(f"محصول «{product.title}» برای ۳ روز فعال شد ✅"),
            level=messages.SUCCESS
        )

    @admin.action(description=_("⛔ غیرفعال‌سازی محصولات انتخاب شده"))
    def deactivate_products(self, request, queryset):
        count = queryset.update(status=Product.Status.INACTIVE)
        self.message_user(
            request,
            _(f"{count} محصول غیرفعال شد."),
            level=messages.SUCCESS
        )

    @admin.action(description=_("📋 کپی محصولات انتخاب شده"))
    def duplicate_products(self, request, queryset):
        for product in queryset:
            original_pk = product.pk
            original_title = product.title

            # اطلاعات اصلی رو کپی کن
            product.pk = None
            product.id = None
            product.slug = f"{product.slug}-copy-{uuid.uuid4().hex[:6]}"
            product.title = f"{original_title} (کپی)"
            product.status = Product.Status.DRAFT
            product.view_count = 0
            product.sold_count = 0
            product.campaign_start = None
            product.campaign_end = None
            product.save()

            # کپی گالری تصاویر
            original = Product.objects.get(pk=original_pk)
            for img in original.images.all():
                ProductImage.objects.create(
                    product=product,
                    image=img.image,
                    alt_text=img.alt_text,
                    order=img.order,
                )

            # کپی ویژگی‌ها
            for feat in original.features.all():
                ProductFeature.objects.create(
                    product=product,
                    feature=feat.feature,
                    value=feat.value,
                )

            # کپی variant ها
            for variant in original.variants.all():
                Variant.objects.create(
                    product=product,
                    attributes=variant.attributes,
                    sku=f"WM-{uuid.uuid4().hex[:8].upper()}",  # SKU جدید
                    price=variant.price,
                    stock=variant.stock,
                    image=variant.image,
                    is_active=variant.is_active,
                )

        self.message_user(
            request,
            _(f"{queryset.count()} محصول با تمام جزئیات کپی شد."),
            level=messages.SUCCESS
        )


# ============================================================
#                       Feature Admin
# ============================================================

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'unit', 'usage_count')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description=_("تعداد استفاده"))
    def usage_count(self, obj):
        count = obj.productfeature_set.count()
        return format_html(
            '<span style="background:#eff6ff;color:#1e40af;'
            'padding:3px 10px;border-radius:12px;font-size:12px;'
            'font-weight:600;">{}</span>',
            count
        )


# ============================================================
#                       Cart Admin
# ============================================================

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('product', 'variant', 'quantity', 'subtotal_display')
    can_delete = False

    @admin.display(description=_("جمع"))
    def subtotal_display(self, obj):
        if obj.pk:
            return f"{obj.subtotal:,} تومان"
        return "-"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'items_count', 'total_display', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__phone_number', 'user__nickname', 'session_key')
    readonly_fields = ('user', 'session_key', 'created_at', 'updated_at')
    inlines = [CartItemInline]

    def has_add_permission(self, request):
        return False

    @admin.display(description=_("تعداد آیتم"))
    def items_count(self, obj):
        count = obj.items_count
        return format_html(
            '<span style="background:#eff6ff;color:#1e40af;'
            'padding:3px 10px;border-radius:12px;font-size:12px;'
            'font-weight:600;">{}</span>',
            count
        )

    @admin.display(description=_("جمع کل"))
    def total_display(self, obj):
        return format_html(
            '<span style="font-weight:700;color:#059669;">{} تومان</span>',
            f"{obj.total_price:,}"
        )


# ============================================================
#                       Order Admin
# ============================================================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = (
        'product', 'variant_info', 'product_title',
        'unit_price', 'quantity', 'subtotal', 'supplier'
    )
    search_fields = ('order__invoice__invoice_number', 'product_title')
    readonly_fields = ('product_title', 'variant_info', 'unit_price', 'subtotal')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
#                       Order Address Inline
# ============================================================

class OrderAddressInline(admin.StackedInline):
    model = OrderAddress
    extra = 0
    can_delete = False
    max_num = 1
    fields = (
        "receiver_name", "receiver_phone",
        ("province", "city"),
        "address",
        ("plaque", "unit", "postal_code"),
    )
    autocomplete_fields = ("province", "city")

    def has_add_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # بعد از ثبت سفارش، همه فیلدها readonly
        if obj:
            return (
                "receiver_name", "receiver_phone",
                "province", "city", "address",
                "plaque", "unit", "postal_code",
            )
        return ()


class OrderShippingInline(admin.StackedInline):
    model = OrderShipping
    extra = 0
    can_delete = False
    fields = ("supplier", "method_name", "shipping_method")
    readonly_fields = ("supplier", "method_name", "shipping_method")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'number_display', 'user_link', 'status_badge',
        'total_display', 'payment_badge', 'created_at'
    )
    list_filter = (
        'status',
        ('created_at', JDateFieldListFilter),
    )
    search_fields = (
        'user__phone_number', 'user__nickname',
        'order_address__receiver_phone',
        'tracking_code',
        'invoice__invoice_number',
    )
    readonly_fields = (
        'user', 'items_total', 'total_amount',
        'paid_at', 'created_at', 'updated_at', 'order_summary'
    )
    inlines = [OrderAddressInline, OrderShippingInline, OrderItemInline]
    list_per_page = 20
    save_on_top = True
    date_hierarchy = 'created_at'

    fieldsets = (
        (_("اطلاعات سفارش"), {
            'fields': ('number_display', 'user', 'status', 'order_summary')
        }),
        (_("ارسال"), {
            'fields': ('tracking_code', 'shipped_at', 'delivered_at',
                       'delivered_confirmed_at', 'supplier_payment_released_at')
        }),
        (_("یادداشت‌ها"), {
            'fields': ('customer_note', 'admin_note')
        }),
        (_("زمان"), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ---------- Columns ----------

    @admin.display(description=_("شماره سفارش"))
    def number_display(self, obj):
        num = obj.number
        if not num:
            return mark_safe('<span style="color:#9ca3af;">—</span>')
        return format_html(
            '<span style="font-weight:700;font-family:monospace;">{}</span>',
            num,
        )

    @admin.display(description=_("کاربر"))
    def user_link(self, obj):
        url = reverse('admin:accounts_customuser_change', args=[obj.user.pk])
        return format_html(
            '<a href="{}" style="color:#2563eb;font-weight:600;">{}</a>',
            url, obj.user.phone_number
        )

    @admin.display(description=_("وضعیت"), ordering='status')
    def status_badge(self, obj):
        colors = {
            'pending': ('#92400e', '#fef3c7'),
            'paid': ('#065f46', '#d1fae5'),
            'processing': ('#1e40af', '#dbeafe'),
            'shipped': ('#5b21b6', '#ede9fe'),
            'delivered': ('#065f46', '#d1fae5'),
            'canceled': ('#991b1b', '#fee2e2'),
            'returned': ('#7c2d12', '#fed7aa'),
        }
        color, bg = colors.get(obj.status, ('#374151', '#f3f4f6'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 12px;'
            'border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            bg, color, obj.get_status_display()
        )

    @admin.display(description=_("مبلغ کل"))
    def total_display(self, obj):
        total = obj.total_amount
        return format_html(
            '<span style="font-weight:700;color:#059669;font-size:14px;">'
            '{} تومان</span>',
            f"{total:,}"
        )

    @admin.display(description=_("پرداخت"))
    def payment_badge(self, obj):
        if obj.is_paid:
            return mark_safe(
                '<span style="color:#059669;font-weight:600;">'
                '✅ پرداخت شده</span>'
            )
        return mark_safe(
            '<span style="color:#dc2626;font-weight:600;">'
            '❌ پرداخت نشده</span>'
        )

    @admin.display(description=_("خلاصه سفارش"))
    def order_summary(self, obj):
        if not obj.pk:
            return "-"
        items = obj.items.all()
        rows = "".join(
            f'<tr>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">'
            f'{item.product_title}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">'
            f'{item.variant_info or "-"}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:center;">'
            f'{item.quantity}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:left;">'
            f'{item.subtotal:,}</td>'
            f'</tr>'
            for item in items
        )
        return mark_safe(f"""
        <table style="width:100%;border-collapse:collapse;background:white;
        border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <thead style="background:#f9fafb;">
                <tr>
                    <th style="padding:8px 10px;text-align:right;font-size:12px;color:#6b7280;">محصول</th>
                    <th style="padding:8px 10px;text-align:right;font-size:12px;color:#6b7280;">تنوع</th>
                    <th style="padding:8px 10px;text-align:center;font-size:12px;color:#6b7280;">تعداد</th>
                    <th style="padding:8px 10px;text-align:left;font-size:12px;color:#6b7280;">جمع</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """)

    actions = ['mark_as_paid', 'mark_as_shipped', 'mark_as_canceled']

    @admin.action(description=_("✅ علامت‌گذاری به عنوان پرداخت شده"))
    def mark_as_paid(self, request, queryset):
        count = queryset.filter(status=Order.Status.PENDING).update(
            status=Order.Status.PAID,
        )
        self.message_user(
            request,
            _(f"{count} سفارش به عنوان پرداخت شده علامت‌گذاری شد."),
            level=messages.SUCCESS
        )

    @admin.action(description=_("📦 علامت‌گذاری به عنوان ارسال شده"))
    def mark_as_shipped(self, request, queryset):
        count = queryset.filter(
            status__in=[Order.Status.PAID, Order.Status.PROCESSING]
        ).update(
            status=Order.Status.SHIPPED,
            shipped_at=timezone.now()
        )
        self.message_user(
            request,
            _(f"{count} سفارش به عنوان ارسال شده علامت‌گذاری شد."),
            level=messages.SUCCESS
        )

    @admin.action(description=_("❌ لغو سفارشات انتخاب شده"))
    def mark_as_canceled(self, request, queryset):
        count = queryset.exclude(status__in=[
            Order.Status.DELIVERED, Order.Status.CANCELED
        ]).update(status=Order.Status.CANCELED)
        self.message_user(
            request,
            _(f"{count} سفارش لغو شد."),
            level=messages.WARNING
        )


# ============================================================
#                    OrderItem Admin (جدید)
# ============================================================

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order_link', 'product_title', 'variant_info',
        'quantity', 'subtotal_display', 'supplier'
    )
    list_filter = ('supplier',)
    search_fields = ('order__invoice__invoice_number', 'product_title')
    readonly_fields = (
        'order', 'product', 'variant', 'product_title',
        'variant_info', 'unit_price', 'quantity', 'subtotal', 'supplier'
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description=_("سفارش"))
    def order_link(self, obj):
        url = reverse('admin:market_order_change', args=[obj.order.pk])
        return format_html(
            '<a href="{}" style="color:#2563eb;font-weight:600;">{}</a>',
            url, obj.order.invoice.invoice_number
        )

    @admin.display(description=_("جمع"))
    def subtotal_display(self, obj):
        return f"{obj.subtotal:,} تومان"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon_preview", "order", "is_active", "products_count")
    list_editable = ("order", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("is_active",)

    @admin.display(description=_("آیکون"))
    def icon_preview(self, obj):
        if obj.icon:
            return format_html(
                '<i class="{}" style="font-size:1.5rem;color:#fd5631;"></i>',
                obj.icon,
            )
        return "-"

    @admin.display(description=_("تعداد محصولات"))
    def products_count(self, obj):
        return obj.products.count()


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "icon_preview", "order", "is_active", "products_count")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("is_active",)

    @admin.display(description=_("آیکون"))
    def icon_preview(self, obj):
        if obj.icon:
            return format_html(
                '<i class="{}" style="font-size:1.5rem;color:#fd5631;"></i>',
                obj.icon,
            )
        return "-"

    @admin.display(description=_("تعداد محصولات"))
    def products_count(self, obj):
        return obj.products.count()


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "product_link", "user_link", "stars_display",
        "is_verified_buyer", "is_active", "created_at",
    )
    list_filter = ("rating", "is_active", "is_verified_buyer", "created_at")
    search_fields = (
        "product__title", "user__phone_number",
        "user__nickname", "comment",
    )
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("is_active",)
    autocomplete_fields = ("product", "user")

    @admin.display(description=_("محصول"))
    def product_link(self, obj):
        url = reverse("admin:market_product_change", args=[obj.product.pk])
        return format_html('<a href="{}">{}</a>', url, obj.product.title)

    @admin.display(description=_("کاربر"))
    def user_link(self, obj):
        url = reverse("admin:accounts_customuser_change", args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.phone_number)

    @admin.display(description=_("امتیاز"))
    def stars_display(self, obj):
        stars = "★" * obj.rating + "☆" * (5 - obj.rating)
        return format_html(
            '<span style="color:#fdbc31;font-size:1rem;letter-spacing:2px;">{}</span>',
            stars,
        )


from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from market.models import GuestOrder


@admin.register(GuestOrder)
class GuestOrderAdmin(admin.ModelAdmin):
    """
    پنل مدیریت سفارشات مهمان (خرید اقساطی مینی‌پی)
    """

    # ---- لیست ----
    list_display = (
        'order_number',
        'product_title',
        'total_amount_display',
        'receiver_name',
        'phone_number',
        'status_badge',
        'created_at',
        'paid_at',
    )
    list_filter = ('status', 'created_at', 'province')
    search_fields = (
        'order_number', 'phone_number', 'national_id',
        'receiver_name', 'product_title',
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 30
    list_select_related = ('product', 'province', 'city')

    # ---- جزئیات ----
    readonly_fields = (
        'order_number',
        'product_link',
        'product_title',
        'unit_price',
        'total_amount',
        'created_at',
        'updated_at',
        'paid_at',
        'inquiry_id',
        'pre_transaction_id',
        'transaction_id',
        'payment_ref_id',
        'payment_error_display',
    )

    fieldsets = (
        ('شناسه و وضعیت', {
            'fields': (
                'order_number', 'status',
                'created_at', 'updated_at', 'paid_at',
            ),
        }),
        ('محصول (Snapshot)', {
            'fields': (
                'product_link', 'product_title',
                'unit_price', 'quantity', 'total_amount',
            ),
        }),
        ('اطلاعات خریدار', {
            'fields': (
                'receiver_name', 'phone_number', 'national_id',
            ),
        }),
        ('آدرس ارسال', {
            'fields': (
                'province', 'city', 'address', 'postal_code',
            ),
        }),
        ('اطلاعات پرداخت مینی‌پی', {
            'fields': (
                'inquiry_id', 'pre_transaction_id',
                'transaction_id', 'payment_ref_id',
                'payment_error_display',
            ),
            'classes': ('collapse',),
        }),
    )

    # ---- Actions ----
    actions = (
        'mark_processing',
        'mark_shipped',
        'mark_delivered',
        'mark_canceled',
        'clear_payment_error',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('product', 'province', 'city')

    # سفارش مهمان فقط از فرانت ساخته می‌شه، نه از پنل
    def has_add_permission(self, request):
        return False

    # ---- ستون‌ها ----

    @admin.display(description='مبلغ (تومان)', ordering='total_amount')
    def total_amount_display(self, obj):
        return f"{obj.total_amount:,}"

    @admin.display(description='محصول')
    def product_link(self, obj):
        if not obj.product_id:
            return obj.product_title or '—'
        try:
            url = reverse('admin:market_product_change', args=[obj.product_id])
            return format_html('<a href="{}" target="_blank">{}</a>', url, obj.product.title)
        except Exception:
            return obj.product_title

    @admin.display(description='وضعیت', ordering='status')
    def status_badge(self, obj):
        colors = {
            'pending':      '#9691a4',
            'inquiry_ok':   '#3c76f2',
            'awaiting_otp': '#fdbc31',
            'paid':         '#07c98b',
            'processing':   '#3c76f2',
            'shipped':      '#5d3cf2',
            'delivered':    '#07c98b',
            'canceled':     '#9691a4',
            'failed':       '#f23c49',
        }
        color = colors.get(obj.status, '#9691a4')
        return format_html(
            '<span style="display:inline-block;padding:.25rem .65rem;'
            'border-radius:50rem;background:{};color:#fff;font-size:.75rem;'
            'font-weight:700;white-space:nowrap;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description='خطای پرداخت')
    def payment_error_display(self, obj):
        if not obj.payment_error:
            return mark_safe('<span style="color:#9691a4;">—</span>')
        return format_html(
            '<pre style="white-space:pre-wrap;direction:ltr;text-align:left;'
            'background:#f9f8fa;padding:.6rem;border-radius:.5rem;'
            'max-height:200px;overflow:auto;font-size:.8rem;margin:0;">{}</pre>',
            obj.payment_error,
        )

    # ---- Actions ----

    @admin.action(description='➡️ انتقال به «در حال آماده‌سازی»')
    def mark_processing(self, request, queryset):
        n = queryset.filter(status=GuestOrder.Status.PAID).update(
            status=GuestOrder.Status.PROCESSING
        )
        self.message_user(request, f'{n} سفارش به «در حال آماده‌سازی» منتقل شد.')

    @admin.action(description='📦 انتقال به «ارسال شده»')
    def mark_shipped(self, request, queryset):
        n = queryset.filter(status=GuestOrder.Status.PROCESSING).update(
            status=GuestOrder.Status.SHIPPED
        )
        self.message_user(request, f'{n} سفارش به «ارسال شده» منتقل شد.')

    @admin.action(description='✅ انتقال به «تحویل داده شده»')
    def mark_delivered(self, request, queryset):
        n = queryset.filter(status=GuestOrder.Status.SHIPPED).update(
            status=GuestOrder.Status.DELIVERED
        )
        self.message_user(request, f'{n} سفارش به «تحویل داده شده» منتقل شد.')

    @admin.action(description='❌ لغو سفارش (فقط پرداخت‌نشده‌ها)')
    def mark_canceled(self, request, queryset):
        n = queryset.filter(
            status__in=[
                GuestOrder.Status.PENDING,
                GuestOrder.Status.INQUIRY_OK,
                GuestOrder.Status.AWAITING_OTP,
                GuestOrder.Status.FAILED,
            ]
        ).update(status=GuestOrder.Status.CANCELED)
        self.message_user(request, f'{n} سفارش لغو شد.')

    @admin.action(description='🧹 پاک کردن پیام خطای پرداخت')
    def clear_payment_error(self, request, queryset):
        n = queryset.exclude(payment_error='').update(payment_error='')
        self.message_user(request, f'پیام خطای {n} سفارش پاک شد.')


from django.utils import timezone


@admin.register(SupportOrderRequest)
class SupportOrderRequestAdmin(admin.ModelAdmin):
    """
    پنل مدیریت درخواست‌های تماس پشتیبان
    """

    # ---- لیست ----
    list_display = (
        'phone_display',
        'national_id_display',
        'product_link',
        'status_badge',
        'admin_note_preview',
        'created_at',
        'contacted_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'phone_number', 'national_id',
        'admin_note', 'product__title',
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 30
    list_select_related = ('product',)

    # ---- جزئیات ----
    readonly_fields = (
        'phone_display',
        'national_id_display',
        'product_link',
        'source_ip',
        'user_agent',
        'created_at',
        'updated_at',
        'contacted_at',
    )

    fieldsets = (
        ('اطلاعات تماس', {
            'fields': (
                'phone_display', 'national_id_display',
            ),
        }),
        ('وضعیت پیگیری', {
            'fields': (
                'status', 'contacted_at', 'admin_note',
            ),
        }),
        ('محصول مرتبط', {
            'fields': ('product_link',),
            'classes': ('collapse',),
        }),
        ('اطلاعات فنی', {
            'fields': (
                'source_ip', 'user_agent',
                'created_at', 'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )

    actions = (
        'mark_contacted',
        'mark_ordered',
        'mark_unreachable',
        'mark_canceled',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

    # سفارش پشتیبان از فرانت ساخته می‌شه، نه از پنل
    def has_add_permission(self, request):
        return False

    # ---- ستون‌ها ----

    @admin.display(description='شماره تلفن', ordering='phone_number')
    def phone_display(self, obj):
        return format_html(
            '<a href="tel:{}" style="direction:ltr;display:inline-block;'
            'font-weight:700;color:#0d6efd;text-decoration:none;">{}</a>',
            obj.phone_number, obj.phone_number,
        )

    @admin.display(description='کد ملی', ordering='national_id')
    def national_id_display(self, obj):
        return format_html(
            '<span style="direction:ltr;display:inline-block;">{}</span>',
            obj.national_id,
        )

    @admin.display(description='محصول')
    def product_link(self, obj):
        if not obj.product_id:
            return mark_safe('<span style="color:#9691a4;">—</span>')
        try:
            url = reverse('admin:market_product_change', args=[obj.product_id])
            return format_html('<a href="{}" target="_blank">{}</a>', url, obj.product.title)
        except Exception:
            return obj.product.title if obj.product else '—'

    @admin.display(description='وضعیت', ordering='status')
    def status_badge(self, obj):
        colors = {
            'pending':     '#fdbc31',
            'contacted':   '#3c76f2',
            'ordered':     '#07c98b',
            'canceled':    '#9691a4',
            'unreachable': '#f23c49',
        }
        color = colors.get(obj.status, '#9691a4')
        return format_html(
            '<span style="display:inline-block;padding:.25rem .65rem;'
            'border-radius:50rem;background:{};color:#fff;font-size:.75rem;'
            'font-weight:700;white-space:nowrap;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description='یادداشت')
    def admin_note_preview(self, obj):
        if not obj.admin_note:
            return mark_safe('<span style="color:#9691a4;">—</span>')
        truncated = obj.admin_note[:60]
        if len(obj.admin_note) > 60:
            truncated += '…'
        return truncated

    # ---- Actions ----

    @admin.action(description='📞 علامت‌گذاری به‌عنوان «تماس گرفته شد»')
    def mark_contacted(self, request, queryset):
        n = queryset.filter(
            status__in=[
                SupportOrderRequest.Status.PENDING,
                SupportOrderRequest.Status.UNREACHABLE,
            ]
        ).update(
            status=SupportOrderRequest.Status.CONTACTED,
            contacted_at=timezone.now(),
        )
        self.message_user(request, f'{n} درخواست به «تماس گرفته شد» تغییر یافت.')

    @admin.action(description='✅ علامت‌گذاری به‌عنوان «سفارش ثبت شد»')
    def mark_ordered(self, request, queryset):
        n = queryset.filter(
            status__in=[
                SupportOrderRequest.Status.PENDING,
                SupportOrderRequest.Status.CONTACTED,
            ]
        ).update(
            status=SupportOrderRequest.Status.ORDERED,
            contacted_at=timezone.now(),
        )
        self.message_user(request, f'{n} درخواست به «سفارش ثبت شد» تغییر یافت.')

    @admin.action(description='📵 علامت‌گذاری به‌عنوان «پاسخگو نبود»')
    def mark_unreachable(self, request, queryset):
        n = queryset.filter(
            status__in=[
                SupportOrderRequest.Status.PENDING,
                SupportOrderRequest.Status.CONTACTED,
            ]
        ).update(status=SupportOrderRequest.Status.UNREACHABLE)
        self.message_user(request, f'{n} درخواست به «پاسخگو نبود» تغییر یافت.')

    @admin.action(description='❌ لغو درخواست')
    def mark_canceled(self, request, queryset):
        n = queryset.exclude(
            status=SupportOrderRequest.Status.CANCELED,
        ).update(status=SupportOrderRequest.Status.CANCELED)
        self.message_user(request, f'{n} درخواست لغو شد.')

# ============================================================
#                    سفارشی‌سازی هدر ادمین
# ============================================================

admin.site.site_header = _("🛒 پنل مدیریت وین مارکت")
admin.site.site_title = _("وین مارکت")
admin.site.index_title = _("مدیریت فروشگاه")
