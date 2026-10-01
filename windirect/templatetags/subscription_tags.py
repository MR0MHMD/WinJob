"""نمایش وضعیت اشتراک بدون فعال‌سازی دوره یا تغییر داده."""

from django import template
from windirect.subscriptions.services import current_period

register = template.Library()


@register.simple_tag
def windirect_active_subscription(user):
    """دورهٔ جاری را برای اعلان مشترک بیس پنل برمی‌گرداند."""
    return current_period(user) if user.is_authenticated else None
