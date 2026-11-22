"""سرویس‌های هسته سیستم توکنی وین فوروارد — محاسبه نرخ، کسر/شارژ اتمیک، هدیه و خرید بسته."""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    FORWARD_PLATFORM_SLUGS,
    ForwardSubscriptionAccount,
    ForwardSubscriptionOrder,
    ForwardSubscriptionPlan,
    ForwardTokenPricing,
    ForwardTokenTransaction,
)

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def account_for(user) -> ForwardSubscriptionAccount:
    """دریافت یا ایجاد کیف توکن وین فوروارد برای کاربر مشخص."""
    account, _ = ForwardSubscriptionAccount.objects.get_or_create(user=user)
    return account


def get_pricing_config() -> ForwardTokenPricing:
    """دریافت تنظیمات فعال نرخ مصرف توکن از دیتابیس."""
    return ForwardTokenPricing.get_active()


def get_max_file_size_bytes() -> int:
    """سقف حجم مجاز فایل به بایت (پیش‌فرض ۲۰ مگابایت)."""
    cfg = get_pricing_config()
    return int(cfg.max_file_size_mb or MAX_FILE_SIZE_MB) * 1024 * 1024


def calculate_delivery_token_cost(
    content_type: str,
    has_caption: bool = False,
    file_size_bytes: int = 0,
    is_hub: bool = False,
    use_ai_watermark: bool = False,
    pricing: Optional[ForwardTokenPricing] = None,
) -> int:
    """محاسبه دقیق توکن مصرفی برای هر تحویل موفق در یک کانال طبق تعرفه وین فوروارد.

    - متن ساده: ۲ توکن
    - عکس: ۲ توکن (+۲ با کپشن = ۴)
    - استیکر و گیف: ۳ توکن
    - صوت، ویس، فایل، ویدیو:
        زیر ۵ مگ: ۵ (+۲ با کپشن = ۷)
        ۵ تا ۱۰ مگ: ۷ (+۲ با کپشن = ۹)
        ۱۰ تا ۲۰ مگ: ۱۰ (+۲ با کپشن = ۱۲)
    - افزونه هاب تیمی: +۲ توکن
    - افزونه حذف واترمارک هوش مصنوعی: +۵ توکن
    """
    cfg = pricing or get_pricing_config()
    ctype = (content_type or "text").lower()

    if ctype == "text":
        cost = int(cfg.text_cost)
    elif ctype == "photo":
        cost = int(cfg.photo_cost) + (int(cfg.caption_extra_cost) if has_caption else 0)
    elif ctype in ("sticker", "animation"):
        cost = int(cfg.sticker_gif_cost)
    else:
        mb = (file_size_bytes or 0) / (1024 * 1024)
        if mb <= 5.0:
            base = int(cfg.media_under_5mb_cost)
        elif mb <= 10.0:
            base = int(cfg.media_5_to_10mb_cost)
        else:
            base = int(cfg.media_10_to_20mb_cost)
        cost = base + (int(cfg.caption_extra_cost) if has_caption else 0)

    if is_hub:
        cost += int(cfg.hub_extra_cost)
    if use_ai_watermark:
        cost += int(cfg.ai_watermark_extra_cost)
    return max(1, cost)


@transaction.atomic
def credit_tokens_atomic(
    user,
    amount: int,
    tx_type: str,
    description: str = "",
    broadcast_job_id: Optional[int] = None,
) -> int:
    """افزایش اتمیک توکن کاربر و ثبت سند در دفترکل تراکنش‌های توکن."""
    amount = int(amount)
    if amount <= 0:
        return account_for(user).token_balance
    acc_obj = account_for(user)
    acc = ForwardSubscriptionAccount.objects.select_for_update().get(pk=acc_obj.pk)
    acc.token_balance = int(acc.token_balance) + amount
    acc.total_tokens_earned = int(acc.total_tokens_earned) + amount
    acc.save(update_fields=["token_balance", "total_tokens_earned"])

    ForwardTokenTransaction.objects.create(
        user=user,
        tx_type=tx_type,
        amount=amount,
        balance_after=acc.token_balance,
        description=description[:255],
        broadcast_job_id=broadcast_job_id,
    )
    return acc.token_balance


@transaction.atomic
def deduct_tokens_atomic(
    user,
    amount: int,
    description: str = "",
    broadcast_job_id: Optional[int] = None,
) -> tuple[bool, int]:
    """کسر اتمیک توکن از حساب کاربر در صورت کافی بودن موجودی؛ خروجی: (موفقیت، موجودی جدید)."""
    amount = int(amount)
    if amount <= 0:
        return True, account_for(user).token_balance
    acc_obj = account_for(user)
    acc = ForwardSubscriptionAccount.objects.select_for_update().get(pk=acc_obj.pk)
    if int(acc.token_balance) < amount:
        return False, int(acc.token_balance)

    acc.token_balance = int(acc.token_balance) - amount
    acc.total_tokens_spent = int(acc.total_tokens_spent) + amount
    acc.save(update_fields=["token_balance", "total_tokens_spent"])

    ForwardTokenTransaction.objects.create(
        user=user,
        tx_type=ForwardTokenTransaction.TxType.SPEND,
        amount=-amount,
        balance_after=acc.token_balance,
        description=description[:255],
        broadcast_job_id=broadcast_job_id,
    )
    return True, acc.token_balance


def _calculate_vat(subtotal: int) -> int:
    """محاسبه مالیات بر ارزش افزوده در صورت فعال بودن FORWARD_ENABLE_VAT."""
    if not getattr(settings, "FORWARD_ENABLE_VAT", False) or subtotal <= 0:
        return 0
    try:
        from payment.services.tax_calculator import calculate_vat
        return int(calculate_vat(subtotal))
    except Exception:
        return int(round(subtotal * 0.10))


@transaction.atomic
def claim_free_gift_tokens(user, plan: Optional[ForwardSubscriptionPlan] = None) -> int:
    """اعطای یک‌بارمصرف هدیه ۳۵۰ توکن رایگان با کلیک کاربر."""
    acc_obj = account_for(user)
    acc = ForwardSubscriptionAccount.objects.select_for_update().get(pk=acc_obj.pk)
    if not acc.can_use_trial:
        raise ValidationError("شما قبلاً هدیه توکن رایگان اولیه خود را دریافت کرده‌اید.")

    cfg = get_pricing_config()
    gift_tokens = int((plan.tokens_amount if plan and plan.tokens_amount else 0) or cfg.free_gift_tokens or 350)
    now = timezone.now()

    acc.token_balance = int(acc.token_balance) + gift_tokens
    acc.total_tokens_earned = int(acc.total_tokens_earned) + gift_tokens
    acc.trial_used_at = now
    acc.save(update_fields=["token_balance", "total_tokens_earned", "trial_used_at"])

    ForwardTokenTransaction.objects.create(
        user=user,
        tx_type=ForwardTokenTransaction.TxType.GIFT,
        amount=gift_tokens,
        balance_after=acc.token_balance,
        description=f"دریافت هدیه شروع رایگان ({gift_tokens:,} توکن)",
    )
    return gift_tokens


@transaction.atomic
def create_token_order_with_invoice(user, plan: ForwardSubscriptionPlan):
    """ثبت سفارش خرید بسته توکن و صدور فاکتور متناظر در اپ payment (سازگار با کیف پول و زرین‌پال)."""
    from payment.models import Invoice

    if plan.is_trial or plan.price_per_platform <= 0 or plan.tokens_amount <= 0:
        raise ValidationError("این بسته برای خرید پولی معتبر نیست.")

    subtotal = int(plan.price_per_platform)
    tokens_qty = int(plan.tokens_amount)
    base_cost = max(subtotal, tokens_qty * 50) if int(plan.discount_percent or 0) > 0 else subtotal
    plan_discount = max(0, base_cost - subtotal)
    vat = _calculate_vat(subtotal)
    total = subtotal + vat

    order = ForwardSubscriptionOrder.objects.create(
        user=user,
        plan=plan,
        order_kind=ForwardSubscriptionOrder.OrderKind.NEW,
        platforms=list(FORWARD_PLATFORM_SLUGS),
        duration_days=0,
        tokens_amount=tokens_qty,
        price_per_platform=subtotal,
        subtotal_amount=subtotal,
        vat_amount=vat,
        total_amount=total,
        status=ForwardSubscriptionOrder.Status.PENDING,
    )

    invoice = Invoice.objects.create(
        type=Invoice.Type.WINFORWARD,
        user=user,
        forward_subscription_order=order,
        base_plan_cost=base_cost,
        plan_discount_amount=plan_discount,
        plan_cost=subtotal,
        plan_vat=vat,
        discount_amount=plan_discount,
        total_amount=base_cost,
        total_vat=vat,
        payable_amount=total,
        base_commission=subtotal,
        commission=subtotal,
        description=f"خرید {plan.name} وین فوروارد ({tokens_qty:,} توکن · بدون تاریخ انقضا)",
    )
    invoice.invoice_number = Invoice.generate_invoice_number(
        invoice.pk, invoice.created_at, Invoice.Type.WINFORWARD
    )
    invoice.save(update_fields=["invoice_number"])
    return order, invoice


@transaction.atomic
def fulfil_forward_order(order: ForwardSubscriptionOrder) -> None:
    """اعمال و شارژ توکن‌های خریداری‌شده بلافاصله پس از پرداخت موفق از کیف پول یا درگاه زرین‌پال."""
    if order.status == ForwardSubscriptionOrder.Status.PAID:
        return

    now = timezone.now()
    tokens_to_add = int(order.tokens_amount or (order.plan.tokens_amount if order.plan else 0))
    acc_obj = account_for(order.user)
    acc = ForwardSubscriptionAccount.objects.select_for_update().get(pk=acc_obj.pk)

    if tokens_to_add > 0:
        acc.token_balance = int(acc.token_balance) + tokens_to_add
        acc.total_tokens_earned = int(acc.total_tokens_earned) + tokens_to_add
        if not acc.first_paid_at:
            acc.first_paid_at = now
        acc.save(update_fields=["token_balance", "total_tokens_earned", "first_paid_at"])

        ForwardTokenTransaction.objects.create(
            user=order.user,
            tx_type=ForwardTokenTransaction.TxType.PURCHASE,
            amount=tokens_to_add,
            balance_after=acc.token_balance,
            description=f"شارژ {tokens_to_add:,} توکن از {order.plan.name} (سفارش #{order.pk})",
        )

    order.status = ForwardSubscriptionOrder.Status.PAID
    order.paid_at = now
    order.save(update_fields=["status", "paid_at"])


@transaction.atomic
def cancel_pending_token_order(order: ForwardSubscriptionOrder, user) -> ForwardSubscriptionOrder:
    """لغو سفارش پرداخت‌نشده خرید بسته توکن توسط مالک سفارش."""
    from payment.models import Invoice, Payment

    order = ForwardSubscriptionOrder.objects.select_for_update().get(pk=order.pk, user=user)
    if order.status != ForwardSubscriptionOrder.Status.PENDING:
        raise ValidationError("فقط سفارش‌های در انتظار پرداخت قابل لغو هستند.")

    invoice = Invoice.objects.filter(forward_subscription_order=order).first()
    if invoice and invoice.is_paid:
        raise ValidationError("این فاکتور قبلاً پرداخت شده است و قابل لغو نیست.")
    if invoice and invoice.payments.filter(status=Payment.Status.PENDING).exists():
        invoice.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.FAILED)

    order.status = ForwardSubscriptionOrder.Status.CANCELED
    order.save(update_fields=["status"])
    return order
