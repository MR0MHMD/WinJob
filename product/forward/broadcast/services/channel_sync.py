"""سرویس همگام‌سازی کانال و تأیید مالکیت با Deep Link (بدون کد تأیید)."""

import uuid
from django.db import IntegrityError
from django.utils import timezone
from product.forward.broadcast.models import BroadcastChannel
from product.forward.messengers.adapters.base import MessengerError
from product.forward.messengers.adapters.registry import get_adapter


DEEP_LINK_PATTERNS = {
    "bale": "https://ble.ir/{bot}?start={payload}",
    "telegram": "https://t.me/{bot}?start={payload}",
    "rubika": "https://rubika.ir/{bot}?start={payload}",
}


def generate_verification_token(channel) -> str:
    """تولید توکن یک بار مصرف ۱۲ کاراکتری و ذخیره در کانال."""
    token = uuid.uuid4().hex[:12]
    channel.verification_token = token
    channel.verification_token_created_at = timezone.now()
    channel.verification_token_used_at = None
    channel.save(update_fields=["verification_token", "verification_token_created_at", "verification_token_used_at"])
    return token


def build_deep_link(channel, bot_username: str = "") -> str:
    """ساخت لینک Deep Link برای شروع فرآیند تأیید مالکیت."""
    slug = channel.platform.slug
    pattern = DEEP_LINK_PATTERNS.get(slug)
    if not pattern:
        raise ValueError(f"پلتفرم {slug} از Deep Link پشتیبانی نمی‌کند.")
    if not channel.verification_token:
        raise ValueError("کانال توکن تأیید ندارد — ابتدا generate_verification_token صدا زده شود.")
    if not bot_username:
        adapter = get_adapter(slug)
        if not adapter:
            raise MessengerError(f"آداپتور {slug} ثبت نشده است.")
        bot_username = adapter.get_bot_username()
    payload = f"verify_{channel.verification_token}"
    return pattern.format(bot=bot_username, payload=payload)


def verify_bot_admin(channel) -> bool:
    """بررسی ادمین بودن ربات در کانال و بروزرسانی فیلدهای مربوطه."""
    adapter = get_adapter(channel.platform.slug)
    if not adapter:
        raise MessengerError(f"آداپتور {channel.platform.slug} ثبت نشده است.")
    try:
        is_admin = adapter.check_bot_is_admin(channel.chat_id)
    except MessengerError:
        channel.bot_is_admin = False
        channel.bot_admin_checked_at = timezone.now()
        channel.save(update_fields=["bot_is_admin", "bot_admin_checked_at"])
        raise
    channel.bot_is_admin = is_admin
    channel.bot_admin_checked_at = timezone.now()
    channel.save(update_fields=["bot_is_admin", "bot_admin_checked_at"])
    return is_admin


def finalize_verification(token: str, platform_slug: str, bot_chat_id: str = "") -> dict:
    """نهایی‌سازی پس از دریافت /start verify_<token> از سمت ربات."""
    result = {"ok": False, "channel": None, "error": None, "detail": None}
    if not token:
        result["error"] = "missing_token"
        return result
    channel = (
        BroadcastChannel.objects
        .filter(verification_token=token, platform__slug=platform_slug, verification_token_used_at__isnull=True)
        .select_related("user", "platform")
        .first()
    )
    if not channel:
        result["error"] = "invalid_or_used_token"
        return result
    if not channel.is_token_valid():
        result["error"] = "expired_token"
        return result
    try:
        is_admin = verify_bot_admin(channel)
    except MessengerError as e:
        result["error"] = "api_error"
        result["detail"] = str(e)
        return result
    if not is_admin:
        result["error"] = "bot_not_admin"
        return result
    channel.mark_verified()
    result["ok"] = True
    result["channel"] = channel
    if bot_chat_id:
        _link_bot_user_silently(channel.user, channel.platform, bot_chat_id)
    return result


def _link_bot_user_silently(user, platform, chat_id: str) -> None:
    """اتصال بی‌صدا BotUser پس از تأیید موفق (بدون خطا در صورت تداخل)."""
    from product.forward.messengers.models import BotUser
    try:
        BotUser.objects.get_or_create(user=user, platform=platform, defaults={"chat_id": str(chat_id), "is_verified": True})
    except IntegrityError:
        pass
