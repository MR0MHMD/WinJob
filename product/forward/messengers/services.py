"""سرویس‌های مربوط به اتصال کاربران سایت به ربات‌های پیام‌رسان."""

import uuid
from .models import ConnectToken


def generate_connect_link(user, platform_slug: str, bot_username: str = "win_forward_bot") -> str:
    """تولید توکن یک‌بارمصرف و ساخت لینک Deep Link برای اتصال به ربات."""
    if platform_slug in ("eitaa", "rubika"):
        raise ValueError(
            f"پلتفرم {platform_slug} از لینک اتصال (Deep Link) پشتیبانی نمی‌کند."
        )

    from core.models import Platform
    platform = Platform.objects.get(slug=platform_slug)

    # حذف توکن‌های قبلی استفاده‌نشده برای این پلتفرم
    ConnectToken.objects.filter(user=user, platform=platform, used_at__isnull=True).delete()

    token = uuid.uuid4().hex
    ConnectToken.objects.create(user=user, platform=platform, token=token)

    return f"https://ble.ir/{bot_username}?start=connect_{token}"
