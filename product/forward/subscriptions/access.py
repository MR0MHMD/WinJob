"""توابع بررسی موجودی توکن و دسترسی یکپارچه وین فوروارد روی همه ۴ پلتفرم."""

from __future__ import annotations

from typing import Dict, Set

from .models import (
    FORWARD_PLATFORM_LABELS,
    FORWARD_PLATFORM_SLUGS,
    ForwardSubscriptionAccount,
)


def get_user_token_balance(user) -> int:
    """دریافت موجودی فعلی توکن کاربر در وین فوروارد."""
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    acc = ForwardSubscriptionAccount.objects.filter(user=user).only("token_balance").first()
    return int(acc.token_balance) if acc else 0


def has_enough_tokens(user, required_tokens: int = 2) -> bool:
    """بررسی کافی بودن موجودی توکن کاربر برای ارسال."""
    return get_user_token_balance(user) >= max(1, int(required_tokens))


def get_user_platform_access_map(user) -> Dict[str, dict]:
    """در سیستم توکنی، در صورت داشتن موجودی توکن، هر ۴ پلتفرم در دسترس هستند."""
    balance = get_user_token_balance(user)
    if balance <= 0:
        return {}
    return {
        slug: {"is_valid": True, "remaining_days": balance, "tokens": balance}
        for slug in FORWARD_PLATFORM_SLUGS
    }


def get_active_platform_slugs(user) -> Set[str]:
    """در سیستم توکنی، با داشتن حداقل ۲ توکن هر ۴ پلتفرم برای ارسال باز هستند."""
    if get_user_token_balance(user) >= 2:
        return set(FORWARD_PLATFORM_SLUGS)
    return set()


def user_has_platform_access(user, platform_slug: str = "") -> bool:
    """بررسی امکان ارسال پیام (داشتن حداقل ۲ توکن در کیف توکن کاربر)."""
    return get_user_token_balance(user) >= 2


def platform_label(platform_slug: str) -> str:
    """برگرداندن نام فارسی خوانای پلتفرم بر اساس slug."""
    return FORWARD_PLATFORM_LABELS.get(platform_slug, platform_slug)
