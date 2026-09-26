"""Helpers for Zarinpal live-domain flow and local sandbox development."""

from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse


ALLOWED_ZARINPAL_HOSTS = {
    "payment.zarinpal.com",
    "sandbox.zarinpal.com",
}


def _zarinpal_sandbox_enabled() -> bool:
    """Read the effective sandbox flag from IRANIAN_PAYMENT settings."""
    payment_settings = getattr(settings, "IRANIAN_PAYMENT", {}) or {}
    gateway_settings = (payment_settings.get("gateways", {}) or {}).get("zarinpal", {}) or {}
    return bool(gateway_settings.get("sandbox", payment_settings.get("sandbox", False)))


def _local_base_url() -> str:
    """
    Base URL used only for sandbox callbacks.

    Prefer BASE_URL from .env/settings so custom localhost ports keep working.
    Fall back to Django's usual local development address.
    """
    base = (getattr(settings, "BASE_URL", "") or "").strip().rstrip("/")
    return base or "http://127.0.0.1:8000"


def site_url(path: str) -> str:
    """Build an absolute URL on the exact canonical domain registered at Zarinpal."""
    base = (getattr(settings, "SITE_URL", "") or "").strip().rstrip("/")
    if not base:
        raise ImproperlyConfigured(
            "SITE_URL must be set to the exact domain registered for the Zarinpal gateway."
        )

    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ImproperlyConfigured(
            "SITE_URL must be an absolute HTTPS URL, e.g. https://winjob.ir"
        )

    return urljoin(base + "/", path.lstrip("/"))


def callback_url(route_name: str) -> str:
    """
    Use a localhost callback for sandbox and SITE_URL for live payments.

    This keeps the existing call sites unchanged.
    """
    if _zarinpal_sandbox_enabled():
        return urljoin(_local_base_url() + "/", reverse(route_name).lstrip("/"))
    return site_url(reverse(route_name))


def prepare_gateway_bridge(request, gateway_url: str) -> str:
    """
    Sandbox: go straight to sandbox StartPay.
    Live: keep the same-domain bridge required for Zarinpal domain matching.
    """
    parsed = urlparse(gateway_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_ZARINPAL_HOSTS:
        raise ValueError("Unexpected Zarinpal gateway URL")

    if parsed.hostname == "sandbox.zarinpal.com" or _zarinpal_sandbox_enabled():
        return gateway_url

    request.session["zarinpal_gateway_redirect_url"] = gateway_url
    request.session.modified = True
    return site_url(reverse("payment:zarinpal_gateway_bridge"))


def pop_gateway_url(request):
    """Consume the one-time StartPay URL used by the bridge."""
    return request.session.pop("zarinpal_gateway_redirect_url", None)


def is_allowed_gateway_url(url: str) -> bool:
    parsed = urlparse(url or "")
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_ZARINPAL_HOSTS


__all__ = ["callback_url", "prepare_gateway_bridge", "pop_gateway_url", "is_allowed_gateway_url"]
