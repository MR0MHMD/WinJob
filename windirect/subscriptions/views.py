"""صفحات انتخاب پلن، خرید، اشتراک و سوابق با بیس فعلی سایت."""

import json
import logging
from math import ceil

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
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
from payment.services.create_invoice import create_subscription_invoice
from windirect.subscriptions.models import (
    SubscriptionPlan,
    SubscriptionOffer,
    SubscriptionOrder,
    WindirectCoupon,
)
from .forms import SubscriptionPaymentForm
from .services import (
    account_for,
    current_period,
    remaining_periods,
    activate_trial,
    create_order,
    _build_quote,
    _as_datetime,
)

logger = logging.getLogger(__name__)


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

    periods = remaining_periods(context["account"])

    all_plans = (
        SubscriptionPlan.objects.filter(is_active=True)
        .prefetch_related("offers")
        .order_by("level", "position", "pk")
    )

    trial_plan = all_plans.filter(is_trial=True).first()
    paid_plans = list(all_plans.filter(is_trial=False))

    TAB_CONFIG = [
        {"key": "monthly", "label": "ماهانه", "days": 30, "icon": "calendar-month"},
        {"key": "quarter", "label": "سه‌ماهه", "days": 90, "icon": "calendar-range"},
        {"key": "yearly", "label": "سالانه", "days": 365, "icon": "calendar-heart"},
    ]

    tabs = []
    for tab in TAB_CONFIG:
        plans_in_tab = []
        for plan in paid_plans:
            offer = next(
                (
                    o for o in plan.offers.all()
                    if o.is_active and o.duration_days == tab["days"]
                ),
                None,
            )
            if offer:
                plans_in_tab.append({"plan": plan, "offer": offer})

        if plans_in_tab:
            tabs.append({
                "key": tab["key"],
                "label": tab["label"],
                "days": tab["days"],
                "icon": tab["icon"],
                "plans": plans_in_tab,
            })

    context.update({
        "trial_plan": trial_plan,
        "trial_offer": (
            next(
                (o for o in trial_plan.offers.all() if o.is_active and o.duration_days == 30),
                None,
            )
            if trial_plan else None
        ),
        "tabs": tabs,
        "periods": periods,
        "paid_reference": next(
            (period for period in periods if period.kind != "trial"), None
        ),
    })
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
def checkout(request, offer_pk=None, order_pk=None):
    """
    صفحهٔ تأیید و پرداخت.

    - اگه `offer_pk` بیاد (از صفحهٔ پلن‌ها):
        → سفارش و فاکتور ساخته/آپدیت می‌شود
        → redirect به همین view با `order_pk`
    - اگه `order_pk` بیاد (پرداخت):
        → فاکتور نمایش داده می‌شود
        → روی POST، پرداخت شروع می‌شود
    """
    # ==================== حالت ۱: از صفحهٔ پلن‌ها ====================
    if offer_pk is not None:
        offer = get_object_or_404(
            SubscriptionOffer.objects.select_related("plan"),
            pk=offer_pk,
            is_active=True,
            plan__is_active=True,
            plan__is_trial=False,
        )
        kind = request.GET.get("kind", "purchase")
        if kind not in ("purchase", "upgrade"):
            kind = "purchase"
        try:
            order = create_order(request.user, offer, kind=kind, coupon_code="")
            create_subscription_invoice(order)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("windirect:plans")
        return redirect("windirect:subscription_checkout", order_pk=order.pk)

    # ==================== حالت ۲: صفحهٔ پرداخت ====================
    order = get_object_or_404(
        SubscriptionOrder.objects.select_related("offer__plan", "referral"),
        pk=order_pk,
        user=request.user,
    )

    # اطمینان از وجود فاکتور
    invoice = getattr(order, "invoice", None)
    if invoice is None:
        invoice = create_subscription_invoice(order)

    # اگه سفارش دیگه pending نیست، فقط نمایش
    if order.status != "pending":
        context = _context(request.user)
        context.update(order=order, invoice=invoice, form=None)
        return render(request, "windirect/subscriptions/checkout.html", context)

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
            logger.exception("خطای شروع پرداخت اشتراک %s", order.pk)
            form.add_error(
                None,
                "شروع پرداخت درگاه ممکن نشد. بعداً دوباره تلاش کنید؛ اشتراک هنوز فعال نشده است.",
            )

    context = _context(request.user)
    context.update(
        order=order,
        invoice=invoice,
        form=form,
    )
    return render(request, "windirect/subscriptions/checkout.html", context)


@login_required(login_url="accounts:login")
@require_POST
def apply_coupon(request, pk):
    """کد تخفیف رو روی سفارش اعمال می‌کنه و quote و invoice رو آپدیت می‌کنه."""
    order = get_object_or_404(
        SubscriptionOrder.objects.select_related("offer__plan"),
        pk=pk,
        user=request.user,
        status=SubscriptionOrder.Status.PENDING,
    )

    try:
        body = json.loads(request.body)
        code = body.get("code", "").strip().upper()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({
            "success": False,
            "message": "درخواست نامعتبر است.",
        }, status=400)

    if not code:
        return JsonResponse({
            "success": False,
            "message": "کد تخفیف را وارد کنید.",
        }, status=400)

    coupon = WindirectCoupon.objects.filter(code=code, is_active=True).first()
    if not coupon:
        return JsonResponse({
            "success": False,
            "message": "کد تخفیف معتبر نیست.",
        }, status=404)

    if not coupon.is_valid():
        return JsonResponse({
            "success": False,
            "message": "این کد تخفیف منقضی شده یا به حد استفاده رسیده است.",
        }, status=400)

    account = account_for(request.user)
    try:
        new_quote, _ = _build_quote(
            account,
            order.offer,
            order.kind,
            code,
        )
    except ValidationError as error:
        return JsonResponse({
            "success": False,
            "message": error.messages[0] if error.messages else str(error),
        }, status=400)

    order.quote = new_quote
    order.save(update_fields=["quote", "updated_at"])

    invoice = getattr(order, "invoice", None)
    if invoice and not invoice.is_paid:
        invoice.base_plan_cost = new_quote["base"]
        invoice.plan_discount_amount = new_quote["discount"]
        invoice.plan_cost = new_quote["net"]
        invoice.plan_vat = new_quote["vat"]
        invoice.discount_amount = new_quote["discount"]
        invoice.total_amount = new_quote["base"]
        invoice.payable_amount = new_quote["total"]
        invoice.total_vat = new_quote["vat"]
        invoice.save(update_fields=[
            "base_plan_cost", "plan_discount_amount", "plan_cost",
            "plan_vat", "discount_amount", "total_amount",
            "payable_amount", "total_vat",
        ])

    return JsonResponse({
        "success": True,
        "message": f"کد «{coupon.code}» با موفقیت اعمال شد.",
        "coupon_code": coupon.code,
        "quote": {
            "base": new_quote["base"],
            "discount": new_quote["discount"],
            "net": new_quote["net"],
            "vat": new_quote["vat"],
            "total": new_quote["total"],
            "vat_rate": new_quote["vat_rate"],
        },
    })


@login_required(login_url="accounts:login")
@require_POST
def remove_coupon(request, pk):
    """کد تخفیف رو از سفارش حذف می‌کنه."""
    order = get_object_or_404(
        SubscriptionOrder.objects.select_related("offer__plan"),
        pk=pk,
        user=request.user,
        status=SubscriptionOrder.Status.PENDING,
    )

    account = account_for(request.user)
    try:
        new_quote, _ = _build_quote(account, order.offer, order.kind, "")
    except ValidationError as error:
        return JsonResponse({
            "success": False,
            "message": error.messages[0] if error.messages else str(error),
        }, status=400)

    order.quote = new_quote
    order.save(update_fields=["quote", "updated_at"])

    invoice = getattr(order, "invoice", None)
    if invoice and not invoice.is_paid:
        invoice.plan_discount_amount = 0
        invoice.discount_amount = 0
        invoice.plan_cost = new_quote["net"]
        invoice.plan_vat = new_quote["vat"]
        invoice.payable_amount = new_quote["total"]
        invoice.total_vat = new_quote["vat"]
        invoice.save(update_fields=[
            "plan_discount_amount", "discount_amount", "plan_cost",
            "plan_vat", "payable_amount", "total_vat",
        ])

    return JsonResponse({
        "success": True,
        "message": "کد تخفیف حذف شد.",
        "quote": {
            "base": new_quote["base"],
            "discount": new_quote["discount"],
            "net": new_quote["net"],
            "vat": new_quote["vat"],
            "total": new_quote["total"],
            "vat_rate": new_quote["vat_rate"],
        },
    })


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
                    _as_datetime(context["periods"][-1].ends_at) - timezone.now()
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
    order = get_object_or_404(SubscriptionOrder, pk=pk, user=request.user)
    invoice = getattr(order, "invoice", None)
    context = _context(request.user)
    context.update(
        order=order,
        invoice=invoice,
        payments=invoice.payments.select_related("invoice").order_by("-created_at") if invoice else [],
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