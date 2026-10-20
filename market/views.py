import re

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from accounts.models import Address
from core.models import City, Province
from payment.services.create_invoice import create_market_order_invoice
from .forms import AddressForm, ProductForm
from .models import (
    Product, Category, SupplierProfile, OrderItem, Review,
    Cart, CartItem, Variant, OrderAddress, Order,
    OrderShipping, ProductImage, ProductFeature, Feature, ShippingMethod,
)
from django.views.generic import TemplateView, DetailView, View, ListView
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django_iranian_payment.contrib.django import services
from payment.models import Invoice, Payment, Transaction, Wallet
from payment.services.zarinpal_flow import callback_url, prepare_gateway_bridge
from django.db.models.functions import Coalesce
import json
import jdatetime
from datetime import timedelta
from django.db.models.functions import TruncDate
from django.http import JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from .utils.slug_utils import generate_english_slug, has_persian
import math


# ============================================================
# لندینگ پیج
# ============================================================
class MarketLandingView(TemplateView):
    template_name = "market/landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()

        active_product = (
            Product.objects
            .filter(
                status=Product.Status.ACTIVE,
                campaign_start__lte=now,
                campaign_end__gte=now,
            )
            .select_related("supplier", "category")
            .prefetch_related("images", "variants", "features__feature")
            .first()
        )

        if not active_product:
            active_product = (
                Product.objects
                .filter(status=Product.Status.ACTIVE)
                .select_related("supplier", "category")
                .prefetch_related("images", "variants", "features__feature")
                .first()
            )

        ctx["active_product"] = active_product

        if active_product:
            variants_stock = (
                active_product.variants.aggregate(total=Sum("stock"))["total"] or 0
            )
            total_stock = (
                variants_stock
                if active_product.variants.exists()
                else active_product.stock
            )

            sold = (
                OrderItem.objects
                .filter(
                    product=active_product,
                    order__status__in=["paid", "processing", "shipped", "delivered"],
                )
                .aggregate(total=Sum("quantity"))["total"]
                or 0
            )

            initial_stock = total_stock + sold
            progress = int((sold / initial_stock) * 100) if initial_stock else 0

            campaign_end_ts = None
            campaign_end_value = active_product.campaign_end
            if campaign_end_value:
                if hasattr(campaign_end_value, "tzinfo") and campaign_end_value.tzinfo is None:
                    try:
                        campaign_end_value = campaign_end_value.replace(
                            tzinfo=ZoneInfo("Asia/Tehran")
                        )
                    except Exception:
                        campaign_end_value = campaign_end_value.replace(tzinfo=dt_timezone.utc)
                try:
                    campaign_end_ts = int(campaign_end_value.timestamp() * 1000)
                except Exception:
                    campaign_end_ts = None

            ctx["campaign"] = {
                "product": active_product,
                "stock": total_stock,
                "sold": sold,
                "progress": min(progress, 100),
                "remaining_seconds": active_product.remaining_time,
                "campaign_end_ts": campaign_end_ts,
            }

            # ---- طرح اقساط (۴ قسط از حقوق تامین اجتماعی) ----
            INSTALLMENT_COUNT = 4
            final_price = active_product.final_price
            # مبلغ هر قسط، رُند شده به هزار تومان (به پایین)
            regular = math.floor(final_price / INSTALLMENT_COUNT / 1000) * 1000
            last = final_price - regular * (INSTALLMENT_COUNT - 1)

            ctx["installment_plan"] = {
                "count": INSTALLMENT_COUNT,
                "regular": regular,
                "last": last,
                "is_uniform": regular == last,
                "total": final_price,
            }

        ctx["categories"] = Category.objects.filter(is_active=True)
        ctx["vendors"] = (
            SupplierProfile.objects
            .filter(is_active=True)
            .annotate(products_count=Count("products", distinct=True))
            .order_by("-created_at")[:6]
        )
        ctx["campaign_product_url"] = (
            reverse("market:guest_checkout", kwargs={"product_id": active_product.pk})
            if active_product else None
        )

        return ctx

# ============================================================
# صفحه محصول
# ============================================================
class ProductDetailView(DetailView):
    model = Product
    template_name = "market/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return (
            Product.objects
            .select_related("supplier", "category")
            .prefetch_related(
                "images", "variants", "features__feature",
                "reviews__user",
            )
        )

    def get_object(self, queryset=None):
        qs = queryset or self.get_queryset()
        return get_object_or_404(
            qs,
            slug=self.kwargs.get("slug"),
            pk=self.kwargs.get("pk"),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object

        # ---------- آمار نظرات ----------
        active_reviews = product.reviews.filter(is_active=True)
        ctx["reviews"] = active_reviews.order_by("-created_at")
        ctx["reviews_count"] = active_reviews.count()

        avg = active_reviews.aggregate(r=Avg("rating"))["r"]
        ctx["avg_rating"] = round(avg, 1) if avg else 0

        # توزیع امتیازها (۵ تا ۱)
        dist = []
        total = ctx["reviews_count"] or 1
        for star in range(5, 0, -1):
            count = active_reviews.filter(rating=star).count()
            percent = int((count / total) * 100)
            dist.append({"star": star, "count": count, "percent": percent})
        ctx["rating_distribution"] = dist

        # ---------- تعداد موجودی ----------
        variants_stock = product.variants.aggregate(total=Sum("stock"))["total"] or 0
        ctx["total_stock"] = variants_stock if product.variants.exists() else product.stock

        # ---------- تایمر کمپین ----------
        campaign_end_ts = None
        if product.campaign_end:
            end_val = product.campaign_end
            if hasattr(end_val, "tzinfo") and end_val.tzinfo is None:
                try:
                    end_val = end_val.replace(tzinfo=ZoneInfo("Asia/Tehran"))
                except Exception:
                    end_val = end_val.replace(tzinfo=dt_timezone.utc)
            try:
                campaign_end_ts = int(end_val.timestamp() * 1000)
            except Exception:
                campaign_end_ts = None
        ctx["campaign_end_ts"] = campaign_end_ts
        ctx["is_in_campaign"] = product.is_on_campaign

        # ---------- نظر خود کاربر ----------
        if self.request.user.is_authenticated:
            ctx["user_review"] = product.reviews.filter(
                user=self.request.user
            ).first()
            ctx["user_bought"] = OrderItem.objects.filter(
                product=product,
                order__user=self.request.user,
                order__status__in=["paid", "processing", "shipped", "delivered"],
            ).exists()
        else:
            ctx["user_review"] = None
            ctx["user_bought"] = False

        # ---------- اطلاعات فروشنده ----------
        if product.supplier:
            ctx["vendor_products_count"] = product.supplier.products.count()

        # ---------- آیتم‌های این محصول در سبد (برای وضعیت دکمه) ----------
        # از -1 برای "بدون variant" استفاده می‌کنیم
        ctx["cart_variant_ids"] = []
        if self.request.user.is_authenticated:
            try:
                cart = Cart.objects.get(user=self.request.user)
                for item in cart.items.filter(product=product):
                    ctx["cart_variant_ids"].append(item.variant_id if item.variant_id else -1)
            except Cart.DoesNotExist:
                pass

        return ctx

    def post(self, request, *args, **kwargs):
        """ثبت یا ویرایش نظر کاربر"""
        self.object = self.get_object()
        product = self.object

        if not request.user.is_authenticated:
            return JsonResponse({"error": "login_required"}, status=401)

        rating = request.POST.get("rating")
        comment = (request.POST.get("comment") or "").strip()

        if not rating or not comment:
            return JsonResponse({"error": "rating_and_comment_required"}, status=400)

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            return JsonResponse({"error": "invalid_rating"}, status=400)

        if len(comment) < 5:
            return JsonResponse({"error": "comment_too_short"}, status=400)

        is_verified = OrderItem.objects.filter(
            product=product,
            order__user=request.user,
            order__status__in=["paid", "processing", "shipped", "delivered"],
        ).exists()

        review, created = Review.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                "rating": rating,
                "comment": comment,
                "is_verified_buyer": is_verified,
                "is_active": True,
            },
        )

        return JsonResponse({
            "success": True,
            "created": created,
            "review": {
                "id": review.id,
                "rating": review.rating,
                "comment": review.comment,
                "user_name": review.user.nickname or review.user.phone_number,
                "user_initial": (review.user.nickname or review.user.phone_number)[:1],
                "is_verified_buyer": review.is_verified_buyer,
                "created_at": str(review.created_at),
            },
        })


# ============================================================
# افزودن به سبد خرید (AJAX)
# ============================================================
class CartAddView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "login_required", "message": "برای افزودن به سبد باید وارد شوید"},
                status=401,
            )

        product = get_object_or_404(Product, pk=pk)

        variant_id = request.POST.get("variant_id")
        try:
            quantity = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        quantity = max(1, quantity)

        variant = None
        if variant_id:
            variant = get_object_or_404(Variant, pk=variant_id, product=product)

        # چک موجودی
        available = variant.stock if variant else product.stock
        if available <= 0:
            return JsonResponse(
                {"error": "out_of_stock", "message": "این محصول ناموجود است"},
                status=400,
            )

        cart, _ = Cart.objects.get_or_create(user=request.user)

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={"quantity": quantity},
        )
        if not created:
            new_qty = item.quantity + quantity
            if new_qty > available:
                return JsonResponse(
                    {
                        "error": "not_enough_stock",
                        "message": f"فقط {available} عدد موجود است",
                    },
                    status=400,
                )
            item.quantity = new_qty
            item.save()

        return JsonResponse({
            "success": True,
            "message": "محصول به سبد خرید اضافه شد ✅",
            "cart_count": cart.items_count,
            "cart_total": cart.total_price,
        })


# ============================================================
# صفحه سبد خرید
# ============================================================
class CartDetailView(LoginRequiredMixin, DetailView):
    template_name = "market/cart.html"
    context_object_name = "cart"

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cart = self.object

        items = (
            cart.items
            .select_related("product__supplier", "variant")
            .prefetch_related("product__images")
            .order_by("added_at")
        )

        # محاسبه هزینه ارسال (per supplier)
        items_total = sum(item.subtotal for item in items)

        ctx["items"] = items
        ctx["items_total"] = items_total
        ctx["shipping_total"] = 0
        ctx["grand_total"] = items_total

        # پیشنهاد محصولات (۴ تا تصادفی به‌جز موارد موجود در سبد)
        existing_product_ids = [i.product_id for i in items]
        ctx["suggestions"] = (
            Product.objects
            .filter(status=Product.Status.ACTIVE)
            .exclude(id__in=existing_product_ids)
            .order_by("?")[:4]
        )
        return ctx


# ============================================================
# Mini Cart (HTML برای پنل کشویی)
# ============================================================
class MiniCartView(LoginRequiredMixin, View):
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items = (
            cart.items
            .select_related("product", "variant")
            .order_by("-added_at")
        )
        return render(request, "market/partials/_mini_cart.html", {
            "cart": cart,
            "items": items,
            "embed": True,
        })


# ============================================================
# helpers
# ============================================================
def _cart_totals(cart):
    """محاسبه مبالغ سبد (بدون هزینه ارسال — پس‌کرایه)"""
    items = cart.items.select_related("product").all()
    items_total = sum(item.subtotal for item in items)
    return {
        "items_total": items_total,
        "shipping_total": 0,
        "grand_total": items_total,
        "cart_count": cart.items_count,
    }


# ============================================================
# آپدیت تعداد یک آیتم
# ============================================================
class CartUpdateView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        try:
            item = CartItem.objects.select_related("product", "variant").get(
                id=item_id, cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return JsonResponse({"error": "not_found"}, status=404)

        try:
            new_qty = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            return JsonResponse({"error": "invalid_quantity"}, status=400)

        new_qty = max(1, new_qty)
        available = item.variant.stock if item.variant else item.product.stock
        if new_qty > available:
            return JsonResponse({
                "error": "not_enough_stock",
                "message": f"فقط {available} عدد موجود است",
                "max_available": available,
            }, status=400)

        item.quantity = new_qty
        item.save()

        cart = item.cart
        totals = _cart_totals(cart)

        return JsonResponse({
            "success": True,
            "quantity": new_qty,
            "item_subtotal": item.subtotal,
            **totals,
        })


# ============================================================
# حذف یک آیتم
# ============================================================
class CartRemoveView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        try:
            item = CartItem.objects.select_related("cart").get(
                id=item_id, cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return JsonResponse({"error": "not_found"}, status=404)

        cart = item.cart
        item.delete()

        # اگه سبد خالی شد
        if not cart.items.exists():
            cart.delete()
            return JsonResponse({
                "success": True,
                "items_total": 0,
                "shipping_total": 0,
                "grand_total": 0,
                "cart_count": 0,
            })

        totals = _cart_totals(cart)
        return JsonResponse({
            "success": True,
            **totals,
        })


# ============================================================
# خالی کردن کل سبد
# ============================================================
class CartClearView(LoginRequiredMixin, View):
    def post(self, request):
        Cart.objects.filter(user=request.user).delete()
        return JsonResponse({
            "success": True,
            "items_total": 0,
            "shipping_total": 0,
            "grand_total": 0,
            "cart_count": 0,
        })


# ============================================================
# Checkout — شروع
# ============================================================
class StartCheckoutView(LoginRequiredMixin, View):
    """
    از صفحه سبد خرید: "ادامه فرآیند خرید"
    - اگه Order نیمه‌کاره وجود داره، ادامه بده
    - وگرنه Order جدید بساز
    """
    def post(self, request):
        cart = getattr(request.user, 'cart', None)
        if not cart or not cart.items.exists():
            messages.error(request, "سبد خرید شما خالی است.")
            return redirect('market:cart_detail')

        # ادامه‌ی سفارش نیمه‌کاره (اگه وجود داره)
        pending_order = Order.objects.filter(
            user=request.user,
            status=Order.Status.PENDING,
        ).order_by('-created_at').first()

        # اگه سفارش نیمه‌کاره داره ولی آدرسش ثبت شده، یعنی تو مرحله تایید بود
        # ولی اگه کاربر دوباره از سبد شروع کرد، یعنی می‌خواد از اول
        if pending_order and hasattr(pending_order, 'order_address'):
            # سفارش قبلی رو پاک کن
            pending_order.delete()
            pending_order = None

        if not pending_order:
            pending_order = Order.objects.create(
                user=request.user,
                status=Order.Status.PENDING,
            )

        request.session['pending_order_id'] = pending_order.id
        request.session.pop('checkout_address_id', None)
        return redirect('market:checkout')


# ============================================================
# Checkout — صفحه اصلی (آدرس)
# ============================================================
class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = "market/checkout.html"

    def get(self, request, *args, **kwargs):
        order_id = request.session.get('pending_order_id')
        if not order_id:
            return redirect('market:cart_detail')

        order = Order.objects.filter(
            pk=order_id, user=request.user
        ).first()
        if not order:
            return redirect('market:cart_detail')

        # اگه سفارش قبلاً آدرس گرفته، برو به مرحله تایید
        if hasattr(order, 'order_address'):
            return redirect('market:checkout_confirm')

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order_id = self.request.session.get('pending_order_id')
        order = Order.objects.filter(
            pk=order_id, user=self.request.user
        ).first()

        ctx['order'] = order
        ctx['addresses'] = self.request.user.addresses.all().order_by('-is_default', '-created_at')
        ctx['addresses_count'] = ctx['addresses'].count()
        ctx['max_addresses'] = 5
        ctx['can_add_more'] = ctx['addresses_count'] < 5
        ctx['default_address'] = self.request.user.addresses.filter(is_default=True).first()
        ctx['provinces'] = Province.objects.all().order_by('name')
        ctx['cart_items'] = order.user.cart.items.select_related('product', 'variant').all()
        ctx['step'] = 1

        # shipping/totals
        ctx['items_total'] = sum(i.subtotal for i in ctx['cart_items'])
        ctx['shipping_total'] = 0
        ctx['grand_total'] = ctx['items_total']

        return ctx


# ============================================================
# Checkout — ذخیره آدرس جدید
# ============================================================
class SaveAddressView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.addresses.count() >= 5:
            return JsonResponse({
                'success': False,
                'error': 'max_addresses',
                'message': 'حداکثر ۵ آدرس می‌توانید ذخیره کنید.',
            })

        form = AddressForm(request.POST)
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'error': 'invalid',
                'errors': form.errors,
            })

        address = form.save(commit=False)
        address.user = request.user
        if request.user.addresses.count() == 0:
            address.is_default = True
        address.save()

        return JsonResponse({
            'success': True,
            'address_id': address.id,
        })


# ============================================================
# Checkout — ویرایش آدرس
# ============================================================
class UpdateAddressView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        address = Address.objects.filter(
            pk=address_id, user=request.user
        ).first()
        if not address:
            return JsonResponse({'success': False, 'error': 'not_found'})

        form = AddressForm(request.POST, instance=address)
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'error': 'invalid',
                'errors': form.errors,
            })
        form.save()
        return JsonResponse({'success': True, 'address_id': address.id})


# ============================================================
# Checkout — حذف آدرس
# ============================================================
class DeleteAddressView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        address = Address.objects.filter(
            pk=address_id, user=request.user
        ).first()
        if not address:
            return JsonResponse({'success': False, 'error': 'not_found'})

        was_default = address.is_default
        address.delete()

        # اگه پیش‌فرض بود، یکی دیگه رو پیش‌فرض کن
        if was_default:
            first = request.user.addresses.first()
            if first:
                first.is_default = True
                first.save()

        return JsonResponse({
            'success': True,
            'remaining': request.user.addresses.count(),
        })


# ============================================================
# Checkout — استفاده از آدرس موجود
# ============================================================
class UseAddressView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        order_id = request.session.get('pending_order_id')
        if not order_id:
            return JsonResponse({'success': False, 'error': 'no_order'})

        order = Order.objects.filter(pk=order_id, user=request.user).first()
        address = Address.objects.filter(pk=address_id, user=request.user).first()
        if not order or not address:
            return JsonResponse({'success': False, 'error': 'not_found'})

        request.session['checkout_address_id'] = address.id
        return JsonResponse({
            'success': True,
            'redirect': reverse('market:checkout_confirm'),
        })


# ============================================================
# Checkout — مرحله ۲ (تایید نهایی)
# ============================================================
# ============================================================
# Checkout — تغییر آدرس انتخاب‌شده
# ============================================================
class ChangeAddressView(LoginRequiredMixin, View):
    """کاربر رو برمی‌گردونه به مرحله ۱ تا آدرس جدید انتخاب کنه"""
    def post(self, request):
        order_id = request.session.get('pending_order_id')
        if not order_id:
            return redirect('market:cart_detail')

        order = Order.objects.filter(pk=order_id, user=request.user).first()
        if order:
            OrderAddress.objects.filter(order=order).delete()

        request.session.pop('checkout_address_id', None)
        return redirect('market:checkout')


# ============================================================
# Checkout — مرحله ۲ (تایید نهایی)
# ============================================================
# ============================================================
# Checkout — مرحله ۲ (تایید نهایی)
# ============================================================
class CheckoutConfirmView(LoginRequiredMixin, TemplateView):
    template_name = "market/checkout_confirm.html"

    def get(self, request, *args, **kwargs):
        order_id = request.session.get('pending_order_id')
        address_id = request.session.get('checkout_address_id')
        if not order_id or not address_id:
            return redirect('market:checkout')

        order = Order.objects.filter(pk=order_id, user=request.user).first()
        address = Address.objects.filter(pk=address_id, user=request.user).first()
        if not order or not address:
            return redirect('market:checkout')

        return super().get(request, *args, **kwargs)

    # ------------------------------------------------------------------
    # helper: گروه‌بندی سبد بر اساس فروشنده + محاسبه روش‌های ارسال
    # ------------------------------------------------------------------
    def _build_supplier_groups(self, cart_items):
        """
        برمی‌گردونه:
        [
            {
                "supplier": <SupplierProfile or None>,
                "supplier_name": "برند A",
                "items": [<CartItem>, ...],
                "subtotal": 1_000_000,
                "available_methods": [<ShippingMethod>, ...],
                "default_method_id": 3,
            },
            ...
        ]
        """
        from .models import ShippingMethod  # جلوگیری از circular import

        # گروه‌بندی بر اساس supplier_id (None هم یه گروه جدا)
        groups_map = {}
        for item in cart_items:
            key = item.product.supplier_id or 0
            if key not in groups_map:
                groups_map[key] = {
                    "supplier": item.product.supplier,
                    "supplier_name": (
                        item.product.supplier.brand_name
                        if item.product.supplier else "فروشنده"
                    ),
                    "items": [],
                    "subtotal": 0,
                }
            groups_map[key]["items"].append(item)
            groups_map[key]["subtotal"] += item.subtotal

        # برای هر گروه، intersection روش‌های ارسال محصولات
        groups = []
        for key, group in groups_map.items():
            product_ids = [it.product_id for it in group["items"]]
            products = Product.objects.filter(pk__in=product_ids).prefetch_related(
                "shipping_methods"
            )

            # intersection
            methods_sets = []
            for p in products:
                p_methods = set(
                    p.shipping_methods.filter(is_active=True).values_list("id", flat=True)
                )
                methods_sets.append(p_methods)

            common_ids = set.intersection(*methods_sets) if methods_sets else set()
            available = list(
                ShippingMethod.objects
                .filter(id__in=common_ids, is_active=True)
                .order_by("order", "name")
            )

            group["available_methods"] = available
            group["default_method_id"] = available[0].id if available else None

            # مرتب‌سازی بر اساس id برای ثبات ترتیب
            groups.append(group)

        groups.sort(key=lambda g: (g["supplier"] is None, g["supplier_name"]))
        return groups

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order_id = self.request.session.get('pending_order_id')
        address_id = self.request.session.get('checkout_address_id')

        order = Order.objects.get(pk=order_id, user=self.request.user)
        address = Address.objects.get(pk=address_id, user=self.request.user)

        ctx['order'] = order
        ctx['selected_address'] = address
        ctx['step'] = 2

        cart = self.request.user.cart
        cart_items = list(
            cart.items
            .select_related('product', 'variant', 'product__supplier')
            .all()
        )
        ctx['cart_items'] = cart_items

        items_total = sum(i.subtotal for i in cart_items)
        ctx['items_total'] = items_total
        ctx['shipping_total'] = 0
        ctx['grand_total'] = items_total

        # گروه‌های فروشنده
        supplier_groups = self._build_supplier_groups(cart_items)
        ctx['supplier_groups'] = supplier_groups
        ctx['has_multiple_suppliers'] = len(supplier_groups) > 1

        # کیف پول
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        ctx['wallet'] = wallet
        ctx['wallet_balance'] = wallet.balance
        ctx['wallet_sufficient'] = wallet.balance >= items_total
        if wallet.balance < items_total:
            ctx['wallet_shortage'] = items_total - wallet.balance
        else:
            ctx['wallet_shortage'] = 0

        # موجودی کیف پول بعد از پرداخت (برای نمایش در مودال تایید)
        ctx['wallet_after_payment'] = max(wallet.balance - items_total, 0)

        # پیش‌فرض‌های گیرنده
        ctx['default_receiver_name'] = (
            self.request.user.nickname or self.request.user.phone_number
        )
        ctx['default_receiver_phone'] = self.request.user.phone_number

        return ctx

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------
    def post(self, request, *args, **kwargs):
        order_id = request.session.get('pending_order_id')
        address_id = request.session.get('checkout_address_id')
        if not order_id or not address_id:
            return redirect('market:checkout')

        order = Order.objects.filter(pk=order_id, user=request.user).first()
        address = Address.objects.filter(pk=address_id, user=request.user).first()
        if not order or not address:
            return redirect('market:checkout')

        if order.status != Order.Status.PENDING:
            messages.warning(request, "این سفارش قابل پرداخت مجدد نیست.")
            return redirect('market:landing')

        cart = getattr(request.user, 'cart', None)
        if not cart or not cart.items.exists():
            messages.error(request, "سبد خرید شما خالی است.")
            return redirect('market:cart_detail')

        # ---- اطلاعات گیرنده ----
        receiver_name = (request.POST.get('receiver_name') or '').strip()
        receiver_phone = (request.POST.get('receiver_phone') or '').strip()
        if not receiver_name:
            receiver_name = request.user.nickname or request.user.phone_number
        if not receiver_phone:
            receiver_phone = request.user.phone_number

        if not re.match(r'^09\d{9}$', receiver_phone):
            messages.error(request, "شماره تماس گیرنده معتبر نیست.")
            return redirect('market:checkout_confirm')

        # ---- یادداشت ----
        customer_note = (request.POST.get('customer_note') or '').strip()

        # ---- روش پرداخت ----
        payment_method = request.POST.get('payment_method', 'gateway')
        if payment_method not in ('gateway', 'wallet'):
            payment_method = 'gateway'

        # ---- cart items ----
        cart_items = list(
            cart.items
            .select_related('product', 'variant', 'product__supplier')
            .all()
        )
        items_total = sum(i.subtotal for i in cart_items)

        # ---- گروه‌های فروشنده برای اعتبارسنجی روش ارسال ----
        supplier_groups = self._build_supplier_groups(cart_items)

        # ---- اعتبارسنجی: هر گروه باید method_id معتبر داشته باشه ----
        from .models import ShippingMethod
        selected_shipping = {}  # {supplier_id_or_0: ShippingMethod}
        for grp in supplier_groups:
            sup_key = grp['supplier'].id if grp['supplier'] else 0
            method_id = request.POST.get(f'shipping_method_{sup_key}')
            available_ids = [m.id for m in grp['available_methods']]

            if not available_ids:
                messages.error(
                    request,
                    f"برای فروشنده «{grp['supplier_name']}» روش ارسال فعالی وجود ندارد. "
                    f"لطفاً با پشتیبانی تماس بگیرید."
                )
                return redirect('market:checkout_confirm')

            try:
                method_id = int(method_id)
            except (TypeError, ValueError):
                method_id = grp['default_method_id']

            if method_id not in available_ids:
                method_id = grp['default_method_id']

            method = ShippingMethod.objects.filter(pk=method_id, is_active=True).first()
            if not method:
                messages.error(request, "روش ارسال انتخابی معتبر نیست.")
                return redirect('market:checkout_confirm')

            selected_shipping[sup_key] = method

        # ============================================================
        # Atomic
        # ============================================================
        try:
            with transaction.atomic():
                # === ۱. OrderAddress (snapshot) ===
                OrderAddress.objects.filter(order=order).delete()
                order_address = OrderAddress.from_user_address(
                    address,
                    receiver_name=receiver_name,
                    receiver_phone=receiver_phone,
                )
                order_address.order = order
                order_address.save()

                # === ۲. آپدیت order ===
                order.customer_note = customer_note
                order.save(update_fields=['customer_note', 'updated_at'])

                # === ۳. OrderItem ها از CartItem (snapshot) ===
                order.items.all().delete()

                for cart_item in cart_items:
                    variant_info = ''
                    if cart_item.variant and cart_item.variant.attributes:
                        variant_info = ' / '.join(
                            str(v) for v in cart_item.variant.attributes.values()
                        )

                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        variant=cart_item.variant,
                        product_title=cart_item.product.title,
                        variant_info=variant_info,
                        unit_price=cart_item.unit_price,
                        quantity=cart_item.quantity,
                        subtotal=cart_item.subtotal,
                        supplier=cart_item.product.supplier,
                    )

                # === ۴. OrderShipping per supplier ===
                OrderShipping.objects.filter(order=order).delete()
                for grp in supplier_groups:
                    sup = grp['supplier']
                    sup_key = sup.id if sup else 0
                    method = selected_shipping.get(sup_key)
                    if not method:
                        continue

                    OrderShipping.objects.create(
                        order=order,
                        supplier=sup,
                        shipping_method=method,
                        method_name=method.name,
                        method_slug=method.slug,
                    )

                # === ۵. Invoice ===
                Invoice.objects.filter(market_order=order).delete()
                invoice = create_market_order_invoice(order)

                # ============================================================
                # پرداخت از کیف پول
                # ============================================================
                if payment_method == 'wallet':
                    wallet = (
                        Wallet.objects
                        .select_for_update()
                        .get(user=request.user)
                    )
                    if wallet.balance < items_total:
                        raise ValidationError(
                            "موجودی کیف پول کافی نیست."
                        )

                    # کم کردن موجودی
                    wallet.balance -= items_total
                    wallet.save(update_fields=['balance', 'updated_at'])

                    # Payment (SUCCESS)
                    payment = Payment.objects.create(
                        user=request.user,
                        invoice=invoice,
                        amount=items_total,
                        payment_method=Payment.Method.WALLET,
                        status=Payment.Status.SUCCESS,
                        ref_id=f"WALLET-{invoice.invoice_number}",
                    )

                    # Invoice → paid
                    invoice.is_paid = True
                    invoice.paid_at = timezone.now()
                    invoice.save(update_fields=['is_paid', 'paid_at'])

                    # Order → PAID
                    order.status = Order.Status.PAID
                    order.save(update_fields=['status', 'updated_at'])

                    # Transaction کاربر
                    Transaction.objects.create(
                        user=request.user,
                        amount=items_total,
                        type=Transaction.Type.MARKET_ORDER_PAYMENT,
                        status=Transaction.Status.SUCCESS,
                        invoice=invoice,
                        payment=payment,
                        reference_id=f"WALLET-{invoice.invoice_number}",
                        description=(
                            f"پرداخت سفارش وین مارکت #{order.id} از کیف پول"
                        ),
                    )

                    # Cart پاک بشه
                    Cart.objects.filter(user=request.user).delete()

                    # session پاک بشه
                    for key in [
                        'pending_order_id', 'checkout_address_id',
                        'market_payment_authority', 'market_payment_amount',
                        'market_payment_order_id', 'market_payment_invoice_id',
                    ]:
                        request.session.pop(key, None)

                    messages.success(
                        request,
                        f"✅ پرداخت سفارش #{order.id} از کیف پول با موفقیت انجام شد."
                    )
                    return redirect('market:order_detail', pk=order.pk)

                # ============================================================
                # پرداخت از درگاه زرین‌پال
                # ============================================================
                payment_result, redirect_url = services.start_payment(
                    slug="zarinpal",
                    amount=items_total,
                    callback_url=callback_url('market:market_order_payment_callback'),
                    order_id=f"market_order_{order.id}",
                    description=f"پرداخت سفارش وین مارکت #{order.id}",
                    mobile=request.user.phone_number,
                )

                Payment.objects.create(
                    user=request.user,
                    invoice=invoice,
                    amount=items_total,
                    payment_method=Payment.Method.GATEWAY,
                    authority=payment_result.authority,
                    status=Payment.Status.PENDING,
                )

                # === session ===
                request.session['market_payment_authority'] = payment_result.authority
                request.session['market_payment_amount'] = items_total
                request.session['market_payment_order_id'] = order.id
                request.session['market_payment_invoice_id'] = invoice.id
                request.session.modified = True

        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('market:checkout_confirm')
        except Exception as e:
            messages.error(request, f"خطا در آماده‌سازی پرداخت: {str(e)}")
            return redirect('market:checkout_confirm')

        # === هدایت به درگاه ===
        return redirect(prepare_gateway_bridge(request, redirect_url))


# ============================================================
# Checkout — کالبک پرداخت وین مارکت
# ============================================================
@login_required
def market_order_payment_callback(request):
    """کالبک بازگشت از درگاه زرین‌پال برای پرداخت سفارش وین مارکت"""
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')

    if not authority:
        messages.error(request, "اطلاعات پرداخت یافت نشد.")
        return redirect('market:cart_detail')

    session_authority = request.session.get('market_payment_authority')
    order_id = request.session.get('market_payment_order_id')
    invoice_id = request.session.get('market_payment_invoice_id')
    amount = request.session.get('market_payment_amount', 0)

    if not session_authority or session_authority != authority or not order_id:
        messages.error(request, "اطلاعات پرداخت معتبر نیست.")
        return redirect('market:cart_detail')

    order = Order.objects.filter(pk=order_id, user=request.user).first()
    invoice = (
        Invoice.objects
        .filter(pk=invoice_id, market_order=order)
        .first()
    )
    payment = (
        Payment.objects
        .filter(authority=authority, invoice=invoice)
        .first()
    )

    if not order or not invoice or not payment:
        messages.error(request, "اطلاعات سفارش یافت نشد.")
        return redirect('market:cart_detail')

    # اگه قبلاً پرداخت شده
    if invoice.is_paid:
        messages.info(request, "این سفارش قبلاً پرداخت شده است.")
        return redirect('market:landing')

    # ============================================================
    # کاربر پرداخت نکرد / لغو کرد
    # ============================================================
    if status != 'OK':
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])
        messages.warning(request, "پرداخت توسط کاربر لغو شد یا ناموفق بود.")
        return redirect('market:checkout_confirm')

    # ============================================================
    # تأیید پرداخت
    # ============================================================
    try:
        result = services.verify_payment(slug="zarinpal", authority=authority)

        if result.status.lower() != 'complete':
            messages.error(request, f"پرداخت ناموفق بود. وضعیت: {result.status}")
            return redirect('market:checkout_confirm')

        with transaction.atomic():
            # === آپدیت Payment ===
            payment.status = Payment.Status.SUCCESS
            payment.ref_id = result.reference_id
            payment.save(update_fields=['status', 'ref_id'])

            # === آپدیت Invoice ===
            invoice.is_paid = True
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=['is_paid', 'paid_at'])

            # === آپدیت Order ===
            order.status = Order.Status.PAID
            order.save(update_fields=['status', 'updated_at'])

            # === Transaction کاربر ===
            Transaction.objects.create(
                user=request.user,
                amount=amount,
                type=Transaction.Type.MARKET_ORDER_PAYMENT,
                status=Transaction.Status.SUCCESS,
                invoice=invoice,
                payment=payment,
                reference_id=result.reference_id,
                description=(
                    f"پرداخت سفارش وین مارکت #{order.id} از طریق زرین‌پال "
                    f"- کد پیگیری: {result.reference_id}"
                ),
            )

            # === پاک کردن سبد کاربر ===
            Cart.objects.filter(user=request.user).delete()

    except Exception as e:
        messages.error(request, f"خطا در تأیید پرداخت: {str(e)}")
        return redirect('market:checkout_confirm')

    # === پاک کردن session ===
    for key in [
        'market_payment_authority', 'market_payment_amount',
        'market_payment_order_id', 'market_payment_invoice_id',
        'pending_order_id', 'checkout_address_id',
    ]:
        request.session.pop(key, None)

    messages.success(
        request,
        f"✅ پرداخت سفارش #{order.id} با موفقیت انجام شد. "
        f"کد پیگیری: {result.reference_id}"
    )
    return redirect('market:order_detail', pk=order.pk)


# ============================================================
# Checkout — AJAX: شهرهای یه استان
# ============================================================
class CitiesByProvinceView(View):
    def get(self, request):
        province_id = request.GET.get('province_id')
        if not province_id:
            return JsonResponse({'cities': []})
        try:
            province_id = int(province_id)
        except (TypeError, ValueError):
            return JsonResponse({'cities': []})

        cities = City.objects.filter(province_id=province_id).order_by('name')
        return JsonResponse({
            'cities': [{'id': c.id, 'name': c.name} for c in cities],
        })


class AddressDetailAPIView(LoginRequiredMixin, View):
    """AJAX: جزئیات یه آدرس برای ویرایش"""
    def get(self, request, address_id):
        address = Address.objects.filter(pk=address_id, user=request.user).first()
        if not address:
            return JsonResponse({'success': False})
        return JsonResponse({
            'success': True,
            'address': {
                'id': address.id,
                'title': address.title,
                'province_id': address.province_id,
                'city_id': address.city_id,
                'address': address.address,
                'plaque': address.plaque,
                'unit': address.unit,
                'postal_code': address.postal_code,
            }
        })


# ============================================================
# سفارشات من — لیست
# ============================================================
class OrderListView(LoginRequiredMixin, ListView):
    template_name = "market/orders.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        qs = (
            Order.objects
            .filter(user=self.request.user)
            .exclude(status=Order.Status.PENDING)  # فقط سفارشات نهایی‌شده
            .select_related("order_address")
            .prefetch_related("items__product", "shippings")
            .order_by("-created_at")
        )

        status = self.request.GET.get("status", "")
        if status and status in dict(Order.Status.choices):
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # --- محاسبه‌ی آمار ---
        all_orders = (
            Order.objects
            .filter(user=self.request.user)
            .exclude(status=Order.Status.PENDING)
        )
        counts = all_orders.aggregate(
            total=Count("id"),
            paid=Count("id", filter=Q(status=Order.Status.PAID)),
            processing=Count("id", filter=Q(status=Order.Status.PROCESSING)),
            shipped=Count("id", filter=Q(status=Order.Status.SHIPPED)),
            delivered=Count("id", filter=Q(status=Order.Status.DELIVERED)),
            canceled=Count("id", filter=Q(status=Order.Status.CANCELED)),
            returned=Count("id", filter=Q(status=Order.Status.RETURNED)),
        )
        ctx["counts"] = counts
        ctx["pending_count"] = counts.get("pending", 0)

        # --- attribute های محاسباتی برای هر سفارش ---
        for order in ctx["orders"]:
            items = list(order.items.all())  # از prefetch cache استفاده می‌کنه
            order.items_count = sum(i.quantity for i in items)
            order.first_item_title = items[0].product_title if items else None

            supplier_ids = set()
            for s in order.shippings.all():
                if s.supplier_id:
                    supplier_ids.add(s.supplier_id)
            # اگه shippings خالی بود، از روی items حساب کن
            if not supplier_ids:
                supplier_ids = {i.supplier_id for i in items if i.supplier_id}
            order.suppliers_count = len(supplier_ids)

        ctx["current_status"] = self.request.GET.get("status", "")
        return ctx


# ============================================================
# سفارشات من — جزئیات
# ============================================================
class OrderDetailView(LoginRequiredMixin, DetailView):
    template_name = "market/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return (
            Order.objects
            .filter(user=self.request.user)
            .select_related(
                "order_address",
                "order_address__province",
                "order_address__city",
            )
            .prefetch_related(
                "items__product",
                "items__supplier",
                "shippings__supplier",
                "shippings__shipping_method",
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = self.object

        # --- Timeline ---
        status_order = [
            Order.Status.PAID,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        ]

        is_canceled = order.status in [Order.Status.CANCELED, Order.Status.RETURNED]

        current_idx = -1
        if order.status in status_order:
            current_idx = status_order.index(order.status)

        steps = [
            {
                "key": "created",
                "label": "ثبت سفارش",
                "icon": "bi-cart-check-fill",
                "done": True,
            },
            {
                "key": "paid",
                "label": "پرداخت",
                "icon": "bi-credit-card-fill",
                "done": order.status in status_order,
            },
            {
                "key": "processing",
                "label": "آماده‌سازی",
                "icon": "bi-box-seam-fill",
                "done": current_idx >= 1,
            },
            {
                "key": "shipped",
                "label": "ارسال",
                "icon": "bi-truck",
                "done": current_idx >= 2,
            },
            {
                "key": "delivered",
                "label": "تحویل",
                "icon": "bi-bag-check-fill",
                "done": current_idx >= 3,
            },
        ]

        ctx["steps"] = steps
        ctx["is_canceled"] = is_canceled

        # --- گروه‌بندی items per supplier ---
        groups_map = {}
        for item in order.items.all():
            key = item.supplier_id or 0
            if key not in groups_map:
                groups_map[key] = {
                    "supplier": item.supplier,
                    "supplier_name": (
                        item.supplier.brand_name if item.supplier else "فروشنده"
                    ),
                    "items": [],
                    "subtotal": 0,
                }
            groups_map[key]["items"].append(item)
            groups_map[key]["subtotal"] += item.subtotal

        # اتصال shipping method به هر گروه
        shipping_map = {s.supplier_id: s for s in order.shippings.all()}
        supplier_groups = []
        for key, grp in groups_map.items():
            grp["shipping"] = shipping_map.get(key) if key else None
            supplier_groups.append(grp)

        supplier_groups.sort(key=lambda g: (g["supplier"] is None, g["supplier_name"]))
        ctx["supplier_groups"] = supplier_groups

        # --- خلاصه مالی ---
        ctx["items_total"] = sum(g["subtotal"] for g in supplier_groups)
        ctx["grand_total"] = ctx["items_total"]

        # --- دکمه تأیید دریافت ---
        ctx["can_confirm_delivery"] = (
                order.status in [
            Order.Status.PAID,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
        ]
                and not order.delivered_confirmed_at
                and not order.supplier_payment_released_at
        )

        # --- فاکتور ---
        ctx["invoice"] = getattr(order, "invoice", None)

        return ctx


# ============================================================
# واریز سهم فروشنده‌ها (بعد از تأیید دریافت)
# ============================================================
def _release_supplier_payments(order):
    """
    واریز subtotal هر فروشنده به کیف پولش
    این تابع فقط وقتی صدا زده می‌شه که کاربر تأیید دریافت کرده باشه.
    """
    items = order.items.select_related("supplier").all()

    supplier_amounts = {}
    for item in items:
        if not item.supplier_id:
            continue
        supplier_amounts[item.supplier_id] = (
            supplier_amounts.get(item.supplier_id, 0) + item.subtotal
        )

    invoice = getattr(order, "invoice", None)

    for supplier_id, amount in supplier_amounts.items():
        if amount <= 0:
            continue

        supplier = (
            SupplierProfile.objects
            .select_related("user")
            .filter(pk=supplier_id)
            .first()
        )
        if not supplier or not supplier.user:
            continue

        supplier_user = supplier.user

        # واریز به کیف پول
        wallet, _ = Wallet.objects.get_or_create(user=supplier_user)
        Wallet.objects.filter(pk=wallet.pk).update(
            balance=F("balance") + amount,
            updated_at=timezone.now(),
        )

        # ثبت تراکنش
        Transaction.objects.create(
            user=supplier_user,
            amount=amount,
            type=Transaction.Type.MARKET_ORDER_SUPPLIER_PAYMENT,
            status=Transaction.Status.SUCCESS,
            invoice=invoice,
            payment=None,
            reference_id=f"MK-SUP-{order.id}-{supplier_id}",
            description=(
                f"واریز سهم فروشنده از سفارش {order.number or ('#' + str(order.id))}"
            ),
        )


# ============================================================
# تأیید دریافت مرسوله توسط مشتری
# ============================================================
class ConfirmDeliveryView(LoginRequiredMixin, View):
    """
    کاربر تأیید می‌کنه که مرسوله رو دریافت کرده
    → وضعیت DELIVERED میشه و پول به فروشنده‌ها واریز میشه
    """

    def post(self, request, pk):
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=pk,
            user=request.user,
        )

        # چک قبلاً تأیید نشده باشه
        if order.status == Order.Status.DELIVERED or order.delivered_confirmed_at:
            messages.info(request, "این سفارش قبلاً تحویل تأیید شده است.")
            return redirect("market:order_detail", pk=order.pk)

        # چک پرداخت شده باشه
        if order.status not in [
            Order.Status.PAID,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
        ]:
            messages.error(
                request,
                "این سفارش در وضعیتی نیست که بتونه تأیید دریافت بشه.",
            )
            return redirect("market:order_detail", pk=order.pk)

        # چک واریز قبلی
        if order.supplier_payment_released_at:
            messages.info(
                request,
                "پرداخت این سفارش قبلاً به فروشنده‌ها واریز شده است.",
            )
            return redirect("market:order_detail", pk=order.pk)

        try:
            with transaction.atomic():
                now = timezone.now()

                # واریز به فروشنده‌ها
                _release_supplier_payments(order)

                # آپدیت سفارش
                order.status = Order.Status.DELIVERED
                order.delivered_at = now
                order.delivered_confirmed_at = now
                order.supplier_payment_released_at = now
                order.save(update_fields=[
                    "status",
                    "delivered_at",
                    "delivered_confirmed_at",
                    "supplier_payment_released_at",
                    "updated_at",
                ])
        except Exception as e:
            messages.error(request, f"خطا در ثبت تأیید: {str(e)}")
            return redirect("market:order_detail", pk=order.pk)

        messages.success(
            request,
            "✅ تأیید دریافت ثبت شد. از خرید شما سپاسگزاریم.",
        )
        return redirect("market:order_detail", pk=order.pk)


class SellerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "market/seller/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not hasattr(request.user, 'supplier_profile'):
            messages.error(request, "شما دسترسی به پنل فروشندگی ندارید.")
            return redirect('market:landing')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        supplier = self.request.user.supplier_profile

        # ---------- محصولات ----------
        products_qs = Product.objects.filter(supplier=supplier)
        ctx['total_products'] = products_qs.count()
        ctx['active_products'] = products_qs.filter(status=Product.Status.ACTIVE).count()
        ctx['draft_products'] = products_qs.filter(status=Product.Status.DRAFT).count()
        ctx['inactive_products'] = products_qs.filter(status=Product.Status.INACTIVE).count()

        # ---------- سفارشات مرتبط با این فروشنده ----------
        items_qs = OrderItem.objects.filter(supplier=supplier)
        order_ids = items_qs.values_list('order_id', flat=True).distinct()

        relevant_orders = Order.objects.filter(
            id__in=order_ids,
            status__in=[
                Order.Status.PAID,
                Order.Status.PROCESSING,
                Order.Status.SHIPPED,
                Order.Status.DELIVERED,
                Order.Status.RETURNED,
            ]
        )

        ctx['total_orders'] = relevant_orders.count()
        ctx['pending_shipment_orders'] = relevant_orders.filter(
            status__in=[Order.Status.PAID, Order.Status.PROCESSING]
        ).count()
        ctx['shipped_orders'] = relevant_orders.filter(status=Order.Status.SHIPPED).count()
        ctx['delivered_orders'] = relevant_orders.filter(status=Order.Status.DELIVERED).count()

        # ---------- درآمد ----------
        # درآمد تایید شده (تحویل داده شده)
        ctx['delivered_revenue'] = items_qs.filter(
            order__status=Order.Status.DELIVERED
        ).aggregate(total=Sum('subtotal'))['total'] or 0

        # درآمد در انتظار (پرداخت شده اما هنوز تحویل نشده)
        ctx['pending_revenue'] = items_qs.filter(
            order__status__in=[
                Order.Status.PAID,
                Order.Status.PROCESSING,
                Order.Status.SHIPPED,
            ]
        ).aggregate(total=Sum('subtotal'))['total'] or 0

        # ---------- کیف پول ----------
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        ctx['wallet_balance'] = wallet.balance

        # ---------- نمودار درآمد ۳۰ روز اخیر ----------
        now = timezone.now()
        last_30_days = now - timedelta(days=30)

        daily_revenue = items_qs.filter(
            order__status=Order.Status.DELIVERED,
            order__delivered_confirmed_at__gte=last_30_days,
        ).annotate(
            day=TruncDate('order__delivered_confirmed_at')
        ).values('day').annotate(
            total=Sum('subtotal')
        ).order_by('day')

        daily_revenue_labels = []
        daily_revenue_data = []
        for item in daily_revenue:
            if item['day']:
                try:
                    jalali = jdatetime.date.fromgregorian(date=item['day'])
                    daily_revenue_labels.append(jalali.strftime('%m/%d'))
                    daily_revenue_data.append(float(item['total']) if item['total'] else 0)
                except Exception:
                    pass

        ctx['daily_revenue_labels_json'] = json.dumps(daily_revenue_labels, ensure_ascii=False)
        ctx['daily_revenue_data_json'] = json.dumps(daily_revenue_data, ensure_ascii=False)

        # ---------- سفارشات اخیر (با annotation مخصوص فروشنده) ----------
        recent_orders = (
            relevant_orders
            .select_related('order_address')
            .order_by('-created_at')[:10]
        )
        for order in recent_orders:
            oi = order.items.filter(supplier=supplier)
            order.supplier_items_count = oi.count()
            order.supplier_total = oi.aggregate(t=Sum('subtotal'))['t'] or 0

        ctx['recent_orders'] = recent_orders

        # ---------- تراکنش‌های اخیر ----------
        ctx['recent_transactions'] = Transaction.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:10]

        # ---------- برترین محصولات ----------
        top_products = products_qs.annotate(
            sold_qty=Sum(
                'orderitem__quantity',
                filter=Q(orderitem__order__status=Order.Status.DELIVERED),
            ),
            revenue=Sum(
                'orderitem__subtotal',
                filter=Q(orderitem__order__status=Order.Status.DELIVERED),
            ),
        ).filter(sold_qty__gt=0).order_by('-sold_qty')[:5]
        ctx['top_products'] = top_products

        # ---------- تاریخ شمسی ----------
        today = jdatetime.date.today()
        weekdays = {
            'Saturday': 'شنبه', 'Sunday': 'یکشنبه', 'Monday': 'دوشنبه',
            'Tuesday': 'سه‌شنبه', 'Wednesday': 'چهارشنبه',
            'Thursday': 'پنجشنبه', 'Friday': 'جمعه',
        }
        months = {
            'Farvardin': 'فروردین', 'Ordibehesht': 'اردیبهشت', 'Khordad': 'خرداد',
            'Tir': 'تیر', 'Mordad': 'مرداد', 'Shahrivar': 'شهریور',
            'Mehr': 'مهر', 'Aban': 'آبان', 'Azar': 'آذر',
            'Dey': 'دی', 'Bahman': 'بهمن', 'Esfand': 'اسفند',
        }
        persian_date = today.strftime("%A %d %B %Y")
        for en, fa in weekdays.items():
            persian_date = persian_date.replace(en, fa)
        for en, fa in months.items():
            persian_date = persian_date.replace(en, fa)
        ctx['persian_date'] = persian_date

        ctx['supplier'] = supplier
        return ctx


# ============================================================
# Seller Panel — لیست محصولات
# ============================================================
class SellerProductListView(LoginRequiredMixin, ListView):
    template_name = "market/seller/products/list.html"
    context_object_name = "products"
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not hasattr(request.user, 'supplier_profile'):
            messages.error(request, "شما دسترسی به پنل فروشندگی ندارید.")
            return redirect('market:landing')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        supplier = self.request.user.supplier_profile

        qs = (
            Product.objects
            .filter(supplier=supplier)
            .select_related('category', 'supplier')
            .prefetch_related('images')
            .annotate(
                sold_qty=Sum(
                    'orderitem__quantity',
                    filter=Q(orderitem__order__status=Order.Status.DELIVERED),
                ),
                revenue=Sum(
                    'orderitem__subtotal',
                    filter=Q(orderitem__order__status=Order.Status.DELIVERED),
                ),
            )
        )

        # ---- Filter: status ----
        status = self.request.GET.get('status', '')
        if status and status in dict(Product.Status.choices):
            qs = qs.filter(status=status)

        # ---- Filter: category ----
        category_id = self.request.GET.get('category', '')
        if category_id and category_id.isdigit():
            qs = qs.filter(category_id=int(category_id))

        # ---- Search ----
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(short_description__icontains=search) |
                Q(slug__icontains=search)
            )

        # ---- Sort ----
        sort = self.request.GET.get('sort', 'newest')
        sort_map = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'price_high': '-base_price',
            'price_low': 'base_price',
            'best_selling': '-sold_qty',
            'name': 'title',
        }
        qs = qs.order_by(sort_map.get(sort, '-created_at'))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        supplier = self.request.user.supplier_profile

        # ---- View mode (table/card) ----
        view_mode = self.request.GET.get('view', 'card')
        if view_mode not in ('table', 'card'):
            view_mode = 'card'
        ctx['view_mode'] = view_mode

        # ---- Stats ----
        base_qs = Product.objects.filter(supplier=supplier)
        ctx['counts'] = {
            'total': base_qs.count(),
            'active': base_qs.filter(status=Product.Status.ACTIVE).count(),
            'draft': base_qs.filter(status=Product.Status.DRAFT).count(),
            'scheduled': base_qs.filter(status=Product.Status.SCHEDULED).count(),
            'inactive': base_qs.filter(status=Product.Status.INACTIVE).count(),
            'sold_out': base_qs.filter(status=Product.Status.SOLD_OUT).count(),
        }

        # ---- Categories for filter ----
        ctx['categories'] = Category.objects.filter(is_active=True).order_by('name')

        # ---- Status choices ----
        ctx['status_choices'] = Product.Status.choices

        # ---- Current filters ----
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_category'] = self.request.GET.get('category', '')
        ctx['current_search'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'newest')

        # ---- Has active filters ----
        ctx['has_active_filters'] = bool(
            ctx['current_status'] or ctx['current_category'] or ctx['current_search']
        )

        # ---- Query string (برای حفظ فیلترها) ----
        params = self.request.GET.copy()
        params.pop('page', None)
        params.pop('view', None)
        ctx['query_params'] = params.urlencode()

        ctx['supplier'] = supplier
        return ctx


# ============================================================
# Seller Panel — ایجاد محصول
# ============================================================
class SellerProductCreateView(LoginRequiredMixin, View):
    template_name = "market/seller/products/form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not hasattr(request.user, 'supplier_profile'):
            messages.error(request, "شما دسترسی به پنل فروشندگی ندارید.")
            return redirect('market:landing')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = ProductForm(supplier=request.user.supplier_profile)
        ctx = self._build_context(request, form, is_edit=False)
        return render(request, self.template_name, ctx)

    def post(self, request):
        form = ProductForm(request.POST, request.FILES, supplier=request.user.supplier_profile)

        if form.is_valid():
            try:
                with transaction.atomic():
                    product = form.save(commit=False)
                    product.supplier = request.user.supplier_profile
                    product.status = Product.Status.DRAFT
                    product.save()
                    form.save_m2m()  # shipping_methods

                    # --- ذخیره‌ی تصاویر ---
                    self._handle_images(request, product, is_edit=False)

                    # --- ذخیره‌ی ویژگی‌ها ---
                    self._handle_features(request, product)

                messages.success(request, "✅ محصول با موفقیت ثبت شد و در انتظار تایید است.")
                return redirect('market:seller_product_list')
            except Exception as e:
                messages.error(request, f"خطا در ذخیره محصول: {str(e)}")
        else:
            messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")

        ctx = self._build_context(request, form, is_edit=False)
        return render(request, self.template_name, ctx)

    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------
    def _build_context(self, request, form, is_edit, product=None):
        return {
            'form': form,
            'is_edit': is_edit,
            'product': product,
            'categories': Category.objects.filter(is_active=True).order_by('order', 'name'),
            'features': Feature.objects.all().order_by('name'),
            'shipping_methods': ShippingMethod.objects.filter(is_active=True).order_by('order', 'name'),
        }

    @staticmethod
    def _handle_images(request, product, is_edit=False):
        """مدیریت آپلود تصاویر"""
        images = request.FILES.getlist('images')
        main_index = request.POST.get('main_image_index', '0')
        try:
            main_index = int(main_index)
        except (ValueError, TypeError):
            main_index = 0

        if not images:
            return

        # محدودیت تعداد
        if len(images) > 10:
            images = images[:10]

        # اگه main_index خارج از محدوده بود، صفر کن
        if main_index < 0 or main_index >= len(images):
            main_index = 0

        for i, img in enumerate(images):
            if i == main_index:
                product.main_image = img
                product.save(update_fields=['main_image'])
            else:
                # چک نکنیم که تکراریه یا نه
                ProductImage.objects.create(
                    product=product,
                    image=img,
                    order=i if i < main_index else i - 1,
                )

    @staticmethod
    def _handle_features(request, product):
        """ذخیره‌ی ویژگی‌ها از JSON"""
        import json

        raw = request.POST.get('features_json', '[]')
        try:
            features_data = json.loads(raw)
        except (ValueError, TypeError):
            features_data = []

        if not isinstance(features_data, list):
            return

        # پاک کردن قبلی‌ها (برای edit)
        product.features.all().delete()

        for item in features_data:
            if not isinstance(item, dict):
                continue
            feature_id = item.get('feature_id')
            value = (item.get('value') or '').strip()
            if not feature_id or not value:
                continue
            try:
                feature = Feature.objects.get(pk=feature_id)
                ProductFeature.objects.create(
                    product=product,
                    feature=feature,
                    value=value,
                )
            except Feature.DoesNotExist:
                continue


# ============================================================
# Seller Panel — ویرایش محصول
# ============================================================
class SellerProductUpdateView(LoginRequiredMixin, View):
    template_name = "market/seller/products/form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not hasattr(request.user, 'supplier_profile'):
            messages.error(request, "شما دسترسی به پنل فروشندگی ندارید.")
            return redirect('market:landing')
        return super().dispatch(request, *args, **kwargs)

    def get_product(self, request, pk):
        return get_object_or_404(
            Product,
            pk=pk,
            supplier=request.user.supplier_profile,
        )

    def get(self, request, pk):
        product = self.get_product(request, pk)
        form = ProductForm(instance=product, supplier=request.user.supplier_profile)

        ctx = {
            'form': form,
            'is_edit': True,
            'product': product,
            'categories': Category.objects.filter(is_active=True).order_by('order', 'name'),
            'features': Feature.objects.all().order_by('name'),
            'shipping_methods': ShippingMethod.objects.filter(is_active=True).order_by('order', 'name'),
            'existing_images': product.images.all().order_by('order'),
            'existing_features_json': self._features_to_json(product),
        }
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        product = self.get_product(request, pk)
        form = ProductForm(
            request.POST, request.FILES,
            instance=product,
            supplier=request.user.supplier_profile,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    product = form.save(commit=False)
                    product.supplier = request.user.supplier_profile
                    # status رو تغییر نده — اگه ACTIVE بود بمونه
                    product.save()
                    form.save_m2m()

                    SellerProductCreateView._handle_images(request, product, is_edit=True)
                    SellerProductCreateView._handle_features(request, product)

                messages.success(request, "✅ محصول با موفقیت ویرایش شد.")
                return redirect('market:seller_product_list')
            except Exception as e:
                messages.error(request, f"خطا در ویرایش محصول: {str(e)}")
        else:
            messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")

        ctx = {
            'form': form,
            'is_edit': True,
            'product': product,
            'categories': Category.objects.filter(is_active=True).order_by('order', 'name'),
            'features': Feature.objects.all().order_by('name'),
            'shipping_methods': ShippingMethod.objects.filter(is_active=True).order_by('order', 'name'),
            'existing_images': product.images.all().order_by('order'),
            'existing_features_json': self._features_to_json(product),
        }
        return render(request, self.template_name, ctx)

    @staticmethod
    def _features_to_json(product):
        import json
        data = [
            {'feature_id': pf.feature_id, 'value': pf.value}
            for pf in product.features.all()
        ]
        return json.dumps(data, ensure_ascii=False)


# ============================================================
# Seller Panel — حذف محصول (AJAX)
# ============================================================
class SellerProductDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        supplier = getattr(request.user, 'supplier_profile', None)
        if not supplier:
            return JsonResponse({'success': False, 'message': 'دسترسی ندارید.'}, status=403)

        product = get_object_or_404(Product, pk=pk, supplier=supplier)

        # چک سفارش‌های مرتبط
        has_orders = OrderItem.objects.filter(product=product).exists()

        if has_orders:
            product.status = Product.Status.INACTIVE
            product.save(update_fields=['status'])
            return JsonResponse({
                'success': True,
                'message': 'این محصول سفارش دارد؛ بنابراین غیرفعال شد اما حذف نشد.',
            })

        product.delete()
        return JsonResponse({
            'success': True,
            'message': 'محصول با موفقیت حذف شد.',
        })


# ============================================================
# Seller Panel — حذف یک تصویر از گالری (AJAX)
# ============================================================
class SellerProductImageDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        supplier = getattr(request.user, 'supplier_profile', None)
        if not supplier:
            return JsonResponse({'success': False, 'message': 'دسترسی ندارید.'}, status=403)

        image = get_object_or_404(
            ProductImage,
            pk=pk,
            product__supplier=supplier,
        )
        image.delete()
        return JsonResponse({'success': True, 'message': 'تصویر حذف شد.'})


# ============================================================
# Seller Panel — انتخاب تصویر اصلی (AJAX)
# ============================================================
class SellerSetMainImageAPIView(LoginRequiredMixin, View):
    """
    این endpoint از دو حالت پشتیبانی می‌کنه:
    1. image_id داده می‌شه → اون ProductImage رو به main_image منتقل می‌کنه
    2. هیچ image_id نده → کاربر می‌خواد main_image فعلی رو حذف کنه
    """
    def post(self, request, pk):
        supplier = getattr(request.user, 'supplier_profile', None)
        if not supplier:
            return JsonResponse({'success': False, 'message': 'دسترسی ندارید.'}, status=403)

        product = get_object_or_404(Product, pk=pk, supplier=supplier)
        image_id = request.POST.get('image_id')

        if not image_id:
            # فقط main رو حذف کن
            if product.main_image:
                product.main_image.delete(save=False)
                product.main_image = None
                product.save(update_fields=['main_image'])
            return JsonResponse({'success': True, 'message': 'تصویر اصلی حذف شد.'})

        img = get_object_or_404(ProductImage, pk=image_id, product=product)

        # main قدیمی رو به گالری برگردون (اگه بود)
        if product.main_image:
            old_main = ProductImage.objects.create(
                product=product,
                image=product.main_image,
                order=99,
            )

        # image جدید رو main کن
        product.main_image = img.image
        product.save(update_fields=['main_image'])

        # و از گالری حذفش کن
        img.delete()

        return JsonResponse({
            'success': True,
            'message': 'تصویر اصلی تغییر کرد.',
        })


# ============================================================
# API — ترجمه‌ی اسلاگ
# ============================================================
class TranslateSlugAPIView(LoginRequiredMixin, View):
    def get(self, request):
        title = (request.GET.get('title') or '').strip()

        if not title:
            return JsonResponse({'slug': ''})

        slug = generate_english_slug(title, fallback_prefix='product')
        return JsonResponse({'slug': slug})