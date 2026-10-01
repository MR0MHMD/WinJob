"""صفحات انتخاب پلن، خرید، اشتراک و سوابق با بیس فعلی سایت."""

from math import ceil
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from payment.services.subscription_payment import (
    pay_subscription_wallet,
    start_subscription_gateway,
)
from payment.services.zarinpal_flow import (
    prepare_gateway_bridge,
    _zarinpal_sandbox_enabled,
)
from ..models import (
    SubscriptionPlan,
    SubscriptionOffer,
    SubscriptionOrder,
    InstagramConnection,
)
from .forms import SubscriptionOrderForm, SubscriptionPaymentForm
from .services import (
    account_for,
    current_period,
    remaining_periods,
    activate_trial,
    create_order,
    _build_quote,
    as_datetime,
)
from .access import register_connection


def _context(user):
    """وضعیت اشتراک را برای صفحات خصوصی آماده می‌کند."""
    account = account_for(user)
    return {
        "noindex": True,
        "section": "subscription",
        "account": account,
        "active": current_period(user),
        "sandbox": _zarinpal_sandbox_enabled(),
    }


@login_required(login_url="accounts:login")
def plans(request):
    """پلن رایگان و گزینه‌های قیمت را با شرایط استفاده نمایش می‌دهد."""
    context = _context(request.user)
    context["plans"] = SubscriptionPlan.objects.filter(is_active=True).prefetch_related(
        "offers"
    )
    context["periods"] = remaining_periods(context["account"])
    context["paid_reference"] = next(
        (period for period in context["periods"] if period.kind != "trial"), None
    )
    return render(request, "windirect/subscriptions/plans.html", context)


@login_required(login_url="accounts:login")
@require_POST
def trial(request, pk):
    """دورهٔ رایگان تنها با اقدام صریح مالک فعال می‌شود."""
    offer = get_object_or_404(SubscriptionOffer, pk=pk)
    try:
        activate_trial(request.user, offer)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("windirect:plans")
    messages.success(request, "دورهٔ رایگان ۳۰ روزهٔ وین دایرکت فعال شد.")
    return redirect("windirect:subscription")


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def subscribe(request, pk):
    """پیش‌نمایش خرید و ثبت سفارش پیش از انتخاب روش پرداخت."""
    offer = get_object_or_404(
        SubscriptionOffer.objects.select_related("plan"),
        pk=pk,
        is_active=True,
        plan__is_active=True,
        plan__is_trial=False,
    )
    context = _context(request.user)
    form = SubscriptionOrderForm(
        request.POST if request.method == "POST" else None,
        initial={
            "kind": "upgrade" if request.GET.get("kind") == "upgrade" else "purchase"
        },
    )
    quote = None
    if request.method == "POST" and form.is_valid():
        try:
            order = create_order(
                request.user,
                offer,
                kind=form.cleaned_data["kind"],
                referral_code=form.cleaned_data["referral_code"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect("windirect:subscription_checkout", pk=order.pk)
    else:
        try:
            quote, _ = _build_quote(context["account"], offer, form.initial["kind"])
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("windirect:plans")
    context.update(form=form, offer=offer, quote=quote)
    return render(request, "windirect/subscriptions/subscribe.html", context)


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def checkout(request, pk):
    """فاکتور قطعی و مبلغ نهایی را نشان می‌دهد و پرداخت را شروع می‌کند."""
    order = get_object_or_404(
        SubscriptionOrder.objects.select_related("offer__plan"),
        pk=pk,
        user=request.user,
    )
    form = SubscriptionPaymentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["method"] == "wallet":
                pay_subscription_wallet(order, request.user)
                messages.success(request, "پرداخت و فعال‌سازی اشتراک انجام شد.")
                return redirect("windirect:subscription_order", pk=order.pk)
            url = start_subscription_gateway(order, request.user)
            return redirect(prepare_gateway_bridge(request, url))
        except ValidationError as error:
            form.add_error(None, error)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "خطای شروع پرداخت اشتراک %s", order.pk
            )
            form.add_error(
                None,
                "شروع پرداخت درگاه ممکن نشد. بعداً دوباره تلاش کنید؛ اشتراک هنوز فعال نشده است.",
            )
    context = _context(request.user)
    context.update(
        order=order,
        invoice=order.invoice,
        form=form,
        expired=as_datetime(order.expires_at) <= timezone.now(),
    )
    return render(request, "windirect/subscriptions/checkout.html", context)


@login_required(login_url="accounts:login")
def subscription(request):
    """دوره‌های فعال و آتی، روزهای ذخیره‌شده و معرفی‌ها را نمایش می‌دهد."""
    context = _context(request.user)
    context["periods"] = remaining_periods(context["account"])
    context["total_days_remaining"] = (
        max(
            0,
            ceil(
                (
                    as_datetime(context["periods"][-1].ends_at) - timezone.now()
                ).total_seconds()
                / 86400
            ),
        )
        if context["periods"]
        else 0
    )
    context["gifts"] = (
        context["account"]
        .gifts.select_related("redemption", "period")
        .order_by("-pk")[:20]
    )
    context["referral"] = getattr(request.user, "windirect_referral_code", None)
    context["orders"] = Paginator(
        SubscriptionOrder.objects.filter(user=request.user).select_related(
            "offer__plan"
        ),
        15,
    ).get_page(request.GET.get("page"))
    return render(request, "windirect/subscriptions/current.html", context)


@login_required(login_url="accounts:login")
def order_detail(request, pk):
    """نتیجه و سوابق تلاش پرداخت سفارش متعلق به کاربر را نمایش می‌دهد."""
    order = get_object_or_404(SubscriptionOrder, pk=pk, user=request.user)
    context = _context(request.user)
    context.update(
        order=order,
        invoice=order.invoice,
        attempts=order.attempts.select_related("payment"),
    )
    return render(request, "windirect/subscriptions/order.html", context)


@login_required(login_url="accounts:login")
@require_POST
def cancel_order(request, pk):
    """سفارش نپرداخته را می‌بندد؛ پرداخت دیرهنگام درگاه به کیف پول اعتبار می‌شود."""
    with transaction.atomic():
        order = get_object_or_404(
            SubscriptionOrder.objects.select_for_update(), pk=pk, user=request.user
        )
        if order.status == "pending":
            order.status = "cancelled"
            order.settled_at = timezone.now()
            order.save(update_fields=["status", "settled_at"])
    return redirect("windirect:subscription_order", pk=pk)


@login_required(login_url="accounts:login")
@require_POST
def connection_toggle(request, pk):
    """قطع پیج داده‌ها را حذف نمی‌کند؛ فعال‌سازی نمونه سقف اشتراک را رعایت می‌کند."""
    with transaction.atomic():
        connection = get_object_or_404(
            InstagramConnection.objects.select_for_update(), pk=pk, owner=request.user
        )
        if connection.status == "disconnected":
            if connection.instagram_user_id:
                messages.error(
                    request, "اتصال مجدد رسمی با ورود متا در مرحلهٔ اتصال انجام می‌شود."
                )
            else:
                try:
                    register_connection(request.user, connection)
                except ValidationError as error:
                    messages.error(request, error.messages[0])
        else:
            connection.status = "disconnected"
            connection.save(update_fields=["status", "updated_at"])
    return redirect("windirect:connections")
