from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from payment.services.zarinpal_flow import is_allowed_gateway_url, pop_gateway_url


@login_required
@never_cache
def zarinpal_gateway_bridge(request):
    """Same-domain browser hop before Zarinpal StartPay."""
    gateway_url = pop_gateway_url(request)
    if not gateway_url:
        return HttpResponseBadRequest("مسیر پرداخت منقضی یا نامعتبر است.")

    if not is_allowed_gateway_url(gateway_url):
        return HttpResponseBadRequest("نشانی درگاه پرداخت معتبر نیست.")

    response = render(
        request,
        "payment/gateway/zarinpal_bridge.html",
        {"gateway_url": gateway_url},
    )
    response["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response
