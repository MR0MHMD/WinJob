from payment.models import Invoice, Payment
from django.utils import timezone


def create_wallet_invoice(user, amount, description=None):
    """
    ساخت فاکتور برای شارژ کیف پول
    """
    invoice = Invoice.objects.create(
        type=Invoice.Type.WALLET,
        user=user,
        campaign=None,
        wallet_deposit_amount=amount,
        total_amount=amount,
        payable_amount=amount,
        description=description or f"شارژ کیف پول به مبلغ {amount:,} تومان",
        is_paid=False,
    )

    # تولید شماره فاکتور
    invoice.invoice_number = Invoice.generate_invoice_number(
        invoice.id,
        invoice.created_at,
        Invoice.Type.WALLET
    )
    invoice.save(update_fields=['invoice_number'])

    return invoice


def create_wallet_invoice_for_payment(user, amount, authority, description=None):
    """
    ساخت فاکتور برای پرداخت درگاه (قبل از رفتن به درگاه)
    """
    invoice = create_wallet_invoice(
        user=user,
        amount=amount,
        description=description or f"شارژ کیف پول از طریق زرین‌پال - مبلغ {amount:,} تومان"
    )

    # ثبت Payment با وضعیت PENDING
    payment = Payment.objects.create(
        user=user,
        invoice=invoice,
        amount=amount,
        payment_method=Payment.Method.GATEWAY,
        authority=authority,
        status=Payment.Status.PENDING,
    )

    return invoice, payment


def complete_wallet_payment(invoice, ref_id):
    """
    تکمیل پرداخت کیف پول بعد از تأیید درگاه
    """
    from django.db import transaction

    with transaction.atomic():
        # به‌روزرسانی فاکتور
        invoice.is_paid = True
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=['is_paid', 'paid_at'])

        # به‌روزرسانی پرداخت
        payment = invoice.payments.first()
        if payment:
            payment.status = Payment.Status.SUCCESS
            payment.ref_id = ref_id
            payment.save(update_fields=['status', 'ref_id'])

        # شارژ کیف پول
        wallet = invoice.user.wallet
        wallet.balance += invoice.wallet_deposit_amount
        wallet.save(update_fields=['balance'])

        # ثبت تراکنش
        from payment.models import Transaction
        Transaction.objects.create(
            user=invoice.user,
            amount=invoice.wallet_deposit_amount,
            type=Transaction.Type.DEPOSIT,
            status=Transaction.Status.SUCCESS,
            invoice=invoice,
            payment=payment,
            reference_id=ref_id,
            description=f"شارژ کیف پول از طریق زرین‌پال - کد پیگیری: {ref_id}"
        )

    return True