"""ویوهای پنل خرید و مدیریت اشتراک وین فوروارد."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from payment.models import Invoice, Wallet
from payment.services.forward_subscription_payment import (
    pay_forward_subscription_wallet,
    start_forward_subscription_gateway,
)
from payment.services.zarinpal_flow import prepare_gateway_bridge

from .access import get_user_platform_access_map
from .forms import ForwardSubscriptionCheckoutForm
from .models import (
    FORWARD_PLATFORMS,
    ForwardSubscriptionOrder,
    ForwardSubscriptionPlan,
)
from .services import (
    account_for,
    activate_trial_subscription,
    create_forward_order_with_invoice,
)


@login_required
def plans_view(request):
    """صفحه نمایش پلن‌های اشتراک وین فوروارد، وضعیت اشتراک فعلی و فرم انتخاب پلتفرم‌ها."""
    account = account_for(request.user)
    access_map = get_user_platform_access_map(request.user)
    plans = ForwardSubscriptionPlan.objects.filter(is_active=True).order_by("position", "duration_days")

    bale_access = access_map.get("bale")
    has_active_paid_bale = bool(
        bale_access and bale_access.is_valid and bale_access.plan and not bale_access.plan.is_trial
    )
    missing_platforms = [
        (slug, label) for slug, label in FORWARD_PLATFORMS if slug not in access_map
    ]

    recent_orders = ForwardSubscriptionOrder.objects.filter(user=request.user).select_related("plan")[:10]

    return render(
        request,
        "product/forward/subscriptions/plans.html",
        {
            "account": account,
            "plans": plans,
            "access_map": access_map,
            "all_platforms": FORWARD_PLATFORMS,
            "has_active_paid_bale": has_active_paid_bale,
            "bale_access": bale_access,
            "missing_platforms": missing_platforms,
            "recent_orders": recent_orders,
        },
    )


@login_required
@require_POST
def create_order_view(request):
    """ثبت سفارش اشتراک (یا فعال‌سازی فوری دوره رایگان ۷ روزه) و هدایت به صفحه پرداخت."""
    form = ForwardSubscriptionCheckoutForm(request.POST)
    if not form.is_valid():
        messages.error(request, "اطلاعات انتخاب‌شده برای اشتراک معتبر نیست.")
        return redirect("forward_subscriptions:plans")

    plan = form.cleaned_data["plan_id"]
    order_kind = form.cleaned_data.get("order_kind") or ForwardSubscriptionOrder.OrderKind.NEW
    selected_platforms = form.cleaned_data.get("platforms") or []

    try:
        if plan.is_trial:
            activate_trial_subscription(request.user, plan)
            messages.success(request, "✅ اشتراک رایگان ۷ روزه برای تمام پلتفرم‌ها با موفقیت فعال شد.")
            return redirect("forward_subscriptions:plans")

        order, _invoice = create_forward_order_with_invoice(
            user=request.user,
            plan=plan,
            selected_platforms=selected_platforms,
            order_kind=order_kind,
        )
        return redirect("forward_subscriptions:order_detail", order_id=order.pk)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
        return redirect("forward_subscriptions:plans")


@login_required
def order_detail_view(request, order_id):
    """نمایش جزئیات سفارش، فاکتور و گزینه‌های پرداخت با کیف پول یا درگاه زرین‌پال."""
    order = get_object_or_404(
        ForwardSubscriptionOrder.objects.select_related("plan"),
        pk=order_id,
        user=request.user,
    )
    invoice = Invoice.objects.filter(forward_subscription_order=order).first()
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    pending_gateway = (
        invoice.payments.filter(status="pending", authority__isnull=False).exclude(authority="").order_by("-pk").first()
        if invoice
        else None
    )

    return render(
        request,
        "product/forward/subscriptions/order_detail.html",
        {
            "order": order,
            "invoice": invoice,
            "wallet": wallet,
            "can_pay_wallet": bool(invoice and wallet.balance >= invoice.payable_amount),
            "pending_gateway": pending_gateway,
        },
    )


@login_required
@require_POST
def pay_wallet_view(request, order_id):
    """پرداخت آنی سفارش اشتراک وین فوروارد از موجودی کیف پول کاربر."""
    order = get_object_or_404(ForwardSubscriptionOrder, pk=order_id, user=request.user)
    try:
        pay_forward_subscription_wallet(order, request.user)
        messages.success(request, "✅ اشتراک وین فوروارد شما با موفقیت از کیف پول پرداخت و فعال شد.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
    return redirect("forward_subscriptions:order_detail", order_id=order.pk)


@login_required
@require_POST
def pay_gateway_view(request, order_id):
    """شروع پرداخت آنلاین سفارش اشتراک وین فوروارد از طریق درگاه زرین‌پال."""
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
