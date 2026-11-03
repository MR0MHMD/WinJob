"""تست‌های واحد سرویس همگام‌سازی کانال (channel_sync)."""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from accounts.models import CustomUser
from core.models import Platform
from product.forward.broadcast.models import BroadcastChannel
from product.forward.broadcast.services import channel_sync
from product.forward.messengers.adapters.base import MessengerAdapter
from product.forward.messengers.adapters.registry import register, unregister


class MockAdapter(MessengerAdapter):
    """آداپتور mock بله برای تست — بدون تماس با API واقعی."""

    platform_slug = "bale"

    def __init__(self, is_admin=True):
        """ذخیره تنظیمات قابل کنترل در تست."""
        self.is_admin = is_admin

    def send_text(self, chat_id, text):
        """بازگرداندن پاسخ ساختگی برای ارسال متن."""
        return {"message_id": "mock_text_1"}

    def send_photo(self, chat_id, photo, caption=""):
        """بازگرداندن پاسخ ساختگی برای ارسال عکس."""
        return {"message_id": "mock_photo_1"}

    def send_video(self, chat_id, video, caption=""):
        """بازگرداندن پاسخ ساختگی برای ارسال ویدیو."""
        return {"message_id": "mock_video_1"}

    def send_document(self, chat_id, document, caption=""):
        """بازگرداندن پاسخ ساختگی برای ارسال فایل."""
        return {"message_id": "mock_doc_1"}

    def check_bot_is_admin(self, chat_id):
        """بازگرداندن مقدار قابل تنظیم is_admin."""
        return self.is_admin

    def get_chat_info(self, chat_id):
        """بازگرداندن اطلاعات ساختگی کانال."""
        return {"title": "Mock", "username": "mock", "type": "channel"}

    def get_bot_username(self):
        """بازگرداندن نام کاربری ربات mock."""
        return "mock_bot"


class ChannelSyncBaseTestCase(TestCase):
    """تست پایه — ساخت داده‌های مشترک و ثبت MockAdapter."""

    def setUp(self):
        """ایجاد کاربر، پلتفرم بله، کانال و ثبت MockAdapter (با ذخیره آداپتور واقعی)."""
        from product.forward.messengers.adapters.registry import get_adapter_class
        self._saved_bale = get_adapter_class("bale")
        self.user = CustomUser(phone_number="09120000001", nickname="Tester")
        self.user.set_unusable_password()
        self.user.save()
        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Bale test", is_active=True)
        self.channel = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="@test_channel",
                                                       title="کانال تست")
        register(MockAdapter, slug="bale")

    def tearDown(self):
        """بازگرداندن آداپتور واقعی بله به رجیستری پس از پایان تست."""
        unregister("bale")
        if self._saved_bale is not None:
            register(self._saved_bale, slug="bale")


class GenerateTokenTests(ChannelSyncBaseTestCase):
    """تست‌های تولید توکن تأیید."""

    def test_generate_token_and_overwrite(self):
        """توکن جدید تولید می‌شود و فراخوانی دوم توکن قبلی را بازنویسی می‌کند."""
        token1 = channel_sync.generate_verification_token(self.channel)
        self.channel.refresh_from_db()
        self.assertEqual(len(token1), 12)
        self.assertEqual(self.channel.verification_token, token1)
        self.assertIsNotNone(self.channel.verification_token_created_at)
        self.assertIsNone(self.channel.verification_token_used_at)
        token2 = channel_sync.generate_verification_token(self.channel)
        self.assertNotEqual(token1, token2)


class BuildDeepLinkTests(ChannelSyncBaseTestCase):
    """تست‌های ساخت لینک Deep Link."""

    def test_bale_deep_link_success(self):
        """Deep Link بله با payload درست ساخته می‌شود."""
        channel_sync.generate_verification_token(self.channel)
        self.channel.refresh_from_db()
        link = channel_sync.build_deep_link(self.channel, bot_username="my_bot")
        self.assertEqual(link, f"https://ble.ir/my_bot?start=verify_{self.channel.verification_token}")

    def test_build_deep_link_failures(self):
        """پلتفرم ناشناخته و کانال بدون توکن هر دو ValueError می‌دهند."""
        self.platform.slug = "unknown_platform"
        self.platform.save()
        self.channel.refresh_from_db()
        with self.assertRaises(ValueError):
            channel_sync.build_deep_link(self.channel, bot_username="x")
        self.platform.slug = "bale"
        self.platform.save()
        self.channel.refresh_from_db()
        self.channel.verification_token = ""
        self.channel.save(update_fields=["verification_token"])
        with self.assertRaises(ValueError):
            channel_sync.build_deep_link(self.channel, bot_username="x")


class VerifyBotAdminTests(ChannelSyncBaseTestCase):
    """تست‌های بررسی ادمین بودن ربات."""

    def test_verify_bot_admin_true(self):
        """ربات ادمین است → True برمی‌گردد و فیلدها به‌روزرسانی می‌شوند."""
        result = channel_sync.verify_bot_admin(self.channel)
        self.assertTrue(result)
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.bot_is_admin)
        self.assertIsNotNone(self.channel.bot_admin_checked_at)

    def test_verify_bot_admin_false(self):
        """ربات ادمین نیست → False برمی‌گردد و فیلدها به‌روزرسانی می‌شوند."""
        unregister("bale")
        class NotAdminMock(MockAdapter):
            def __init__(self):
                super().__init__(is_admin=False)
        register(NotAdminMock, slug="bale")
        result = channel_sync.verify_bot_admin(self.channel)
        self.assertFalse(result)
        self.channel.refresh_from_db()
        self.assertFalse(self.channel.bot_is_admin)


class FinalizeVerificationTests(ChannelSyncBaseTestCase):
    """تست‌های نهایی‌سازی فرآیند تأیید مالکیت."""

    def test_finalize_success(self):
        """توکن معتبر + ربات ادمین → تأیید موفق."""
        token = channel_sync.generate_verification_token(self.channel)
        result = channel_sync.finalize_verification(token, "bale")
        self.assertTrue(result["ok"])
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.bot_is_admin)
        self.assertIsNotNone(self.channel.verification_token_used_at)

    def test_finalize_invalid_token(self):
        """توکن ناموجود → invalid_or_used_token."""
        result = channel_sync.finalize_verification("nonexistent", "bale")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_or_used_token")

    def test_finalize_expired_token(self):
        """توکن منقضی (بیش از ۱۰ دقیقه) → expired_token."""
        token = channel_sync.generate_verification_token(self.channel)
        self.channel.refresh_from_db()
        self.channel.verification_token_created_at = timezone.now() - timedelta(minutes=15)
        self.channel.save(update_fields=["verification_token_created_at"])
        result = channel_sync.finalize_verification(token, "bale")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "expired_token")

    def test_finalize_bot_not_admin(self):
        """توکن معتبر ولی ربات ادمین نیست → bot_not_admin."""
        unregister("bale")
        class NotAdminMock(MockAdapter):
            def __init__(self):
                super().__init__(is_admin=False)
        register(NotAdminMock, slug="bale")
        token = channel_sync.generate_verification_token(self.channel)
        result = channel_sync.finalize_verification(token, "bale")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bot_not_admin")


class EndToEndTests(ChannelSyncBaseTestCase):
    """تست‌های end-to-end زنجیره کامل تأیید مالکیت با آداپتور mock."""

    def test_e2e_full_verification_flow(self):
        """زنجیره کامل: توکن → دیپ‌لینک → نهایی‌سازی → BotUser ساخته می‌شود."""
        from product.forward.messengers.models import BotUser
        token = channel_sync.generate_verification_token(self.channel)
        self.channel.refresh_from_db()
        link = channel_sync.build_deep_link(self.channel, bot_username="mock_bot")
        self.assertIn(f"verify_{token}", link)
        result = channel_sync.finalize_verification(token, "bale", bot_chat_id="123456")
        self.assertTrue(result["ok"])
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.bot_is_admin)
        self.assertIsNotNone(self.channel.verification_token_used_at)
        bot_user = BotUser.objects.get(user=self.user, platform=self.platform)
        self.assertEqual(bot_user.chat_id, "123456")
        self.assertTrue(bot_user.is_verified)

    def test_e2e_without_bot_chat_id_skips_link(self):
        """نهایی‌سازی بدون bot_chat_id → BotUser ساخته نمی‌شود."""
        from product.forward.messengers.models import BotUser
        token = channel_sync.generate_verification_token(self.channel)
        before = BotUser.objects.count()
        result = channel_sync.finalize_verification(token, "bale")
        self.assertTrue(result["ok"])
        self.assertEqual(BotUser.objects.count(), before)

    def test_e2e_two_platforms(self):
        """دو کانال روی دو پلتفرم → هر دو تأیید و دو BotUser ساخته می‌شود."""
        from product.forward.messengers.models import BotUser
        register(MockAdapter, slug="telegram")
        self.addCleanup(unregister, "telegram")
        platform_tg = Platform.objects.create(name="Telegram", slug="telegram", description="TG test", is_active=True)
        channel_tg = BroadcastChannel.objects.create(user=self.user, platform=platform_tg, chat_id="@tg_channel", title="کانال تلگرام")
        token_bale = channel_sync.generate_verification_token(self.channel)
        token_tg = channel_sync.generate_verification_token(channel_tg)
        r1 = channel_sync.finalize_verification(token_bale, "bale", bot_chat_id="bale_111")
        r2 = channel_sync.finalize_verification(token_tg, "telegram", bot_chat_id="tg_222")
        self.assertTrue(r1["ok"])
        self.assertTrue(r2["ok"])
        self.assertEqual(BotUser.objects.filter(user=self.user).count(), 2)