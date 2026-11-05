"""سرویس‌های مربوط به اتصال کاربران سایت به ربات‌های پیام‌رسان."""

import uuid
from .models import ConnectToken


def generate_connect_link(user, platform_slug: str, bot_username: str = "win_forward_bot") -> str:
    """تولید توکن یک بار مصرف و ساخت لینک Deep Link برای اتصال به ربات."""
    from core.models import Platform
    platform = Platform.objects.get(slug=platform_slug)

    # حذف توکن‌های قبلی استفاده نشده برای این پلتفرم
    ConnectToken.objects.filter(user=user, platform=platform, used_at__isnull=True).delete()

    token = uuid.uuid4().hex
    ConnectToken.objects.create(user=user, platform=platform, token=token)

    return f"https://ble.ir/{bot_username}?start=connect_{token}"
