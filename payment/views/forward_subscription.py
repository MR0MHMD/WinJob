"""ویوهای بازگشت و بررسی مجدد درگاه زرین‌پال برای اشتراک وین فوروارد."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from payment.models import Payment
from payment.services.forward_subscription_payment import verify_forward_subscription_gateway

logger = logging.getLogger(__name__)


def forward_subscription_callback(request):
    """کالبک بازگشت از درگاه زرین‌پال برای سفارش‌های اشتراک وین فوروارد.

    :param request: درخواست GET بازگشتی از درگاه زرین‌پال شامل Authority و Status.
    :return: ریدایرکت به صفحه جزئیات سفارش اشتراک وین فوروارد.
    """
    authority = request.GET.get("Authority", "")
    if not authority:
        messages.error(request, "شناسه پرداخت در بازگشت از درگاه یافت نشد.")
        return redirect("forward_subscriptions:plans")

    payment = get_object_or_404(
        Payment,
        authority=authority,
        invoice__forward_subscription_order__isnull=False,
    )

    if request.GET.get("Status") == "OK":
        try:
            verify_forward_subscription_gateway(payment)
            messages.success(request, "✅ پرداخت با موفقیت تایید و اشتراک وین فوروارد فعال شد.")
        except ValidationError as error:
            messages.error(request, error.messages[0])
        except Exception:
            logger.exception("خطای تایید پرداخت وین فوروارد %s", payment.pk)
            messages.error(request, "تایید درگاه فعلاً ممکن نشد. از صفحه سفارش دوباره بررسی کنید.")
    else:
        messages.warning(request, "پرداخت درگاه لغو یا ناموفق بود.")

    return redirect("forward_subscriptions:order_detail", order_id=payment.invoice.forward_subscription_order_id)


@login_required(login_url="accounts:login")
@require_POST
def forward_subscription_reverify(request, pk):
    """بررسی مجدد وضعیت پرداخت درگاه توسط مالک سفارش.

    :param request: درخواست POST کاربر لاگین‌شده.
    :param pk: شناسه رکورد Payment.
    :return: ریدایرکت به صفحه جزئیات سفارش.
    """
    payment = get_object_or_404(
        Payment,
        pk=pk,
        invoice__forward_subscription_order__user=request.user,
        authority__isnull=False,
    )
    try:
        verify_forward_subscription_gateway(payment)
        messages.success(request, "✅ پرداخت تایید و اشتراک وین فوروارد فعال شد.")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    except Exception:
        logger.exception("خطای بررسی مجدد پرداخت وین فوروارد %s", payment.pk)
        messages.error(request, "درگاه در دسترس نیست. لطفاً دوباره تلاش کنید.")

    return redirect("forward_subscriptions:order_detail", order_id=payment.invoice.forward_subscription_order_id)
