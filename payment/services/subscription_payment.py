"""پرداخت اشتراک با کیف پول و زرین‌پال و اتصال به تسهیم موجود پروژه."""

import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django_iranian_payment.contrib.django import services as gateway
from payment.models import (
    Invoice,
    Payment,
    Transaction,
    Wallet,
    CommissionSplit,
    SubscriptionPaymentAttempt,
)
from payment.services.payout import payout_commission, PayoutError
from payment.services.commission import calculate_subscription_breakdown
from payment.services.zarinpal_flow import callback_url
from windirect.models import SubscriptionOrder, SubscriptionAccount
from windirect.subscriptions.services import account_for, validate_order, fulfil_order

logger = logging.getLogger(__name__)


def _lock_accounts(order):
    """حساب خریدار و معرف را با ترتیب ثابت برای جلوگیری از رقابت قفل می‌کند."""
    user_ids = {order.user_id}
    if order.referral_id:
        user_ids.add(order.referral.owner_id)
    for user in get_user_model().objects.filter(pk__in=user_ids):
        account_for(user)
    accounts = list(
        SubscriptionAccount.objects.select_for_update()
        .filter(user_id__in=user_ids)
        .order_by("user_id")
    )
    return next(a for a in accounts if a.user_id == order.user_id)


def _lock_wallets(order):
    """کیف پول خریدار و مدیران را پیش از برداشت و تسهیم به ترتیب قفل می‌کند."""
    user_ids = set(
        get_user_model()
        .objects.filter(role__in=["ceo", "developer"], is_active=True)
        .values_list("pk", flat=True)
    )
    user_ids.add(order.user_id)
    for user_id in sorted(user_ids):
        Wallet.objects.get_or_create(user_id=user_id)
    wallets = list(
        Wallet.objects.select_for_update()
        .filter(user_id__in=user_ids)
        .order_by("user_id")
    )
    return next(w for w in wallets if w.user_id == order.user_id)


def _record_success(order, invoice, account, payment):
    """فاکتور، حق دسترسی و تسهیم را ثبت می‌کند؛ نبود مدیر وجه خریدار را گم نمی‌کند."""
    invoice.is_paid = True
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=["is_paid", "paid_at"])
    fulfil_order(order, account)
    breakdown = calculate_subscription_breakdown(invoice)
    CommissionSplit.objects.get_or_create(
        invoice=invoice,
        defaults={
            "ceo_amount": breakdown.ceo_amount,
            "developer_amount": breakdown.developer_amount,
            "site_maintenance_amount": breakdown.site_maintenance_amount,
            "snapshot": breakdown.setting_snapshot,
        },
    )
    try:
        # تابع موجود در یک savepoint جدا اجرا می‌شود؛ در نبود مدیر، واریز قابل تلاش مجدد است.
        payout_commission(invoice)
    except PayoutError as error:
        logger.error(
            "تسهیم اشتراک فاکتور %s در انتظار اصلاح مدیران: %s", invoice.pk, error
        )


@transaction.atomic
def pay_subscription_wallet(order, user):
    """برداشت، ثبت پرداخت و اعطای اشتراک را یک‌بار و اتمیک انجام می‌دهد."""
    order = (
        SubscriptionOrder.objects.select_for_update()
        .select_related("referral__owner", "offer__plan")
        .get(pk=order.pk, user=user)
    )
    invoice = Invoice.objects.select_for_update().get(subscription_order=order)
    if order.status == "paid":
        return order
    account = _lock_accounts(order)
    validate_order(order, account)
    if order.attempts.filter(payment__status="pending").exists():
        raise ValidationError(
            "این سفارش در حال پرداخت درگاه است. ابتدا آن را لغو و سفارش جدید ایجاد کنید."
        )
    wallet = _lock_wallets(order)
    amount = invoice.payable_amount
    if wallet.balance < amount:
        raise ValidationError("موجودی کیف پول برای این خرید کافی نیست.")
    Wallet.objects.filter(pk=wallet.pk).update(
        balance=F("balance") - amount, updated_at=timezone.now()
    )
    payment = Payment.objects.create(
        user=user,
        invoice=invoice,
        amount=amount,
        payment_method=Payment.Method.WALLET,
        status=Payment.Status.SUCCESS,
        ref_id=f"WD-WALLET-{order.pk}",
    )
    Transaction.objects.create(
        user=user,
        invoice=invoice,
        payment=payment,
        amount=amount,
        type=Transaction.Type.SUBSCRIPTION_PAYMENT,
        reference_id=payment.ref_id,
        description=f'پرداخت اشتراک {order.quote["plan_name"]} از کیف پول',
    )
    _record_success(order, invoice, account, payment)
    return order


def start_subscription_gateway(order, user):
    """تلاش پرداخت را پیش از تماس شبکه ذخیره می‌کند و از مبلغ دیتابیس استفاده می‌کند."""
    with transaction.atomic():
        order = (
            SubscriptionOrder.objects.select_for_update()
            .select_related("referral__owner")
            .get(pk=order.pk, user=user)
        )
        invoice = Invoice.objects.select_for_update().get(subscription_order=order)
        account = _lock_accounts(order)
        validate_order(order, account)
        pending = order.attempts.filter(
            payment__status="pending", verified_at__isnull=True
        ).first()
        if pending:
            if pending.gateway_url:
                return pending.gateway_url
            raise ValidationError(
                "درخواست درگاه در حال آماده‌سازی است. کمی بعد دوباره تلاش کنید."
            )
        payment = Payment.objects.create(
            user=user,
            invoice=invoice,
            amount=invoice.payable_amount,
            payment_method=Payment.Method.GATEWAY,
            status=Payment.Status.PENDING,
        )
        attempt = SubscriptionPaymentAttempt.objects.create(
            order=order, payment=payment
        )
    try:
        from django.conf import settings

        config = settings.IRANIAN_PAYMENT["gateways"]["zarinpal"]
        if not config.get("sandbox") and config.get("merchant_id", "").startswith(
            "xxxxxxxx"
        ):
            raise ValidationError(
                "شناسهٔ واقعی زرین‌پال برای محیط پروداکشن تنظیم نشده است."
            )
        record, url = gateway.start_payment(
            "zarinpal",
            amount=invoice.payable_amount,
            currency="toman",
            callback_url=callback_url("payment:subscription_callback"),
            order_id=f"windirect-{attempt.pk}",
            description=invoice.description,
            mobile=user.phone_number,
        )
        from payment.services.zarinpal_flow import is_allowed_gateway_url

        if not record.authority or not is_allowed_gateway_url(url):
            raise ValidationError("پاسخ درگاه معتبر نیست.")
        with transaction.atomic():
            attempt = SubscriptionPaymentAttempt.objects.select_for_update().get(
                pk=attempt.pk
            )
            attempt.authority = record.authority
            attempt.gateway_url = url
            attempt.save(update_fields=["authority", "gateway_url"])
            Payment.objects.filter(pk=payment.pk).update(authority=record.authority)
        return url
    except Exception:
        Payment.objects.filter(pk=payment.pk, status="pending").update(
            status=Payment.Status.FAILED
        )
        raise


@transaction.atomic
def settle_subscription_gateway(attempt, record):
    """تأیید قطعی درگاه را حتی پس از تغییر وضعیت سفارش یک‌بار تعیین تکلیف می‌کند."""
    order = (
        SubscriptionOrder.objects.select_for_update()
        .select_related("referral__owner", "offer__plan")
        .get(pk=attempt.order_id)
    )
    invoice = Invoice.objects.select_for_update().get(subscription_order=order)
    attempt = SubscriptionPaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.verified_at:
        return order
    if (
        record is None
        or str(record.status).lower() != "complete"
        or record.authority != attempt.authority
        or record.order_id != f"windirect-{attempt.pk}"
        or int(record.amount) != invoice.payable_amount * 10
        or record.gateway_slug != "zarinpal"
    ):
        raise ValidationError("تأیید پرداخت با سفارش و مبلغ ثبت‌شده تطابق ندارد.")
    account = _lock_accounts(order)
    wallet = _lock_wallets(order)
    payment = Payment.objects.select_for_update().get(pk=attempt.payment_id)
    payment.status = Payment.Status.SUCCESS
    payment.ref_id = record.reference_id
    payment.save(update_fields=["status", "ref_id"])
    try:
        validate_order(order, account)
    except ValidationError:
        # وجه سفارش دیرهنگام یا پرداخت دوم به کیف پول خریدار برمی‌گردد؛ به مدیران نمی‌رود.
        Wallet.objects.filter(pk=wallet.pk).update(
            balance=F("balance") + invoice.payable_amount, updated_at=timezone.now()
        )
        Transaction.objects.create(
            user=order.user,
            invoice=invoice,
            payment=payment,
            amount=invoice.payable_amount,
            type=Transaction.Type.DEPOSIT,
            reference_id=record.reference_id,
            description="اعتبار وجه پرداخت تأییدشدهٔ اشتراک؛ سفارش منقضی، تغییرکرده یا قبلاً پرداخت شده بود.",
        )
        if order.status != "paid":
            order.status = "credited"
            order.settled_at = timezone.now()
            order.save(update_fields=["status", "settled_at"])
    else:
        Transaction.objects.create(
            user=order.user,
            invoice=invoice,
            payment=payment,
            amount=invoice.payable_amount,
            type=Transaction.Type.SUBSCRIPTION_GATEWAY,
            reference_id=record.reference_id,
            description=f'پرداخت اشتراک {order.quote["plan_name"]} از زرین‌پال',
        )
        _record_success(order, invoice, account, payment)
    attempt.verified_at = timezone.now()
    attempt.save(update_fields=["verified_at"])
    return order


def verify_subscription_gateway(attempt):
    """تماس تأیید درگاه خارج از قفل‌ها انجام می‌شود و در خطای شبکه قابل تکرار است."""
    record = gateway.verify_payment(slug="zarinpal", authority=attempt.authority)
    if record is None or str(record.status).lower() != "complete":
        raise ValidationError(
            "پرداخت هنوز توسط درگاه تأیید نشده است. امکان بررسی دوباره وجود دارد."
        )
    return settle_subscription_gateway(attempt, record)
