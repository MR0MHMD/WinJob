"""توابع بررسی دسترسی اشتراک وین فوروارد برای هر کاربر و پلتفرم."""

from __future__ import annotations

from typing import Dict, Set

from django.utils import timezone

from .models import FORWARD_PLATFORM_LABELS, ForwardPlatformAccess


def get_user_platform_access_map(user) -> Dict[str, ForwardPlatformAccess]:
    """دریافت دیکشنری دسترسی‌های معتبر (منقضی‌نشده) کاربر به تفکیک slug پلتفرم.

    :param user: نمونه کاربر سایت (CustomUser).
    :return: دیکشنری با کلید slug پلتفرم و مقدار آبجکت ForwardPlatformAccess.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    now = timezone.now()
    accesses = ForwardPlatformAccess.objects.filter(
        user=user,
        is_active=True,
        expires_at__gt=now,
    ).select_related("plan")
    return {acc.platform_slug: acc for acc in accesses}


def get_active_platform_slugs(user) -> Set[str]:
    """دریافت مجموعه slug پلتفرم‌هایی که کاربر در حال حاضر اشتراک فعال آن‌ها را دارد.

    :param user: نمونه کاربر سایت.
    :return: مجموعه (set) رشته‌های slug پلتفرم‌های فعال.
    """
    return set(get_user_platform_access_map(user).keys())


def user_has_platform_access(user, platform_slug: str) -> bool:
    """بررسی اینکه آیا کاربر برای پلتفرم مشخص‌شده اشتراک فعال دارد یا خیر.

    :param user: نمونه کاربر سایت.
    :param platform_slug: شناسه پلتفرم ('bale'، 'eitaa'، 'rubika'، 'soroush').
    :return: True در صورت داشتن اشتراک فعال، در غیر این صورت False.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    now = timezone.now()
    return ForwardPlatformAccess.objects.filter(
        user=user,
        platform_slug=platform_slug,
        is_active=True,
        expires_at__gt=now,
    ).exists()


def platform_label(platform_slug: str) -> str:
    """برگرداندن نام فارسی خوانای پلتفرم بر اساس slug.

    :param platform_slug: شناسه انگلیسی پلتفرم.
    :return: نام فارسی پلتفرم.
    """
    return FORWARD_PLATFORM_LABELS.get(platform_slug, platform_slug)
