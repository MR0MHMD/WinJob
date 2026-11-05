"""دستور ثبت آدرس Webhook در API بله."""

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """ثبت آدرس Webhook در بله با استفاده از متد setWebhook."""

    help = "ثبت آدرس Webhook در API بله"

    def add_arguments(self, parser):
        """افزودن آرگومان‌های خط فرمان."""
        parser.add_argument(
            "--url",
            type=str,
            required=True,
            help="آدرس عمومی ngrok (مثلاً https://xxxx.ngrok-free.app)",
        )

    def handle(self, *args, **options):
        """اجرای اصلی دستور برای ثبت Webhook."""
        url = options["url"]
        token = getattr(settings, "FORWARD_BALE_TOKEN", None)

        if not token:
            raise CommandError("توکن FORWARD_BALE_TOKEN در تنظیمات یافت نشد.")

        # مسیر دقیق ویو ما
        webhook_endpoint = f"{url}/webhooks/bale/"

        api_url = f"https://tapi.bale.ai/bot{token}/setWebhook"

        self.stdout.write(f"در حال ثبت Webhook در آدرس: {webhook_endpoint} ...")

        try:
            response = requests.post(api_url, json={"url": webhook_endpoint}, timeout=10)
            data = response.json()

            if data.get("ok"):
                self.stdout.write(self.style.SUCCESS("✅ Webhook با موفقیت در بله ثبت شد!"))
                self.stdout.write(f"Description: {data.get('description')}")
            else:
                raise CommandError(f"خطا از سمت بله: {data}")

        except requests.RequestException as e:
            raise CommandError(f"خطا در ارتباط با سرور بله: {e}")
