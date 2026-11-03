"""دستور تست اتصال به بله — بررسی واقعی آداپتور با API."""

from django.core.management.base import BaseCommand, CommandError
from product.forward.messengers.adapters.base import (
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from product.forward.messengers.adapters.registry import get_adapter


class Command(BaseCommand):
    """بررسی اتصال واقعی به بله: bot info، admin status، و ارسال تستی."""

    help = "تست اتصال واقعی به بله با آداپتور BaleAdapter"

    def add_arguments(self, parser):
        """افزودن آرگومان‌های خط فرمان."""
        parser.add_argument(
            "--chat-id",
            type=str,
            required=True,
            help="شناسه کانال تستی (مثلاً @my_test_channel)",
        )
        parser.add_argument(
            "--message",
            type=str,
            default="✅ تست اتصال وین فوروارد — این پیام خودکار ارسال شد.",
            help="متن پیام تستی (پیش‌فرض: پیام تستی استاندارد)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="فقط بررسی bot info و admin status بدون ارسال پیام",
        )

    def handle(self, *args, **options):
        """اجرای اصلی دستور با مدیریت خطا و عیب‌یابی خام."""
        import requests
        from django.conf import settings

        chat_id = options["chat_id"]
        message = options["message"]
        dry_run = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING("═══ تست اتصال بله ═══"))
        self.stdout.write(f"کانال هدف: {chat_id}")
        self.stdout.write(f"حالت: {'DRY-RUN (بدون ارسال)' if dry_run else 'ارسال واقعی'}")

        token = getattr(settings, "FORWARD_BALE_TOKEN", "")
        self.stdout.write(f"توکن در حال استفاده: {token[:10]}...{token[-4:] if len(token) > 14 else ''}")
        self.stdout.write("")

        self.stdout.write("[عیب‌یابی خام] بررسی مستقیم API بله...")
        try:
            # 1. تست getMe
            me_resp = requests.get(f"https://tapi.bale.ai/bot{token}/getMe").json()
            self.stdout.write(f"  → getMe: {me_resp}")
            bot_id = me_resp.get("result", {}).get("id")

            # 2. تست getChat
            chat_resp = requests.get(f"https://tapi.bale.ai/bot{token}/getChat", params={"chat_id": chat_id}).json()
            self.stdout.write(f"  → getChat: {chat_resp}")

            # 3. تست getChatMember
            if bot_id:
                member_resp = requests.get(
                    f"https://tapi.bale.ai/bot{token}/getChatMember",
                    params={"chat_id": chat_id, "user_id": bot_id}
                ).json()
                self.stdout.write(f"  → getChatMember: {member_resp}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  ⚠ خطا در بررسی خام: {e}"))
        self.stdout.write("")

        adapter = get_adapter("bale")
        if adapter is None:
            raise CommandError("آداپتور بله در رجیستری ثبت نشده است.")

        # مرحله ۱: get_me (حیاتی)
        try:
            self.stdout.write("[۱/۴] دریافت نام کاربری ربات...")
            bot_username = adapter.get_bot_username()
            self.stdout.write(self.style.SUCCESS(f"    ✓ نام کاربری: @{bot_username}"))
        except Exception as exc:
            raise CommandError(f"دریافت اطلاعات ربات شکست خورد: {exc}")
        self.stdout.write("")

        # مرحله ۲: check_bot_is_admin (حیاتی)
        self.stdout.write("[۲/۴] بررسی ادمین بودن ربات...")
        try:
            is_admin = adapter.check_bot_is_admin(chat_id)
            if is_admin:
                self.stdout.write(self.style.SUCCESS("    ✓ ربات ادمین است"))
            else:
                self.stdout.write(self.style.WARNING("    ⚠ ربات ادمین نیست — ارسال ممکن است شکست بخورد"))
        except MessengerNotFoundError as exc:
            raise CommandError(f"کانال یافت نشد یا ربات دسترسی ندارد: {exc}")
        except MessengerPermissionError as exc:
            raise CommandError(f"ربات دسترسی لازم را ندارد: {exc}")
        except Exception as exc:
            raise CommandError(f"بررسی ادمین شکست خورد: {exc}")
        self.stdout.write("")

        # مرحله ۳: get_chat_info (اختیاری)
        self.stdout.write("[۳/۴] دریافت اطلاعات کانال (اختیاری)...")
        try:
            chat_info = adapter.get_chat_info(chat_id)
            self.stdout.write(self.style.SUCCESS(f"    ✓ عنوان: {chat_info['title']}"))
            self.stdout.write(self.style.SUCCESS(f"    ✓ username: @{chat_info['username']}"))
            self.stdout.write(self.style.SUCCESS(f"    ✓ نوع: {chat_info['type']}"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"    ⚠ دریافت اطلاعات شکست خورد (ادامه می‌دهیم): {exc}"))
        self.stdout.write("")

        if dry_run:
            self.stdout.write(self.style.MIGRATE_HEADING("═══ DRY-RUN موفق — پیامی ارسال نشد ═══"))
            return

        # مرحله ۴: send_text (حیاتی)
        self.stdout.write("[۴/۴] ارسال پیام تستی...")
        try:
            result = adapter.send_text(chat_id, message)
            self.stdout.write(self.style.SUCCESS(f"    ✓ ارسال موفق — message_id: {result['message_id']}"))
        except MessengerPermissionError as exc:
            raise CommandError(f"ربات اجازه ارسال ندارد: {exc}")
        except MessengerNotFoundError as exc:
            raise CommandError(f"کانال یافت نشد: {exc}")
        except MessengerRateLimitError as exc:
            raise CommandError(f"محدودیت نرخ — {exc.retry_after} ثانیه صبر کنید: {exc}")
        except MessengerAPIError as exc:
            raise CommandError(f"خطای API بله: {exc}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("═══ تست کامل موفق ═══"))
