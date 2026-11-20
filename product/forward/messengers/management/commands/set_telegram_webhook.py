"""دستور مدیریتی برای تنظیم وب‌هوک پروداکشن ربات تلگرام وین فوروارد."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from product.forward.messengers.telegram_proxy import ensure_telegram_proxy, get_telegram_proxies


class Command(BaseCommand):
    """ثبت آدرس وب‌هوک رسمی وین‌فوروارد در تلگرام با تمام آپدیت‌های لازم (message, callback_query, my_chat_member)."""

    help = "تنظیم وب‌هوک رسمی ربات تلگرام روی سرور وین فوروارد"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="https://winjob.ir/webhooks/telegram/",
            help="آدرس HTTPS وب‌هوک (پیش‌فرض: https://winjob.ir/webhooks/telegram/)",
        )
        parser.add_argument("--info", action="store_true", help="نمایش وضعیت فعلی getWebhookInfo")

    def handle(self, *args, **options):
        token = getattr(settings, "FORWARD_TELEGRAM_TOKEN", "").strip()
        if not token:
            raise CommandError("متغیر FORWARD_TELEGRAM_TOKEN در settings.py تنظیم نشده است.")

        webhook_url = options["url"].strip()
        base_url = f"https://api.telegram.org/bot{token}"

        if not ensure_telegram_proxy():
            raise CommandError("پروکسی تلگرام در دسترس نیست.")

        session = requests.Session()
        retry_cfg = Retry(total=3, backoff_factor=1.0, allowed_methods=["GET", "POST"])
        session.mount("https://", HTTPAdapter(max_retries=retry_cfg))
        proxies = get_telegram_proxies()
        if proxies:
            session.proxies.update(proxies)

        if not options.get("info"):
            resp = session.post(
                f"{base_url}/setWebhook",
                json={
                    "url": webhook_url,
                    "allowed_updates": ["message", "callback_query", "channel_post", "my_chat_member"],
                    "drop_pending_updates": True,
                },
                timeout=20,
            ).json()
            if not resp.get("ok"):
                raise CommandError(f"خطا در setWebhook: {resp}")
            self.stdout.write(self.style.SUCCESS(f"✅ وب‌هوک پروداکشن تلگرام تنظیم شد: {webhook_url}"))

        info = session.get(f"{base_url}/getWebhookInfo", timeout=20).json()
        self.stdout.write(f"getWebhookInfo: {info}")
