"""سرویس‌های منطق کسب‌وکار اشتراک وین فوروارد — محاسبه قیمت، صدور فاکتور، فعال‌سازی و تمدید."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .access import get_user_platform_access_map
from .models import (
    FORWARD_PLATFORM_LABELS,
    FORWARD_PLATFORM_SLUGS,
    ForwardPlatformAccess,
    ForwardSubscriptionAccount,
    ForwardSubscriptionOrder,
    ForwardSubscriptionPlan,
)


def account_for(user) -> ForwardSubscriptionAccount:
    """دریافت یا ایجاد حساب اشتراک وین فوروارد برای کاربر مشخص.

    :param user: نمونه کاربر سایت (CustomUser).
    :return: آبجکت ForwardSubscriptionAccount مربوط به کاربر.
    """
    account, _ = ForwardSubscriptionAccount.objects.get_or_create(user=user)
    return account


def _calculate_vat(subtotal: int) -> int:
    """محاسبه مالیات بر ارزش افزوده در صورت فعال بودن فلگ FORWARD_ENABLE_VAT در تنظیمات.

    :param subtotal: مبلغ پایه پیش از مالیات (تومان).
    :return: مبلغ مالیات به تومان (در حالت پیش‌فرض ۰).
    """
    if not getattr(settings, "FORWARD_ENABLE_VAT", False) or subtotal <= 0:
        return 0
    try:
        from payment.services.tax_calculator import calculate_vat
        return int(calculate_vat(subtotal))
    except Exception:
        return int(round(subtotal * 0.10))


def calculate_order_quote(
    user,
    plan: ForwardSubscriptionPlan,
    selected_platforms: List[str],
    order_kind: str = ForwardSubscriptionOrder.OrderKind.NEW,
) -> Dict[str, Any]:
    """محاسبه دقیق قیمت، مدت و اعتبارسنجی پلتفرم‌های انتخاب‌شده توسط کاربر.

    - در پلن رایگان ۷ روزه: تمام ۴ پلتفرم با قیمت ۰ تومان فعال می‌شوند (فقط یک‌بار برای هر کاربر).
    - در خرید جدید یا تمدید: پلتفرم بله («bale») اجباری است.
    - در افزودن پلتفرم در میانه دوره («add_platform»): قیمت بر اساس روزهای باقی‌مانده دوره فعلی بله محاسبه می‌شود.

    :param user: نمونه کاربر سایت.
    :param plan: پلن انتخاب‌شده.
    :param selected_platforms: لیست slug پلتفرم‌های انتخاب‌شده.
    :param order_kind: نوع سفارش ('new'، 'renew' یا 'add_platform').
    :return: دیکشنری کامل پیش‌فاکتور شامل مبالغ، مدت و لیست پلتفرم‌ها.
    """
    account = account_for(user)
    clean_platforms = []
    for slug in selected_platforms:
        if slug in FORWARD_PLATFORM_SLUGS and slug not in clean_platforms:
            clean_platforms.append(slug)

    if plan.is_trial:
        if not account.can_use_trial:
            raise ValidationError("شما قبلاً از دوره رایگان ۷ روزه خود استفاده کرده‌اید.")
        return {
            "order_kind": ForwardSubscriptionOrder.OrderKind.NEW,
            "platforms": list(FORWARD_PLATFORM_SLUGS),
            "duration_days": plan.duration_days,
            "price_per_platform": 0,
            "subtotal_amount": 0,
            "vat_amount": 0,
            "total_amount": 0,
        }

    access_map = get_user_platform_access_map(user)
    bale_access = access_map.get("bale")

    if order_kind == ForwardSubscriptionOrder.OrderKind.ADD_PLATFORM:
        if not bale_access or not bale_access.is_valid:
            raise ValidationError("برای افزودن پلتفرم جدید در میانه دوره، ابتدا باید اشتراک فعال بله داشته باشید.")
        new_platforms = [slug for slug in clean_platforms if slug not in access_map]
        if not new_platforms:
            raise ValidationError("لطفاً حداقل یک پلتفرم جدید که هنوز اشتراک فعال ندارد انتخاب کنید.")

        remaining_days = bale_access.remaining_days
        ref_plan = bale_access.plan or plan
        base_days = max(1, ref_plan.duration_days or 30)
        base_price = ref_plan.price_per_platform or plan.price_per_platform
        prorated_unit = max(1000, int(round(base_price * remaining_days / base_days)))
        subtotal = prorated_unit * len(new_platforms)
        vat = _calculate_vat(subtotal)
        return {
            "order_kind": ForwardSubscriptionOrder.OrderKind.ADD_PLATFORM,
            "platforms": new_platforms,
            "duration_days": remaining_days,
            "price_per_platform": prorated_unit,
            "subtotal_amount": subtotal,
            "vat_amount": vat,
            "total_amount": subtotal + vat,
        }

    # خرید جدید یا تمدید: پلتفرم بله اجباری است
    if "bale" not in clean_platforms:
        clean_platforms.insert(0, "bale")

    effective_kind = (
        ForwardSubscriptionOrder.OrderKind.RENEW
        if bale_access and bale_access.is_valid
        else ForwardSubscriptionOrder.OrderKind.NEW
    )
    unit_price = int(plan.price_per_platform)
    subtotal = unit_price * len(clean_platforms)
    vat = _calculate_vat(subtotal)

    return {
        "order_kind": effective_kind,
        "platforms": clean_platforms,
        "duration_days": plan.duration_days,
        "price_per_platform": unit_price,
        "subtotal_amount": subtotal,
        "vat_amount": vat,
        "total_amount": subtotal + vat,
    }


@transaction.atomic
def activate_trial_subscription(user, plan: ForwardSubscriptionPlan) -> ForwardSubscriptionOrder:
    """فعال‌سازی فوری و اتمیک اشتراک رایگان ۷ روزه برای تمام ۴ پلتفرم.

    :param user: نمونه کاربر سایت.
    :param plan: پلن رایگان ۷ روزه.
    :return: آبجکت ForwardSubscriptionOrder ثبت‌شده با وضعیت پرداخت‌شده.
    """
    account = ForwardSubscriptionAccount.objects.select_for_update().get(pk=account_for(user).pk)
    if not plan.is_trial:
        raise ValidationError("این متد فقط برای پلن رایگان قابل استفاده است.")
    if not account.can_use_trial:
        raise ValidationError("شما قبلاً از دوره رایگان ۷ روزه خود استفاده کرده‌اید.")

    now = timezone.now()
    expires_at = now + timedelta(days=plan.duration_days)

    order = ForwardSubscriptionOrder.objects.create(
        user=user,
        plan=plan,
        order_kind=ForwardSubscriptionOrder.OrderKind.NEW,
        platforms=list(FORWARD_PLATFORM_SLUGS),
        duration_days=plan.duration_days,
        price_per_platform=0,
        subtotal_amount=0,
        vat_amount=0,
        total_amount=0,
        status=ForwardSubscriptionOrder.Status.PAID,
        paid_at=now,
    )

    for slug in FORWARD_PLATFORM_SLUGS:
        ForwardPlatformAccess.objects.update_or_create(
            user=user,
            platform_slug=slug,
            defaults={
                "plan": plan,
                "started_at": now,
                "expires_at": expires_at,
                "is_active": True,
            },
        )

    account.trial_used_at = now
    account.save(update_fields=["trial_used_at"])
    return order


@transaction.atomic
def create_forward_order_with_invoice(
    user,
    plan: ForwardSubscriptionPlan,
    selected_platforms: List[str],
    order_kind: str = ForwardSubscriptionOrder.OrderKind.NEW,
):
    """ایجاد سفارش اشتراک پولی وین فوروارد به همراه فاکتور متناظر در اپ payment.

    :param user: نمونه کاربر سایت.
    :param plan: پلن انتخاب‌شده.
    :param selected_platforms: لیست slug پلتفرم‌ها.
    :param order_kind: نوع سفارش ('new'، 'renew' یا 'add_platform').
    :return: تاپل شامل (ForwardSubscriptionOrder, Invoice).
    """
    from payment.models import Invoice

    quote = calculate_order_quote(user, plan, selected_platforms, order_kind=order_kind)
    order = ForwardSubscriptionOrder.objects.create(
        user=user,
        plan=plan,
        order_kind=quote["order_kind"],
        platforms=quote["platforms"],
        duration_days=quote["duration_days"],
        price_per_platform=quote["price_per_platform"],
        subtotal_amount=quote["subtotal_amount"],
        vat_amount=quote["vat_amount"],
        total_amount=quote["total_amount"],
        status=ForwardSubscriptionOrder.Status.PENDING,
    )

    platform_names = "، ".join(FORWARD_PLATFORM_LABELS.get(s, s) for s in quote["platforms"])
    invoice = Invoice.objects.create(
        type=Invoice.Type.WINFORWARD,
        user=user,
        forward_subscription_order=order,
        base_plan_cost=quote["subtotal_amount"],
        plan_cost=quote["subtotal_amount"],
        plan_vat=quote["vat_amount"],
        tax_amount=quote["vat_amount"],
        payable_amount=quote["total_amount"],
        description=f"اشتراک وین فوروارد ({plan.name}) — پلتفرم‌ها: {platform_names}",
    )
    return order, invoice


@transaction.atomic
def fulfil_forward_order(order: ForwardSubscriptionOrder) -> None:
    """اعمال دسترسی پلتفرم‌ها پس از پرداخت موفق سفارش اشتراک وین فوروارد.

    - در خرید جدید یا تمدید: مدت دوره به تاریخ انقضای فعلی (یا زمان حال) اضافه می‌شود.
    - در افزودن پلتفرم در میانه دوره: تاریخ انقضای پلتفرم جدید دقیقاً با تاریخ انقضای بله همگام می‌شود.

    :param order: سفارش پرداخت‌شده ForwardSubscriptionOrder.
    """
    if order.status == ForwardSubscriptionOrder.Status.PAID:
        return

    now = timezone.now()
    account = ForwardSubscriptionAccount.objects.select_for_update().get(pk=account_for(order.user).pk)

    if order.order_kind == ForwardSubscriptionOrder.OrderKind.ADD_PLATFORM:
        bale_access = ForwardPlatformAccess.objects.filter(
            user=order.user, platform_slug="bale", is_active=True, expires_at__gt=now
        ).first()
        target_expiry = (
            bale_access.expires_at if bale_access else now + timedelta(days=order.duration_days)
        )
        for slug in order.platforms:
            ForwardPlatformAccess.objects.update_or_create(
                user=order.user,
                platform_slug=slug,
                defaults={
                    "plan": order.plan,
                    "started_at": now,
                    "expires_at": target_expiry,
                    "is_active": True,
                },
            )
    else:
        for slug in order.platforms:
            existing = ForwardPlatformAccess.objects.filter(
                user=order.user, platform_slug=slug
            ).first()
            base_time = (
                existing.expires_at
                if (existing and existing.is_active and existing.expires_at > now)
                else now
            )
            new_expiry = base_time + timedelta(days=order.duration_days)
            ForwardPlatformAccess.objects.update_or_create(
                user=order.user,
                platform_slug=slug,
                defaults={
                    "plan": order.plan,
                    "started_at": existing.started_at if (existing and existing.is_valid) else now,
                    "expires_at": new_expiry,
                    "is_active": True,
                },
            )

    order.status = ForwardSubscriptionOrder.Status.PAID
    order.paid_at = now
    order.save(update_fields=["status", "paid_at"])

    if not account.first_paid_at:
        account.first_paid_at = now
        account.save(update_fields=["first_paid_at"])
