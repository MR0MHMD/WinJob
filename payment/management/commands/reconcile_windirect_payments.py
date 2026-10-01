"""بررسی تلاش‌های درگاه و تسویهٔ سهم‌های در انتظار؛ بدون اعطای تکراری."""

from django.core.management.base import BaseCommand
from django_iranian_payment.contrib.django.models import Payment as GatewayPayment
from payment.models import SubscriptionPaymentAttempt, Invoice
from payment.services.subscription_payment import (
    verify_subscription_gateway,
    settle_subscription_gateway,
)
from payment.services.payout import payout_commission, PayoutError


class Command(BaseCommand):
    help = "بررسی مجدد پرداخت‌های وین دایرکت و تسهیم‌های پرداخت‌نشده"

    def handle(self, *args, **options):
        """موفقیت تأییدشده یا خطای قابل پیگیری هر مورد را گزارش می‌کند."""
        completed = 0
        failed = 0
        for attempt in SubscriptionPaymentAttempt.objects.filter(
            verified_at__isnull=True
        ).select_related("payment"):
            record = (
                GatewayPayment.objects.filter(
                    gateway_slug="zarinpal", order_id=f"windirect-{attempt.pk}"
                )
                .order_by("-created_at")
                .first()
            )
            if not record or not record.authority:
                continue
            if not attempt.authority:
                attempt.authority = record.authority
                attempt.gateway_url = record.redirect_url
                attempt.save(update_fields=["authority", "gateway_url"])
            try:
                if str(record.status).lower() == "complete":
                    settle_subscription_gateway(attempt, record)
                elif str(record.status).lower() == "returned":
                    verify_subscription_gateway(attempt)
                else:
                    continue
                completed += 1
            except Exception:
                failed += 1
                self.stderr.write(f"تلاش #{attempt.pk} هنوز تعیین تکلیف نشده است.")
        for invoice in Invoice.objects.filter(
            type="windirect", is_paid=True, commission_paid_at__isnull=True
        ):
            try:
                payout_commission(invoice)
            except PayoutError as error:
                failed += 1
                self.stderr.write(f"تسهیم فاکتور #{invoice.pk}: {error}")
        self.stdout.write(
            f"{completed} تلاش تعیین تکلیف شد؛ {failed} مورد نیاز به بررسی دارد."
        )
