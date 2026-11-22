"""ویوهای فروشگاه بسته‌های توکن، دریافت هدیه ۳۵۰ توکنی، تاریخچه تراکنش توکن و پرداخت."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Platform
from payment.models import Invoice, Wallet
from payment.services.forward_subscription_payment import (
    pay_forward_subscription_wallet,
    start_forward_subscription_gateway,
)
from payment.services.zarinpal_flow import prepare_gateway_bridge

from .forms import ForwardTokenPackageCheckoutForm
from .models import (
    ForwardSubscriptionOrder,
    ForwardSubscriptionPlan,
    ForwardTokenTransaction,
)
from .services import (
    account_for,
    cancel_pending_token_order,
    claim_free_gift_tokens,
    create_token_order_with_invoice,
    get_pricing_config,
)


def _get_forward_platforms_map() -> dict:
    """واکشی دیکشنری هر ۴ پلتفرم وین‌فوروارد از دیتابیس."""
    qs = Platform.objects.filter(slug__in=["bale", "eitaa", "rubika", "telegram", "soroush"])
    return {p.slug: p for p in qs}


@login_required
def plans_view(request):
    """صفحه فروشگاه بسته‌های توکن، دکمه دریافت ۳۵۰ توکن رایگان، جدول شفاف نرخ‌ها و تاریخچه تراکنش‌ها."""
    nav_platforms = _get_forward_platforms_map()
    account = account_for(request.user)
    pricing = get_pricing_config()

    gift_plan = ForwardSubscriptionPlan.objects.filter(is_active=True, is_trial=True).first()
    paid_packages = list(
        ForwardSubscriptionPlan.objects.filter(is_active=True, is_trial=False, tokens_amount__gt=0)
        .order_by("position", "tokens_amount")
    )
    for pkg in paid_packages:
        pkg.per_token_price = int(round(pkg.price_per_platform / max(1, pkg.tokens_amount)))

    tx_qs = ForwardTokenTransaction.objects.filter(user=request.user).order_by("-created_at", "-pk")
    paginator = Paginator(tx_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    recent_orders = ForwardSubscriptionOrder.objects.filter(user=request.user).select_related("plan")[:8]

    return render(
        request,
        "product/forward/subscriptions/plans.html",
        {
            "account": account,
            "pricing": pricing,
            "gift_plan": gift_plan,
            "paid_packages": paid_packages,
            "transactions": page_obj.object_list,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "recent_orders": recent_orders,
            "nav_platforms": nav_platforms,
        },
    )


@login_required
@require_POST
def create_order_view(request):
    """دریافت هدیه ۳۵۰ توکنی یا ثبت سفارش خرید بسته توکن و هدایت به صفحه پرداخت."""
    form = ForwardTokenPackageCheckoutForm(request.POST)
    if not form.is_valid():
        messages.error(request, "بسته انتخاب‌شده معتبر نیست.")
        return redirect("forward_subscriptions:plans")

    plan = form.cleaned_data["plan_id"]
    try:
        if plan.is_trial:
            gift_amount = claim_free_gift_tokens(request.user, plan=plan)
            messages.success(
                request,
                f"🎁 {gift_amount:,} توکن رایگان با موفقیت به کیف توکن شما اضافه شد! (بدون تاریخ انقضا)",
            )
            return redirect("broadcast:dashboard")

        order, _invoice = create_token_order_with_invoice(request.user, plan)
        return redirect("forward_subscriptions:order_detail", order_id=order.pk)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
        return redirect("forward_subscriptions:plans")


@login_required
def order_detail_view(request, order_id):
    """نمایش فاکتور خرید بسته توکن و پرداخت با کیف پول یا درگاه زرین‌پال."""
    nav_platforms = _get_forward_platforms_map()
    order = get_object_or_404(
        ForwardSubscriptionOrder.objects.select_related("plan"),
        pk=order_id,
        user=request.user,
    )
    invoice = Invoice.objects.filter(forward_subscription_order=order).first()
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    account = account_for(request.user)
    pending_gateway = (
        invoice.payments.filter(status="pending", authority__isnull=False)
        .exclude(authority="")
        .order_by("-pk")
        .first()
        if invoice
        else None
    )

    latest_payment = (
        invoice.payments.order_by("-pk").first()
        if invoice
        else None
    )
    tokens_qty = int(order.tokens_amount or (order.plan.tokens_amount if order.plan else 0))
    per_token_price = int(round(order.subtotal_amount / max(1, tokens_qty))) if tokens_qty else 0
    new_token_balance = int(account.token_balance) + (tokens_qty if order.status == ForwardSubscriptionOrder.Status.PENDING else 0)
    sandbox_mode = bool(
        getattr(settings, "IRANIAN_PAYMENT", {})
        .get("gateways", {})
        .get("zarinpal", {})
        .get("sandbox", False)
    )

    return render(
        request,
        "product/forward/subscriptions/order_detail.html",
        {
            "order": order,
            "invoice": invoice,
            "wallet": wallet,
            "account": account,
            "can_pay_wallet": bool(invoice and wallet.balance >= invoice.payable_amount),
            "pending_gateway": pending_gateway,
            "latest_payment": latest_payment,
            "per_token_price": per_token_price,
            "new_token_balance": new_token_balance,
            "sandbox": sandbox_mode,
            "nav_platforms": nav_platforms,
        },
    )


@login_required
@require_POST
def pay_wallet_view(request, order_id):
    """پرداخت آنی بسته توکن از کیف پول و شارژ فوری توکن‌ها."""
    order = get_object_or_404(ForwardSubscriptionOrder, pk=order_id, user=request.user)
    try:
        pay_forward_subscription_wallet(order, request.user)
        messages.success(
            request,
            f"✅ {order.tokens_amount:,} توکن با موفقیت به کیف توکن وین‌فوروارد شما اضافه شد!",
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
    return redirect("forward_subscriptions:order_detail", order_id=order.pk)


@login_required
@require_POST
def pay_gateway_view(request, order_id):
    """شروع پرداخت آنلاین بسته توکن از طریق درگاه زرین‌پال."""
    order = get_object_or_404(ForwardSubscriptionOrder, pk=order_id, user=request.user)
    try:
        gateway_url = start_forward_subscription_gateway(order, request.user)
        redirect_url = prepare_gateway_bridge(request, gateway_url)
        return redirect(redirect_url)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
    except Exception:
        messages.error(request, "در حال حاضر اتصال به درگاه زرین‌پال برقرار نشد. لطفاً بعداً تلاش کنید.")
    return redirect("forward_subscriptions:order_detail", order_id=order.pk)


@login_required
@require_POST
def cancel_order_view(request, order_id):
    """لغو سفارش پرداخت‌نشده خرید بسته توکن و بازگشت به فروشگاه توکن."""
    order = get_object_or_404(ForwardSubscriptionOrder, pk=order_id, user=request.user)
    try:
        cancel_pending_token_order(order, request.user)
        messages.info(request, f"سفارش #{order.pk} با موفقیت لغو شد.")
        return redirect("forward_subscriptions:plans")
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
        return redirect("forward_subscriptions:order_detail", order_id=order.pk)
