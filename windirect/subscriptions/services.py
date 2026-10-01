"""قواعد دورهٔ رایگان، قیمت‌گذاری، تمدید، ارتقا و هدیهٔ معرفی."""

from datetime import timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from payment import constants
from ..models import (
    SubscriptionPlan,
    SubscriptionOffer,
    SubscriptionAccount,
    SubscriptionOrder,
    UserSubscription,
    ReferralCode,
    ReferralRedemption,
    SubscriptionGift,
)

FEATURES = ("smart_comments", "smart_direct", "showcases", "forms")


def as_datetime(value):
    """تاریخ مدل شمسی را برای محاسبات دقیق زمانی به میلادی تبدیل می‌کند."""
    result = value.togregorian() if hasattr(value, "togregorian") else value
    return timezone.make_aware(result) if timezone.is_naive(result) else result


def money(value):
    """مبلغ را یک‌بار با گردکردن نیم‌به‌بالا به تومان صحیح تبدیل می‌کند."""
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def account_for(user):
    """حساب اشتراک را بدون فعال‌سازی خودکار رایگان ایجاد می‌کند."""
    return SubscriptionAccount.objects.get_or_create(user=user)[0]


def current_period(user, now=None):
    """بازهٔ فعال را در زمان درخواست، مستقل از کار زمان‌بندی‌شده پیدا می‌کند."""
    now = now or timezone.now()
    account = SubscriptionAccount.objects.filter(user=user).first()
    if not account:
        return None
    return (
        account.periods.filter(starts_at__lte=now, ends_at__gt=now, is_superseded=False)
        .select_related("offer__plan")
        .first()
    )


def remaining_periods(account, now=None):
    """دوره‌های فعلی و رزروشده را با ترتیب ثابت می‌خواند."""
    return list(
        account.periods.filter(ends_at__gt=now or timezone.now(), is_superseded=False)
        .select_related("offer__plan")
        .order_by("starts_at", "pk")
    )


def _append_period(
    account,
    offer,
    caps,
    name,
    days,
    kind,
    order=None,
    credit_daily=0,
    now=None,
    reference_days=None,
):
    """دسترسی جدید را بعد از آخرین دورهٔ موجود اضافه می‌کند."""
    now = now or timezone.now()
    periods = remaining_periods(account, now)
    start = max(now, as_datetime(periods[-1].ends_at)) if periods else now
    return UserSubscription.objects.create(
        account=account,
        offer=offer,
        order=order,
        kind=kind,
        starts_at=start,
        ends_at=start + timedelta(days=days),
        capabilities=caps,
        plan_name=name,
        duration_days=reference_days or offer.duration_days,
        credit_daily=credit_daily,
    )


@transaction.atomic
def activate_trial(user, offer):
    """فقط با درخواست کاربر یک دورهٔ رایگان قابل عرضه را فعال می‌کند."""
    account_for(user)
    account = SubscriptionAccount.objects.select_for_update().get(user=user)
    offer = SubscriptionOffer.objects.select_related("plan").get(pk=offer.pk)
    if (
        not offer.is_active
        or not offer.plan.is_active
        or not offer.plan.is_trial
        or offer.price != 0
        or offer.duration_days != 30
    ):
        raise ValidationError("این دورهٔ رایگان قابل فعال‌سازی نیست.")
    if account.trial_used_at or account.first_paid_at:
        raise ValidationError(
            "دورهٔ رایگان فقط یک بار و پیش از اولین خرید پولی قابل فعال‌سازی است."
        )
    period = _append_period(
        account, offer, offer.plan.capabilities(), offer.plan.name, 30, "trial"
    )
    account.trial_used_at = timezone.now()
    account.revision += 1
    account.save(update_fields=["trial_used_at", "revision"])
    return period


def _build_quote(account, offer, kind, code="", now=None):
    """قیمت و سیاست ارتقا را از ورودی‌های معتبر سرور محاسبه می‌کند."""
    now = now or timezone.now()
    offer = SubscriptionOffer.objects.select_related("plan").get(pk=offer.pk)
    plan = offer.plan
    if (
        constants.WINDIRECT_CEO_POOL_PERCENT
        + constants.WINDIRECT_DEVELOPER_POOL_PERCENT
        != 100
        or not 0 <= constants.WINDIRECT_MAINTENANCE_PERCENT <= 100
    ):
        raise ValidationError("درصدهای تسهیم اشتراک در ثابت‌های پرداخت معتبر نیستند.")
    if not plan.is_active or not offer.is_active or plan.is_trial or offer.price <= 0:
        raise ValidationError("این گزینهٔ خرید فعال نیست.")
    if plan.level < account.highest_level:
        raise ValidationError("کاهش پلن خریداری‌شده مجاز نیست.")
    periods = remaining_periods(account, now)
    paid = [p for p in periods if p.kind != "trial"]
    referral = None
    discount = 0
    upgrades = []
    if kind == "upgrade":
        if not paid:
            raise ValidationError(
                "برای ارتقا باید یک دورهٔ پولی یا هدیهٔ وابسته به خرید باقی مانده باشد."
            )
        if plan.level <= max(p.capabilities["level"] for p in paid):
            raise ValidationError("پلن مقصد باید سطح بالاتری داشته باشد.")
        if offer.duration_days != paid[0].duration_days:
            raise ValidationError(
                "ارتقا باید با دورهٔ فروش متناظر با اشتراک فعلی انجام شود."
            )
        base = Decimal(0)
        for period in paid:
            target = SubscriptionOffer.objects.filter(
                plan=plan,
                duration_days=period.duration_days,
                is_active=True,
                price__gt=0,
            ).first()
            if target is None:
                raise ValidationError(
                    f"قیمت حرفه‌ای برای دورهٔ {period.duration_days} روزه تعریف نشده است."
                )
            start = max(now, as_datetime(period.starts_at))
            remaining = Decimal(
                str((as_datetime(period.ends_at) - start).total_seconds())
            ) / Decimal(86400)
            target_daily = Decimal(target.price) / Decimal(target.duration_days)
            # هدیه اعتبار نقدی ندارد؛ برای ارتقای آن قیمت مقصد کامل محاسبه می‌شود.
            credit = Decimal(period.credit_daily)
            difference = max(target_daily - credit, Decimal(0)) * remaining
            base += difference
            upgrades.append(
                {
                    "period_id": period.pk,
                    "offer_id": target.pk,
                    "daily": str(target_daily),
                    "days": str(remaining),
                    "credit_daily": str(credit),
                    "cost": str(difference),
                }
            )
        base = money(base)
        if code:
            raise ValidationError(
                "کد معرف فقط برای اولین خرید است و روی ارتقا اعمال نمی‌شود."
            )
    elif kind == "purchase":
        if paid and plan.level != paid[-1].capabilities["level"]:
            raise ValidationError("برای تغییر پلن فعال، از گزینهٔ ارتقا استفاده کنید.")
        base = offer.price
        if code:
            code = code.strip().upper()
            referral = (
                ReferralCode.objects.select_related("owner")
                .filter(code=code, is_active=True, owner__is_active=True)
                .first()
            )
            if referral is None or referral.owner_id == account.user_id:
                raise ValidationError("کد معرف معتبر نیست یا متعلق به خودتان است.")
            if (
                account.first_paid_at
                or ReferralRedemption.objects.filter(buyer_id=account.user_id).exists()
            ):
                raise ValidationError(
                    "مزایای معرف فقط در اولین خرید موفق قابل استفاده است."
                )
            discount = money(
                Decimal(base)
                * Decimal(constants.WINDIRECT_REFERRAL_DISCOUNT_PERCENT)
                / 100
            )
    else:
        raise ValidationError("نوع سفارش نامعتبر است.")
    net = base - discount
    if net <= 0:
        raise ValidationError("مبلغ خرید یا ارتقا باید مثبت باشد.")
    vat = money(Decimal(net) * Decimal(str(constants.VAT_PERCENT)))
    quote = {
        "plan_name": plan.name,
        "capabilities": plan.capabilities(),
        "duration_days": offer.duration_days,
        "base": base,
        "discount": discount,
        "net": net,
        "vat": vat,
        "total": net + vat,
        "vat_rate": str(constants.VAT_PERCENT),
        "quoted_at": now.isoformat(),
        "upgrades": upgrades,
        "buyer_gift_days": constants.WINDIRECT_BUYER_GIFT_DAYS if referral else 0,
        "owner_gift_days": constants.WINDIRECT_REFERRER_GIFT_DAYS if referral else 0,
        "maintenance_percent": constants.WINDIRECT_MAINTENANCE_PERCENT,
        "ceo_pool_percent": constants.WINDIRECT_CEO_POOL_PERCENT,
        "developer_pool_percent": constants.WINDIRECT_DEVELOPER_POOL_PERCENT,
    }
    return quote, referral


@transaction.atomic
def create_order(user, offer, kind="purchase", referral_code=""):
    """سفارش و فاکتور قطعی را با اعتبار پانزده دقیقه‌ای ایجاد می‌کند."""
    account_for(user)
    account = SubscriptionAccount.objects.select_for_update().get(user=user)
    quote, referral = _build_quote(account, offer, kind, referral_code)
    order = SubscriptionOrder.objects.create(
        user=user,
        offer=offer,
        kind=kind,
        quote=quote,
        account_revision=account.revision,
        referral=referral,
        expires_at=timezone.now() + timedelta(minutes=15),
    )
    from payment.services.create_invoice import create_subscription_invoice

    create_subscription_invoice(order)
    return order


def validate_order(order, account, now=None):
    """سفارش قدیمی یا ناسازگار با تغییرات حساب را پیش از برداشت رد می‌کند."""
    now = now or timezone.now()
    if (
        order.status != "pending"
        or as_datetime(order.expires_at) <= now
        or account.revision != order.account_revision
    ):
        raise ValidationError(
            "سفارش منقضی شده یا وضعیت اشتراک تغییر کرده است؛ سفارش جدید بسازید."
        )
    if (
        order.kind == "upgrade"
        and not account.periods.filter(
            pk__in=[row["period_id"] for row in order.quote["upgrades"]],
            is_superseded=False,
            ends_at__gt=now,
        ).exists()
    ):
        raise ValidationError(
            "دورهٔ قابل ارتقا پایان یافته است؛ سفارش خرید جدید بسازید."
        )
    if order.referral_id and (
        account.first_paid_at
        or ReferralRedemption.objects.filter(buyer=order.user).exists()
    ):
        raise ValidationError("تخفیف معرفی قبلاً مصرف شده است.")


def _grant_gift(account, redemption, days, buyer_period=None):
    """هدیه را به دورهٔ پولی اضافه یا برای خرید بعدی ذخیره می‌کند."""
    gift = SubscriptionGift.objects.create(
        account=account, redemption=redemption, days=days
    )
    periods = remaining_periods(account)
    paid_periods = [period for period in periods if period.kind != "trial"]
    eligible = buyer_period or (paid_periods[-1] if paid_periods else None)
    if eligible:
        gift.period = _append_period(
            account,
            eligible.offer,
            eligible.capabilities,
            eligible.plan_name,
            days,
            "gift",
            order=redemption.order if buyer_period else None,
            reference_days=eligible.duration_days,
        )
        gift.save(update_fields=["period"])
    else:
        account.banked_gift_days += days


def fulfil_order(order, account):
    """پس از تأیید پرداخت، دسترسی و هدیه‌ها را یک‌بار ایجاد می‌کند؛ داخل تراکنش فراخوانی شود."""
    now = timezone.now()
    quote = order.quote
    if order.kind == "purchase":
        period = _append_period(
            account,
            order.offer,
            quote["capabilities"],
            quote["plan_name"],
            quote["duration_days"],
            "paid",
            order=order,
            credit_daily=Decimal(quote["net"]) / Decimal(quote["duration_days"]),
            now=now,
            reference_days=quote["duration_days"],
        )
        if account.banked_gift_days:
            gift_period = _append_period(
                account,
                order.offer,
                quote["capabilities"],
                quote["plan_name"],
                account.banked_gift_days,
                "gift",
                order=order,
                reference_days=quote["duration_days"],
            )
            account.gifts.filter(period__isnull=True).update(period=gift_period)
            account.banked_gift_days = 0
        if order.referral_id:
            redemption = ReferralRedemption.objects.create(
                buyer=order.user,
                referral=order.referral,
                order=order,
                buyer_days=quote["buyer_gift_days"],
                owner_days=quote["owner_gift_days"],
            )
            _grant_gift(
                account, redemption, quote["buyer_gift_days"], buyer_period=period
            )
            owner_account = SubscriptionAccount.objects.select_for_update().get(
                user=order.referral.owner
            )
            _grant_gift(owner_account, redemption, quote["owner_gift_days"])
            owner_account.revision += 1
            owner_account.save(update_fields=["banked_gift_days", "revision"])
    else:
        quoted_at = datetime.fromisoformat(quote["quoted_at"])
        for row in quote["upgrades"]:
            period = UserSubscription.objects.select_for_update().get(
                pk=row["period_id"], account=account
            )
            start = as_datetime(period.starts_at)
            end = as_datetime(period.ends_at)
            if start < quoted_at:
                period.ends_at = quoted_at
                period.save(update_fields=["ends_at"])
                start = quoted_at
            else:
                period.is_superseded = True
                period.save(update_fields=["is_superseded"])
            UserSubscription.objects.create(
                account=account,
                offer_id=row["offer_id"],
                order=order,
                kind="paid",
                starts_at=start,
                ends_at=end,
                capabilities=quote["capabilities"],
                plan_name=quote["plan_name"],
                duration_days=period.duration_days,
                credit_daily=Decimal(row["daily"]),
            )
    account.first_paid_at = account.first_paid_at or now
    account.highest_level = max(account.highest_level, quote["capabilities"]["level"])
    account.revision += 1
    account.save(
        update_fields=["first_paid_at", "highest_level", "revision", "banked_gift_days"]
    )
    order.status = "paid"
    order.settled_at = now
    order.save(update_fields=["status", "settled_at"])
