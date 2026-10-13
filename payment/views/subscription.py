"""بازگشت و بررسی مجدد درگاه اشتراک؛ فعال‌سازی وابسته به ورود مرورگر نیست."""

import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from payment.models import Payment
from payment.services.subscription_payment import verify_subscription_gateway

logger = logging.getLogger(__name__)


def subscription_callback(request):
    """شناسهٔ درگاه را با تأیید سرور بررسی می‌کند؛ وضعیت GET سند پرداخت نیست."""
    authority = request.GET.get("Authority", "")
    if not authority:
        messages.error(request, "شناسهٔ پرداخت در بازگشت از درگاه یافت نشد.")
        return redirect("windirect:subscription")

    payment = get_object_or_404(
        Payment,
        authority=authority,
        invoice__subscription_order__isnull=False,
    )
    if request.GET.get("Status") == "OK":
        try:
            verify_subscription_gateway(payment)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        except Exception:
            logger.exception("خطای تأیید پرداخت اشتراک %s", payment.pk)
            messages.error(
                request, "تأیید درگاه فعلاً ممکن نشد. از صفحهٔ سفارش دوباره بررسی کنید."
            )
    else:
        messages.warning(
            request,
            "پرداخت درگاه تأیید نشده است؛ در صورت کسر وجه امکان بررسی مجدد وجود دارد.",
        )
    return redirect("windirect:subscription_order", pk=payment.invoice.subscription_order_id)


@login_required(login_url="accounts:login")
@require_POST
def subscription_reverify(request, pk):
    """تلاش پرداخت مالک را بدون ایجاد سفارش یا هدیهٔ تکراری بررسی می‌کند."""
    payment = get_object_or_404(
        Payment,
        pk=pk,
        invoice__subscription_order__user=request.user,
        authority__isnull=False,
    )
    try:
        verify_subscription_gateway(payment)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    except Exception:
        logger.exception("خطای بررسی مجدد اشتراک %s", payment.pk)
        messages.error(request, "درگاه در دسترس نیست. دوباره تلاش کنید.")
    return redirect("windirect:subscription_order", pk=payment.invoice.subscription_order_id)
