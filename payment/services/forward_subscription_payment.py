"""سرویس پرداخت اشتراک وین فوروارد با کیف پول و درگاه زرین‌پال (سندباکس و واقعی) + تسهیم اختیاری."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django_iranian_payment.contrib.django import services as gateway

from payment.models import (
    CommissionSplit,
    Invoice,
    Payment,
    Transaction,
    Wallet,
)
from payment.services.commission import calculate_subscription_breakdown
from payment.services.payout import PayoutError, payout_commission
from payment.services.zarinpal_flow import callback_url, is_allowed_gateway_url
from product.forward.subscriptions.models import ForwardSubscriptionOrder
from product.forward.subscriptions.services import fulfil_forward_order

logger = logging.getLogger(__name__)


def _lock_user_and_admin_wallets(buyer_user_id: int) -> Wallet:
    """قفل کردن کیف پول خریدار (و در صورت فعال بودن تسهیم، کیف پول مدیران) به ترتیب ثابت.

    :param buyer_user_id: شناسه کاربری خریدار.
    :return: آبجکت قفل‌شده Wallet متعلق به خریدار.
    """
    user_ids = {buyer_user_id}
    if getattr(settings, "FORWARD_ENABLE_COMMISSION_SPLIT", False):
        admin_ids = (
            get_user_model()
            .objects.filter(role__in=["ceo", "developer"], is_active=True)
            .values_list("pk", flat=True)
        )
        user_ids.update(admin_ids)

    for uid in sorted(user_ids):
        Wallet.objects.get_or_create(user_id=uid)

    wallets = list(
        Wallet.objects.select_for_update()
        .filter(user_id__in=user_ids)
        .order_by("user_id")
    )
    return next(w for w in wallets if w.user_id == buyer_user_id)


def _record_forward_success(order: ForwardSubscriptionOrder, invoice: Invoice) -> None:
    """ثبت پرداخت موفق فاکتور، اعطای دسترسی پلتفرم‌ها و اجرای اختیاری تسهیم مدیران.

    :param order: سفارش اشتراک وین فوروارد.
    :param invoice: فاکتور متناظر در اپ payment.
    """
    invoice.is_paid = True
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=["is_paid", "paid_at"])

    fulfil_forward_order(order)

    # قابلیت تسهیم آماده است و با تنظیم FORWARD_ENABLE_COMMISSION_SPLIT = True در settings فعال می‌شود
    if getattr(settings, "FORWARD_ENABLE_COMMISSION_SPLIT", False):
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
            payout_commission(invoice)
        except PayoutError as error:
            logger.error("تسهیم اشتراک وین فوروارد فاکتور %s ناموفق بود: %s", invoice.pk, error)


@transaction.atomic
def pay_forward_subscription_wallet(order: ForwardSubscriptionOrder, user) -> ForwardSubscriptionOrder:
    """پرداخت اتمیک سفارش اشتراک وین فوروارد از کیف پول کاربر و فعال‌سازی پلتفرم‌ها.

    :param order: سفارش اشتراک در انتظار پرداخت.
    :param user: کاربر مالک سفارش.
    :return: سفارش به‌روزرسانی‌شده با وضعیت PAID.
    """
    order = (
        ForwardSubscriptionOrder.objects.select_for_update()
        .select_related("plan")
        .get(pk=order.pk, user=user)
    )
    invoice = Invoice.objects.select_for_update().get(forward_subscription_order=order)
    if order.status == ForwardSubscriptionOrder.Status.PAID:
        return order

    if invoice.payments.filter(status=Payment.Status.PENDING).exists():
        raise ValidationError("این سفارش دارای پرداخت در حال انجام در درگاه است. لطفاً ابتدا وضعیت آن را بررسی کنید.")

    wallet = _lock_user_and_admin_wallets(order.user_id)
    amount = invoice.payable_amount
    if wallet.balance < amount:
        raise ValidationError("موجودی کیف پول شما برای پرداخت این سفارش کافی نیست.")

    Wallet.objects.filter(pk=wallet.pk).update(
        balance=F("balance") - amount,
        updated_at=timezone.now(),
    )

    payment = Payment.objects.create(
        user=user,
        invoice=invoice,
        amount=amount,
        payment_method=Payment.Method.WALLET,
        status=Payment.Status.SUCCESS,
        ref_id=f"WF-WALLET-{order.pk}",
    )

    Transaction.objects.create(
        user=user,
        invoice=invoice,
        payment=payment,
        amount=amount,
        type=Transaction.Type.FORWARD_SUBSCRIPTION_PAYMENT,
        reference_id=payment.ref_id,
        description=f"خرید بسته توکن وین فوروارد ({order.plan.name} · {order.tokens_amount:,} توکن) از کیف پول",
    )

    _record_forward_success(order, invoice)
    return order


def start_forward_subscription_gateway(order: ForwardSubscriptionOrder, user) -> str:
    """شروع پرداخت آنلاین سفارش وین فوروارد از طریق درگاه زرین‌پال (سندباکس یا واقعی).

    :param order: سفارش اشتراک وین فوروارد.
    :param user: کاربر مالک سفارش.
    :return: آدرس درگاه پرداخت زرین‌پال برای هدایت کاربر.
    """
    with transaction.atomic():
        order = (
            ForwardSubscriptionOrder.objects.select_for_update()
            .select_related("plan")
            .get(pk=order.pk, user=user)
        )
        if order.status == ForwardSubscriptionOrder.Status.PAID:
            raise ValidationError("این سفارش قبلاً پرداخت شده است.")

        invoice = Invoice.objects.select_for_update().get(forward_subscription_order=order)
        pending = (
            invoice.payments.filter(status=Payment.Status.PENDING, authority__isnull=False)
            .exclude(authority="")
            .first()
        )
        if pending:
            raise ValidationError("پرداخت درگاه قبلی برای این سفارش هنوز در انتظار است. از دکمه بررسی مجدد استفاده کنید.")

        payment = Payment.objects.create(
            user=user,
            invoice=invoice,
            amount=invoice.payable_amount,
            payment_method=Payment.Method.GATEWAY,
            status=Payment.Status.PENDING,
        )

    try:
        config = settings.IRANIAN_PAYMENT["gateways"]["zarinpal"]
        if not config.get("sandbox") and config.get("merchant_id", "").startswith("xxxxxxxx"):
            raise ValidationError("شناسه واقعی زرین‌پال برای محیط پروداکشن تنظیم نشده است.")

        record, url = gateway.start_payment(
            "zarinpal",
            amount=invoice.payable_amount,
            currency="toman",
            callback_url=callback_url("payment:forward_subscription_callback"),
            order_id=f"winforward-{payment.pk}",
            description=invoice.description,
            mobile=user.phone_number,
        )
        if not record.authority or not is_allowed_gateway_url(url):
            raise ValidationError("پاسخ دریافتی از درگاه زرین‌پال معتبر نیست.")

        with transaction.atomic():
            Payment.objects.filter(pk=payment.pk).update(authority=record.authority)
        return url
    except Exception:
        Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED
        )
        raise


@transaction.atomic
def settle_forward_subscription_gateway(payment: Payment, record) -> ForwardSubscriptionOrder:
    """نهایی‌سازی اتمیک پرداخت درگاه زرین‌پال، ثبت تراکنش و فعال‌سازی اشتراک وین فوروارد.

    :param payment: رکورد Payment در وضعیت در انتظار.
    :param record: نتیجه تاییدشده از gateway.verify_payment.
    :return: سفارش پرداخت‌شده ForwardSubscriptionOrder.
    """
    payment = Payment.objects.select_for_update().select_related(
        "invoice__forward_subscription_order__plan"
    ).get(pk=payment.pk)
    invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)
    order = ForwardSubscriptionOrder.objects.select_for_update().select_related("plan").get(
        pk=invoice.forward_subscription_order_id
    )

    if payment.status == Payment.Status.SUCCESS:
        return order

    if (
        record is None
        or str(record.status).lower() != "complete"
        or record.authority != payment.authority
        or record.order_id != f"winforward-{payment.pk}"
        or int(record.amount) != invoice.payable_amount * 10
        or record.gateway_slug != "zarinpal"
    ):
        raise ValidationError("اطلاعات تایید پرداخت با سفارش و مبلغ ثبت‌شده مطابقت ندارد.")

    _lock_user_and_admin_wallets(order.user_id)
    payment.status = Payment.Status.SUCCESS
    payment.ref_id = record.reference_id
    payment.save(update_fields=["status", "ref_id"])

    Transaction.objects.create(
        user=order.user,
        invoice=invoice,
        payment=payment,
        amount=invoice.payable_amount,
        type=Transaction.Type.FORWARD_SUBSCRIPTION_GATEWAY,
        reference_id=record.reference_id,
        description=f"خرید بسته توکن وین فوروارد ({order.plan.name} · {order.tokens_amount:,} توکن) از زرین‌پال - کد پیگیری: {record.reference_id}",
    )

    _record_forward_success(order, invoice)
    return order


def verify_forward_subscription_gateway(payment: Payment) -> ForwardSubscriptionOrder:
    """استعلام تایید تراکنش از سرور زرین‌پال و تسویه سفارش اشتراک وین فوروارد.

    :param payment: رکورد Payment دارای authority.
    :return: سفارش تکمیل‌شده ForwardSubscriptionOrder.
    """
    record = gateway.verify_payment(slug="zarinpal", authority=payment.authority)
    if record is None or str(record.status).lower() != "complete":
        raise ValidationError("پرداخت هنوز توسط درگاه تایید نشده است. می‌توانید دوباره بررسی کنید.")
    return settle_forward_subscription_gateway(payment, record)
