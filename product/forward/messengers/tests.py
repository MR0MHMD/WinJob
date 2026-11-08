"""تست‌های واحد آداپتور بله با mock کردن HTTP API."""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from accounts.models import CustomUser
from product.forward.messengers.adapters.base import (
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from product.forward.messengers.adapters.registry import get_adapter, get_registered_slugs
# اطمینان از ثبت آداپتور ایتا در رجیستری (اجرای @register)
from product.forward.messengers.adapters.eitaa import EitaaAdapter  # noqa: F401


def _make_response(ok: bool, result=None, error_code: int = 0, description: str = ""):
    """ساخت MagicMock پاسخ HTTP برای requests.get."""
    response = MagicMock()
    payload = {"ok": ok, "result": result}
    if not ok:
        payload = {"ok": False, "error_code": error_code, "description": description}
    response.json.return_value = payload
    return response


class BaleAdapterRegistrationTests(TestCase):
    """تست‌های ثبت و مقداردهی اولیه آداپتور بله."""

    @override_settings(FORWARD_BALE_TOKEN="test_token_12345")
    def test_adapter_registered_and_instantiable(self):
        """آداپتور بله در رجیستری ثبت شده و با توکن معتبر ساخته می‌شود."""
        self.assertIn("bale", get_registered_slugs())
        adapter = get_adapter("bale")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.platform_slug, "bale")

    @override_settings(FORWARD_BALE_TOKEN="")
    def test_missing_token_raises(self):
        """نبودن توکن تنظیمات باعث MessengerAPIError می‌شود."""
        from product.forward.messengers.adapters.bale import BaleAdapter
        with self.assertRaises(MessengerAPIError):
            BaleAdapter()


class BaleAdapterSendTests(TestCase):
    """تست‌های ارسال متن و مدیا."""

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    @patch("product.forward.messengers.adapters.bale.requests.get")
    def test_send_text_returns_message_id(self, mock_get):
        """send_text پیام ارسال می‌کند و message_id را برمی‌گرداند."""
        mock_get.return_value = _make_response(True, {"message_id": 98765})
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        result = adapter.send_text("@channel", "سلام")
        self.assertEqual(result, {"message_id": "98765"})
        args, kwargs = mock_get.call_args
        self.assertIn("sendMessage", args[0])
        self.assertEqual(kwargs["params"]["chat_id"], "@channel")
        self.assertEqual(kwargs["params"]["text"], "سلام")

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    @patch("product.forward.messengers.adapters.bale.requests.post")
    def test_send_media_dispatch_all_types(self, mock_post):
        """send_media برای هر نوع محتوا متد صحیح را صدا می‌زند (با mock کردن requests.post)."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_post.side_effect = [
            _make_response(True, {"message_id": 1}),
            _make_response(True, {"message_id": 2}),
            _make_response(True, {"message_id": 3}),
        ]
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()

        photo = SimpleUploadedFile("p.jpg", b"fake_photo", content_type="image/jpeg")
        video = SimpleUploadedFile("v.mp4", b"fake_video", content_type="video/mp4")
        doc = SimpleUploadedFile("d.pdf", b"fake_doc", content_type="application/pdf")

        self.assertEqual(adapter.send_media("@ch", "photo", photo, "cap")["message_id"], "1")
        self.assertEqual(adapter.send_media("@ch", "video", video, "cap")["message_id"], "2")
        self.assertEqual(adapter.send_media("@ch", "document", doc, "cap")["message_id"], "3")

        urls = [call[0][0] for call in mock_post.call_args_list]
        self.assertTrue(any("sendPhoto" in u for u in urls))
        self.assertTrue(any("sendVideo" in u for u in urls))
        self.assertTrue(any("sendDocument" in u for u in urls))

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    def test_send_media_unsupported_type_raises(self):
        """نوع محتوای ناشناخته باعث ValueError می‌شود."""
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        with self.assertRaises(ValueError):
            adapter.send_media("@ch", "audio", "a.mp3", "")


class BaleAdapterErrorMappingTests(TestCase):
    """تست‌های تبدیل خطاهای API بله به خطاهای معنادار."""

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    @patch("product.forward.messengers.adapters.bale.requests.get")
    def test_not_found_error_mapped(self, mock_get):
        """خطای chat not found به MessengerNotFoundError تبدیل می‌شود."""
        mock_get.return_value = _make_response(False, error_code=400, description="Bad Request: chat not found")
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        with self.assertRaises(MessengerNotFoundError):
            adapter.send_text("@nonexistent", "test")

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    @patch("product.forward.messengers.adapters.bale.requests.get")
    def test_permission_error_mapped(self, mock_get):
        """خطای not enough rights به MessengerPermissionError تبدیل می‌شود."""
        mock_get.return_value = _make_response(False, error_code=403, description="Forbidden: not enough rights")
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        with self.assertRaises(MessengerPermissionError):
            adapter.send_text("@channel", "test")

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    @patch("product.forward.messengers.adapters.bale.requests.get")
    def test_rate_limit_parses_retry_after(self, mock_get):
        """خطای 429 با retry_after پارس و در exception ذخیره می‌شود."""
        mock_get.return_value = _make_response(False, error_code=429, description="Too Many Requests: retry after 42")
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        with self.assertRaises(MessengerRateLimitError) as ctx:
            adapter.send_text("@channel", "test")
        self.assertEqual(ctx.exception.retry_after, 42)


class BaleAdapterInfoTests(TestCase):
    """تست‌های دریافت اطلاعات کانال و ربات."""

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    @patch("product.forward.messengers.adapters.bale.requests.get")
    def test_check_bot_is_admin_true_and_false(self, mock_get):
        """check_bot_is_admin وضعیت administrator را True و member را False می‌دهد."""
        mock_get.side_effect = [
            _make_response(True, {"id": 42, "username": "my_bot"}),
            _make_response(True, {"status": "administrator", "user": {"id": 42}}),
            _make_response(True, {"id": 42, "username": "my_bot"}),
            _make_response(True, {"status": "member", "user": {"id": 42}}),
        ]
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        self.assertTrue(adapter.check_bot_is_admin("@ch"))
        self.assertFalse(adapter.check_bot_is_admin("@ch"))

    @override_settings(FORWARD_BALE_TOKEN="test_token")
    @patch("product.forward.messengers.adapters.bale.requests.get")
    def test_get_bot_username_and_chat_info(self, mock_get):
        """get_bot_username و get_chat_info اطلاعات را صحیح برمی‌گردانند."""
        mock_get.side_effect = [
            _make_response(True, {"username": "win_forward_bot"}),
            _make_response(True, {"title": "کانال تست", "username": "test_ch", "type": "channel"}),
        ]
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        self.assertEqual(adapter.get_bot_username(), "win_forward_bot")
        info = adapter.get_chat_info("@test_ch")
        self.assertEqual(info["title"], "کانال تست")
        self.assertEqual(info["username"], "test_ch")
        self.assertEqual(info["type"], "channel")


class BaleWebhookTests(TestCase):
    """تست‌های Webhook ربات بله."""

    def setUp(self):
        """آماده‌سازی URL، Platform و mock کردن آداپتور."""
        from core.models import Platform
        from django.test import override_settings
        self.url = "/webhooks/bale/"
        self.platform = Platform.objects.create(
            name="Bale", slug="bale", description="Test", is_active=True,
        )
        self.override = override_settings(FORWARD_BALE_TOKEN="test_token")
        self.override.enable()

    def tearDown(self):
        """غیرفعال‌سازی override."""
        self.override.disable()

    def test_webhook_rejects_get(self):
        """درخواست GET باید 405 برگرداند."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_start_without_token_sends_welcome(self, mock_get_adapter):
        """دستور /start بدون توکن باید پیام خوش‌آمدگویی بفرستد."""
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        payload = {"message": {"text": "/start", "chat": {"id": 12345}}}
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        mock_adapter.send_text.assert_called_once()
        args, _ = mock_adapter.send_text.call_args
        self.assertIn("خوش آمدید", args[1])

    @patch("product.forward.messengers.webhooks.finalize_verification")
    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_start_with_token_success(self, mock_get_adapter, mock_finalize):
        """دستور /start با توکن معتبر باید finalize_verification را صدا بزند."""
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        # شبیه‌سازی موفقیت
        mock_channel = MagicMock()
        mock_channel.title = "کانال تست"
        mock_finalize.return_value = {"ok": True, "channel": mock_channel}

        payload = {"message": {"text": "/start verify_abc123", "chat": {"id": 12345}}}
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        mock_finalize.assert_called_once_with("abc123", "bale", "12345")
        mock_adapter.send_text.assert_called_once()
        args, _ = mock_adapter.send_text.call_args
        self.assertIn("با موفقیت", args[1])

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_bot_added_user_not_linked(self, mock_get_adapter):
        """کاربر ناشناخته ربات را اضافه می‌کند — ربات پیام راهنما می‌فرستد، کانال ساخته نمی‌شود."""
        from product.forward.broadcast.models import BroadcastChannel
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter
        before = BroadcastChannel.objects.count()

        # ساختار دقیقاً مطابق خروجی n8n
        payload = {
            "message": {
                "from": {"id": 99999},
                "chat": {"id": -100123, "type": "channel", "title": "کانال ناشناخته"},
                "new_chat_members": [{"id": 123456, "is_bot": True}]
            }
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BroadcastChannel.objects.count(), before)
        mock_adapter.send_text.assert_called_once()

    def test_bot_added_user_linked_creates_channel(self):
        """کاربر شناخته‌شده ربات را اضافه می‌کند — کانال به‌طور خودکار ساخته می‌شود."""
        from accounts.models import CustomUser
        from product.forward.broadcast.models import BroadcastChannel
        from product.forward.messengers.models import BotUser

        user = CustomUser(phone_number="09120000099", nickname="LinkedUser")
        user.set_unusable_password()
        user.save()
        BotUser.objects.create(user=user, platform=self.platform, chat_id="55555", is_verified=True)

        with patch("product.forward.messengers.webhooks.get_adapter") as mock_get:
            mock_adapter = MagicMock()
            mock_adapter.check_bot_is_admin.return_value = True
            mock_get.return_value = mock_adapter

            payload = {
                "message": {
                    "from": {"id": 55555},
                    "chat": {"id": -100999, "type": "channel", "title": "کانال تستی"},
                    "new_chat_members": [{"id": 123456, "is_bot": True}]
                }
            }
            response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        channel = BroadcastChannel.objects.get(chat_id="-100999")
        self.assertEqual(channel.user, user)
        self.assertTrue(channel.bot_is_admin)
        self.assertEqual(channel.title, "کانال تستی")

    def test_bot_removed_deactivates_channel(self):
        """حذف ربات از کانال — کانال غیرفعال می‌شود."""
        from accounts.models import CustomUser
        from product.forward.broadcast.models import BroadcastChannel

        user = CustomUser(phone_number="09120000088", nickname="RemovedUser")
        user.set_unusable_password()
        user.save()
        channel = BroadcastChannel.objects.create(
            user=user, platform=self.platform, chat_id="-100777", title="کانال حذف‌شدنی", bot_is_admin=True,
            is_active=True,
        )

        payload = {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": -100777, "type": "channel", "title": "کانال حذف‌شدنی"},
                "left_chat_member": {"id": 123456, "is_bot": True}
            }
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        channel.refresh_from_db()
        self.assertFalse(channel.is_active)
        self.assertFalse(channel.bot_is_admin)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_private_message_creates_draft_job(self, mock_get_adapter):
        """ارسال متن در چت خصوصی باید یک BroadcastJob در حالت DRAFT بسازد."""
        from product.forward.broadcast.models import BroadcastJob
        from product.forward.messengers.models import BotUser
        from accounts.models import CustomUser

        # کاربر و کانال
        user = CustomUser(phone_number="09001386427", nickname="BotUser")
        user.set_unusable_password()
        user.save()
        BotUser.objects.create(user=user, platform=self.platform, chat_id="55555", is_verified=True)

        from product.forward.broadcast.models import BroadcastChannel
        BroadcastChannel.objects.create(user=user, platform=self.platform, chat_id="-100", title="کانال تست",
                                        is_active=True, bot_is_admin=True)

        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        payload = {
            "message": {
                "text": "سلام از طریق ربات",
                "chat": {"id": 55555, "type": "private"},
                "from": {"id": 55555}
            }
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BroadcastJob.objects.count(), 1)
        job = BroadcastJob.objects.first()
        self.assertEqual(job.status, BroadcastJob.Status.DRAFT)
        self.assertEqual(job.message.text, "سلام از طریق ربات")
        mock_adapter.send_text.assert_called_once()
        args, kwargs = mock_adapter.send_text.call_args
        self.assertIn("inline_keyboard", kwargs.get("reply_markup", {}))


class ConnectTokenWebhookTests(TestCase):
    """تست‌های اتصال کاربر از طریق لینک Deep Link."""

    def setUp(self):
        """آماده‌سازی پلتفرم و URL."""
        from core.models import Platform
        self.url = "/webhooks/bale/"
        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)
        self.user = CustomUser(phone_number="09120000077", nickname="ConnectUser")
        self.user.set_unusable_password()
        self.user.save()

    def test_generate_connect_link(self):
        """تولید لینک اتصال باید توکن بسازد و لینک صحیح برگرداند."""
        from product.forward.messengers.services import generate_connect_link
        from product.forward.messengers.models import ConnectToken

        link = generate_connect_link(self.user, "bale")
        self.assertIn("https://ble.ir/win_forward_bot?start=connect_", link)
        self.assertEqual(ConnectToken.objects.count(), 1)

        token_obj = ConnectToken.objects.first()
        self.assertEqual(token_obj.user, self.user)
        self.assertTrue(token_obj.is_valid())

    def test_connect_user_success(self):
        """دریافت /start connect_<token> باید BotUser را بسازد و توکن را باطل کند."""
        from product.forward.messengers.models import ConnectToken, BotUser
        from django.utils import timezone

        token_obj = ConnectToken.objects.create(user=self.user, platform=self.platform, token="testtoken123")

        payload = {
            "message": {
                "text": "/start connect_testtoken123",
                "chat": {"id": 999888},
                "from": {"id": 999888, "username": "connect_user"}
            }
        }

        with patch("product.forward.messengers.webhooks.get_adapter") as mock_get:
            mock_adapter = MagicMock()
            mock_get.return_value = mock_adapter

            response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)

        # چک کردن BotUser
        bot_user = BotUser.objects.get(user=self.user, platform=self.platform)
        self.assertEqual(bot_user.chat_id, "999888")
        self.assertTrue(bot_user.is_verified)

        # چک کردن باطل شدن توکن
        token_obj.refresh_from_db()
        self.assertIsNotNone(token_obj.used_at)
        mock_adapter.send_text.assert_called_once()
        self.assertIn("با موفقیت", mock_adapter.send_text.call_args[0][1])

    def test_connect_user_invalid_token(self):
        """توکن نامعتبر نباید BotUser بسازد و باید پیام خطا بفرستد."""
        from product.forward.messengers.models import BotUser

        payload = {
            "message": {
                "text": "/start connect_invalidtoken",
                "chat": {"id": 999888},
                "from": {"id": 999888}
            }
        }

        with patch("product.forward.messengers.webhooks.get_adapter") as mock_get:
            mock_adapter = MagicMock()
            mock_get.return_value = mock_adapter

            response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BotUser.objects.count(), 0)
        mock_adapter.send_text.assert_called_once()
        self.assertIn("نامعتبر", mock_adapter.send_text.call_args[0][1])


class BotCommandsTests(TestCase):
    """تست‌های دستورات /status و /channels در ربات."""

    def setUp(self):
        """آماده‌سازی پلتفرم، کاربر و BotUser."""
        from core.models import Platform
        from product.forward.messengers.models import BotUser
        self.url = "/webhooks/bale/"
        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)
        self.user = CustomUser(phone_number="09120000066", nickname="CommandUser")
        self.user.set_unusable_password()
        self.user.save()
        self.bot_user = BotUser.objects.create(user=self.user, platform=self.platform, chat_id="777888",
                                               is_verified=True)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_status_command_connected(self, mock_get):
        """دستور /status برای کاربر متصل باید اطلاعات کاربر را برگرداند."""
        mock_adapter = MagicMock()
        mock_get.return_value = mock_adapter

        payload = {"message": {"text": "/status", "chat": {"id": 777888}}}
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        mock_adapter.send_text.assert_called_once()
        msg = mock_adapter.send_text.call_args[0][1]
        self.assertIn("وضعیت حساب شما", msg)
        self.assertIn("09120000066", msg)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_status_command_not_connected(self, mock_get):
        """دستور /status برای کاربر ناشناس باید پیام خطا بدهد."""
        mock_adapter = MagicMock()
        mock_get.return_value = mock_adapter

        # چت آیدی که BotUser ندارد
        payload = {"message": {"text": "/status", "chat": {"id": 111222}}}
        response = self.client.post(self.url, data=payload, content_type="application/json")

        mock_adapter.send_text.assert_called_once()
        msg = mock_adapter.send_text.call_args[0][1]
        self.assertIn("حساب بله شما به سایت متصل نیست", msg)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_channels_command_with_channels(self, mock_get):
        """دستور /channels باید کانال‌های کاربر را به شکل دکمه‌های شیشه‌ای نشان دهد."""
        from product.forward.broadcast.models import BroadcastChannel
        mock_adapter = MagicMock()
        mock_get.return_value = mock_adapter

        # ساخت دو کانال تستی برای این کاربر
        BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-1", title="کانال اول",
                                        bot_is_admin=True, is_active=True)
        BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-2", title="کانال دوم",
                                        bot_is_admin=False, is_active=True)

        payload = {"message": {"text": "/channels", "chat": {"id": 777888}}}
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        mock_adapter.send_text.assert_called_once()

        args, kwargs = mock_adapter.send_text.call_args
        msg = args[1]

        # چک کردن پیام اصلی
        self.assertIn("لطفاً یک کانال", msg)

        # چک کردن کیبورد شیشه‌ای
        reply_markup = kwargs.get("reply_markup")
        self.assertIsNotNone(reply_markup, "reply_markup باید ارسال شود")
        self.assertIn("inline_keyboard", reply_markup)

        buttons = reply_markup["inline_keyboard"]
        self.assertEqual(len(buttons), 2, "باید دو ردیف دکمه باشد (یکی برای هر کانال)")

        button_texts = [b[0]["text"] for b in buttons]
        self.assertTrue(any("کانال اول" in t for t in button_texts))
        self.assertTrue(any("کانال دوم" in t for t in button_texts))
        self.assertTrue(any("✅" in t for t in button_texts), "کانال ادمین‌شده باید ✅ داشته باشد")
        self.assertTrue(any("⚠️" in t for t in button_texts), "کانال غیرادمین باید ⚠️ داشته باشد")

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_status_command_works_in_private_chat(self, mock_get):
        """/status در چت خصوصی (type=private) باید پاسخ بده — رفع باگ."""
        mock_adapter = MagicMock()
        mock_get.return_value = mock_adapter

        payload = {"message": {"text": "/status", "chat": {"id": 777888, "type": "private"}}}
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        mock_adapter.send_text.assert_called_once()
        msg = mock_adapter.send_text.call_args[0][1]
        self.assertIn("وضعیت حساب شما", msg)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_channels_command_works_in_private_chat(self, mock_get):
        """/channels در چت خصوصی (type=private) باید پاسخ بده — رفع باگ."""
        from product.forward.broadcast.models import BroadcastChannel
        mock_adapter = MagicMock()
        mock_get.return_value = mock_adapter

        BroadcastChannel.objects.create(
            user=self.user, platform=self.platform, chat_id="-1", title="کانال تست",
            bot_is_admin=True, is_active=True,
        )

        payload = {"message": {"text": "/channels", "chat": {"id": 777888, "type": "private"}}}
        response = self.client.post(self.url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        mock_adapter.send_text.assert_called_once()
        msg = mock_adapter.send_text.call_args[0][1]
        self.assertIn("لطفاً یک کانال", msg)


class InlineKeyboardTests(TestCase):
    """تست‌های دکمه‌های شیشه‌ای و Callback Query."""

    def setUp(self):
        """آماده‌سازی داده‌ها."""
        from core.models import Platform
        from product.forward.messengers.models import BotUser
        from product.forward.broadcast.models import BroadcastChannel
        self.url = "/webhooks/bale/"
        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)
        self.user = CustomUser(phone_number="09120000055", nickname="KeyboardUser")
        self.user.set_unusable_password()
        self.user.save()
        BotUser.objects.create(user=self.user, platform=self.platform, chat_id="123123", is_verified=True)
        self.channel = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-100",
                                                       title="کانال کیبورد", is_active=True)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_callback_channel_details(self, mock_get):
        """کلیک روی کانال باید صفحه مدیریت کانال را باز کند."""
        mock_adapter = MagicMock()
        mock_get.return_value = mock_adapter

        payload = {
            "callback_query": {
                "data": f"ch_{self.channel.pk}",
                "message": {"chat": {"id": 123123}}
            }
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        mock_adapter.send_text.assert_called_once()
        args, kwargs = mock_adapter.send_text.call_args
        self.assertIn("کانال کیبورد", args[1])
        self.assertIn("reply_markup", kwargs)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_callback_delete_channel(self, mock_get):
        """کلیک روی دکمه حذف باید کانال را غیرفعال کند."""
        mock_adapter = MagicMock()
        mock_get.return_value = mock_adapter

        payload = {
            "callback_query": {
                "data": f"delete_{self.channel.pk}",
                "message": {"chat": {"id": 123123}}
            }
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.channel.refresh_from_db()
        self.assertFalse(self.channel.is_active)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_callback_refresh_channel(self, mock_get):
        """کلیک روی دکمه بروزرسانی باید وضعیت ادمین را چک کند."""
        mock_adapter = MagicMock()
        mock_adapter.check_bot_is_admin.return_value = True
        mock_get.return_value = mock_adapter

        # ذخیره وضعیت اولیه کانال (در حالت تست false است)
        self.channel.bot_is_admin = False
        self.channel.save()

        payload = {
            "callback_query": {
                "data": f"refresh_{self.channel.pk}",
                "message": {"chat": {"id": 123123}}
            }
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.bot_is_admin)


class BotSendFlowTests(TestCase):
    """تست‌های فرآیند ارسال پیام از طریق ربات (انتخاب کانال و تایید)."""

    def setUp(self):
        from accounts.models import CustomUser
        from core.models import Platform
        from product.forward.messengers.models import BotUser
        from product.forward.broadcast.models import BroadcastChannel, BroadcastMessage, BroadcastJob
        from django.core.files.uploadedfile import SimpleUploadedFile  # 🔑 اضافه شد

        self.url = "/webhooks/bale/"
        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)
        self.platform.logo = SimpleUploadedFile("logo.png", b"fake", content_type="image/png")  # 🔑 اضافه شد
        self.platform.save()

        self.user = CustomUser(phone_number="09001386427", nickname="BotSender")
        self.user.set_unusable_password()
        self.user.save()
        BotUser.objects.create(user=self.user, platform=self.platform, chat_id="777777", is_verified=True)

        self.ch1 = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-1",
                                                   title="کانال ۱", bot_is_admin=True)
        self.ch2 = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-2",
                                                   title="کانال ۲", bot_is_admin=True)

        # ساخت یک پیش‌نویس اولیه
        msg = BroadcastMessage.objects.create(user=self.user, content_type="text", text="پیام تست")
        self.job = BroadcastJob.objects.create(message=msg, status=BroadcastJob.Status.DRAFT)

    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_select_channel_callback(self, mock_get_adapter):
        """کلیک روی کانال باید Target را بسازد/حذف کند."""
        from product.forward.broadcast.models import BroadcastTarget
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        payload = {
            "callback_query": {
                "data": f"sel_{self.job.pk}_{self.ch1.pk}",
                "message": {"chat": {"id": 777777}, "message_id": 100}
            }
        }

        # کلیک اول: انتخاب
        self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(BroadcastTarget.objects.count(), 1)

        # کلیک دوم: لغو انتخاب
        self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(BroadcastTarget.objects.count(), 0)

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_send_job_callback_without_targets(self, mock_webhook_adapter, mock_dispatch_adapter):
        """کلیک روی ارسال بدون انتخاب کانال باید پیام خطا بدهد."""
        mock_w_adapter = MagicMock()
        mock_webhook_adapter.return_value = mock_w_adapter

        payload = {
            "callback_query": {
                "data": f"send_{self.job.pk}",
                "message": {"chat": {"id": 777777}}
            }
        }
        self.client.post(self.url, data=payload, content_type="application/json")

        mock_w_adapter.send_text.assert_called_once()
        self.assertIn("حداقل یک کانال", mock_w_adapter.send_text.call_args[0][1])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, self.job.Status.DRAFT)  # هنوز ارسال نشده

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    @patch("product.forward.messengers.webhooks.get_adapter")
    def test_send_job_callback_success(self, mock_webhook_adapter, mock_dispatch_adapter):
        """کلیک روی ارسال با کانال انتخاب‌شده باید دیسپچر را صدا بزند."""
        from product.forward.broadcast.models import BroadcastTarget
        BroadcastTarget.objects.create(job=self.job, channel=self.ch1)  # شبیه‌سازی انتخاب

        mock_w_adapter = MagicMock()
        mock_webhook_adapter.return_value = mock_w_adapter
        mock_d_adapter = MagicMock()
        mock_d_adapter.send_text.return_value = {"message_id": "123"}
        mock_dispatch_adapter.return_value = mock_d_adapter

        payload = {
            "callback_query": {
                "data": f"send_{self.job.pk}",
                "message": {"chat": {"id": 777777}}
            }
        }
        self.client.post(self.url, data=payload, content_type="application/json")

        self.job.refresh_from_db()
        # چون dispatch_job اجرا شده، وضعیت از DRAFT به DONE تغییر می‌کنه
        self.assertEqual(self.job.status, self.job.Status.DONE)
        self.assertEqual(self.job.success_count, 1)
        self.assertIn("پردازش شد", mock_w_adapter.send_text.call_args[0][1])


# ============================================================
# Eitaa Adapter Tests
# ============================================================


def _make_eitaa_response(ok: bool, result=None, description: str = ""):
    """ساخت MagicMock پاسخ HTTP برای requests.post (ایتا)."""
    response = MagicMock()
    payload = {"ok": ok, "result": result}
    if not ok:
        payload["description"] = description
    response.json.return_value = payload
    return response


class EitaaAdapterRegistrationTests(TestCase):
    """تست‌های ثبت و مقداردهی اولیه آداپتور ایتا."""

    @override_settings(EITAA_BOT_TOKEN="test_token_12345")
    def test_adapter_registered_and_instantiable(self):
        """آداپتور ایتا در رجیستری ثبت شده و با توکن معتبر ساخته می‌شود."""
        self.assertIn("eitaa", get_registered_slugs())
        adapter = get_adapter("eitaa")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.platform_slug, "eitaa")

    @override_settings(EITAA_BOT_TOKEN="")
    def test_missing_token_raises(self):
        """نبودن توکن تنظیمات باعث MessengerAPIError می‌شود."""
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        with self.assertRaises(MessengerAPIError):
            EitaaAdapter()


class EitaaAdapterSendTests(TestCase):
    """تست‌های ارسال متن و مدیا در ایتا."""

    @patch("product.forward.messengers.adapters.eitaa.requests.post")
    def test_send_text_returns_message_id(self, mock_post):
        """send_text پیام ارسال می‌کند و message_id را برمی‌گرداند."""
        mock_post.return_value = _make_eitaa_response(True, {"message_id": 98765})
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")
        result = adapter.send_text("1404", "سلام ایتا")
        self.assertEqual(result["message_id"], "98765")
        args, kwargs = mock_post.call_args
        self.assertIn("sendMessage", args[0])
        self.assertEqual(kwargs["json"]["chat_id"], "1404")
        self.assertEqual(kwargs["json"]["text"], "سلام ایتا")

    @patch("product.forward.messengers.adapters.eitaa.requests.post")
    def test_send_media_dispatch_all_types(self, mock_post):
        """send_media برای هر نوع محتوا متد صحیح را صدا می‌زند."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_post.side_effect = [
            _make_eitaa_response(True, {"message_id": 1}),
            _make_eitaa_response(True, {"message_id": 2}),
            _make_eitaa_response(True, {"message_id": 3}),
        ]
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")

        photo = SimpleUploadedFile("p.jpg", b"fake_photo", content_type="image/jpeg")
        video = SimpleUploadedFile("v.mp4", b"fake_video", content_type="video/mp4")
        doc = SimpleUploadedFile("d.pdf", b"fake_doc", content_type="application/pdf")

        self.assertEqual(adapter.send_media("1404", "photo", photo, "cap")["message_id"], "1")
        self.assertEqual(adapter.send_media("1404", "video", video, "cap")["message_id"], "2")
        self.assertEqual(adapter.send_media("1404", "document", doc, "cap")["message_id"], "3")

        # همه فراخوانی‌ها باید به sendFile یا sendDocument برن
        urls = [call[0][0] for call in mock_post.call_args_list]
        self.assertTrue(any("sendFile" in u for u in urls))
        self.assertTrue(any("sendDocument" in u for u in urls))

    def test_send_media_unsupported_type_raises(self):
        """نوع محتوای ناشناخته باعث ValueError می‌شود."""
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")
        with self.assertRaises(ValueError):
            adapter.send_media("1404", "audio", "a.mp3", "")


class EitaaAdapterErrorTests(TestCase):
    """تست‌های تبدیل خطاهای API ایتا به خطاهای معنادار."""

    @patch("product.forward.messengers.adapters.eitaa.requests.post")
    def test_not_found_error_mapped(self, mock_post):
        """خطای chat not found به MessengerNotFoundError تبدیل می‌شود."""
        mock_post.return_value = _make_eitaa_response(False, description="chat not found")
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")
        with self.assertRaises(MessengerNotFoundError):
            adapter.send_text("9999", "test")

    @patch("product.forward.messengers.adapters.eitaa.requests.post")
    def test_permission_error_mapped(self, mock_post):
        """خطای forbidden به MessengerPermissionError تبدیل می‌شود."""
        mock_post.return_value = _make_eitaa_response(False, description="Forbidden: not enough rights")
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")
        with self.assertRaises(MessengerPermissionError):
            adapter.send_text("1404", "test")

    @patch("product.forward.messengers.adapters.eitaa.requests.post")
    def test_rate_limit_mapped(self, mock_post):
        """خطای rate limit به MessengerRateLimitError تبدیل می‌شود."""
        mock_post.return_value = _make_eitaa_response(False, description="Too Many Requests")
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")
        with self.assertRaises(MessengerRateLimitError):
            adapter.send_text("1404", "test")


class EitaaAdapterInfoTests(TestCase):
    """تست‌های دریافت اطلاعات ربات و بررسی ادمین بودن."""

    @patch("product.forward.messengers.adapters.eitaa.requests.post")
    def test_get_bot_username(self, mock_post):
        """get_bot_username نام کاربری را از getMe استخراج می‌کند."""
        mock_post.return_value = _make_eitaa_response(True, {"username": "win_forward_bot"})
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")
        self.assertEqual(adapter.get_bot_username(), "win_forward_bot")

    def test_check_bot_is_admin_always_true(self):
        """check_bot_is_admin برای ایتا همیشه True برمی‌گرداند (مسئولیت با کاربر)."""
        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        adapter = EitaaAdapter(token="test_token")
        self.assertTrue(adapter.check_bot_is_admin("1404"))


# ============================================================
# Eitaa Data Modeling Tests (Phase 4)
# ============================================================

class EitaaBotUserModelTests(TestCase):
    """تست‌های فیلد api_token در مدل BotUser."""

    def setUp(self):
        """آماده‌سازی کاربر، پلتفرم ایتا و پلتفرم بله."""
        from core.models import Platform
        self.user = CustomUser(phone_number="09120003333", nickname="EitaaUser")
        self.user.set_unusable_password()
        self.user.save()

        self.eitaa_platform = Platform.objects.create(
            name="Eitaa", slug="eitaa", description="Eitaa test", is_active=True, is_forward_active=True
        )
        self.bale_platform = Platform.objects.create(
            name="Bale", slug="bale", description="Bale test", is_active=True
        )

    def test_bot_user_api_token_can_be_saved(self):
        """فیلد api_token باید قابل ذخیره و بازیابی باشد."""
        from product.forward.messengers.models import BotUser
        bot_user = BotUser.objects.create(
            user=self.user,
            platform=self.eitaa_platform,
            chat_id=f"eitaa_user_{self.user.id}",
            is_verified=True,
            api_token="test_eitaayar_token_xyz",
        )
        bot_user.refresh_from_db()
        self.assertEqual(bot_user.api_token, "test_eitaayar_token_xyz")

    def test_bot_user_api_token_is_optional(self):
        """برای بله، api_token باید بتواند خالی بماند."""
        from product.forward.messengers.models import BotUser
        bot_user = BotUser.objects.create(
            user=self.user,
            platform=self.bale_platform,
            chat_id="bale_chat_123",
            is_verified=True,
        )
        self.assertIsNone(bot_user.api_token)

    def test_bale_bot_user_unaffected(self):
        """فیلد جدید نباید رفتار بله را تغییر دهد."""
        from product.forward.messengers.models import BotUser
        bot_user = BotUser.objects.create(
            user=self.user,
            platform=self.bale_platform,
            chat_id="bale_chat_999",
            is_verified=True,
        )
        self.assertEqual(bot_user.platform.slug, "bale")
        self.assertIsNone(bot_user.api_token)


class EitaaDeepLinkBlockedTests(TestCase):
    """تست‌های مسدود بودن Deep Link برای ایتا."""

    def setUp(self):
        """آماده‌سازی کاربر، پلتفرم ایتا و کانال."""
        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel
        self.user = CustomUser(phone_number="09120004444", nickname="EitaaLinkUser")
        self.user.set_unusable_password()
        self.user.save()
        self.eitaa_platform = Platform.objects.create(
            name="Eitaa", slug="eitaa", description="Eitaa test", is_active=True
        )
        self.channel = BroadcastChannel.objects.create(
            user=self.user, platform=self.eitaa_platform, chat_id="1404", title="کانال ایتا"
        )

    def test_build_deep_link_raises_for_eitaa(self):
        """build_deep_link برای ایتا باید ValueError بدهد."""
        from product.forward.broadcast.services import channel_sync
        channel_sync.generate_verification_token(self.channel)
        with self.assertRaises(ValueError) as ctx:
            channel_sync.build_deep_link(self.channel, bot_username="any_bot")
        self.assertIn("پشتیبانی", str(ctx.exception))

    def test_build_deep_link_works_for_bale(self):
        """برای بله، build_deep_link باید مثل قبل کار کند (بدون رگرسیون)."""
        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel
        from product.forward.broadcast.services import channel_sync

        bale = Platform.objects.create(name="Bale", slug="bale", description="Bale", is_active=True)
        bale_channel = BroadcastChannel.objects.create(
            user=self.user, platform=bale, chat_id="@test_ch", title="کانال بله"
        )
        channel_sync.generate_verification_token(bale_channel)
        link = channel_sync.build_deep_link(bale_channel, bot_username="my_bot")
        self.assertIn("ble.ir/my_bot?start=verify_", link)


class EitaaConnectLinkBlockedTests(TestCase):
    """تست‌های مسدود بودن generate_connect_link برای ایتا."""

    def setUp(self):
        from core.models import Platform
        self.user = CustomUser(phone_number="09120005555", nickname="ConnectUser")
        self.user.set_unusable_password()
        self.user.save()
        self.eitaa_platform = Platform.objects.create(
            name="Eitaa", slug="eitaa", description="Eitaa", is_active=True
        )

    def test_generate_connect_link_raises_for_eitaa(self):
        """generate_connect_link برای ایتا باید ValueError بدهد."""
        from product.forward.messengers.services import generate_connect_link
        with self.assertRaises(ValueError) as ctx:
            generate_connect_link(self.user, "eitaa")
        self.assertIn("پشتیبانی نمی‌کند", str(ctx.exception))

    def test_generate_connect_link_still_works_for_bale(self):
        """برای بله، generate_connect_link نباید رگرسیون داشته باشد."""
        from core.models import Platform
        from product.forward.messengers.services import generate_connect_link

        Platform.objects.create(name="Bale", slug="bale", description="Bale", is_active=True)
        link = generate_connect_link(self.user, "bale")
        self.assertIn("ble.ir/", link)
        self.assertIn("connect_", link)


class EitaaDispatcherTests(TestCase):
    """تست‌های ارسال به کانال ایتا از طریق Dispatcher."""

    def setUp(self):
        from core.models import Platform
        from product.forward.messengers.models import BotUser
        from product.forward.broadcast.models import BroadcastChannel, BroadcastMessage

        self.user = CustomUser(phone_number="09120008888", nickname="EitaaDispatch")
        self.user.set_unusable_password()
        self.user.save()
        self.eitaa_platform = Platform.objects.create(
            name="Eitaa", slug="eitaa", description="Eitaa", is_active=True, is_forward_active=True
        )
        self.msg = BroadcastMessage.objects.create(user=self.user, content_type="text", text="سلام ایتا")

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_dispatch_uses_user_token_for_eitaa(self, mock_get_adapter):
        """Dispatcher باید توکن کاربر را به EitaaAdapter پاس بدهد."""
        from product.forward.messengers.models import BotUser
        from product.forward.broadcast.models import BroadcastChannel, BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job

        BotUser.objects.create(
            user=self.user, platform=self.eitaa_platform,
            chat_id=f"eitaa_user_{self.user.id}",
            is_verified=True, api_token="user_eitaa_token_xyz",
        )
        channel = BroadcastChannel.objects.create(
            user=self.user, platform=self.eitaa_platform,
            chat_id="1404", title="کانال ایتا", bot_is_admin=True, is_active=True,
        )

        mock_adapter = MagicMock()
        mock_adapter.send_text.return_value = {"message_id": "200"}
        mock_get_adapter.return_value = mock_adapter

        job = BroadcastJob.objects.create(message=self.msg)
        BroadcastTarget.objects.create(job=job, channel=channel)

        dispatch_job(job.pk)

        # آداپتور باید با token=... صدا زده شده باشه
        mock_get_adapter.assert_called_once_with("eitaa", token="user_eitaa_token_xyz")

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_dispatch_fails_without_token(self, mock_get_adapter):
        """اگر کاربر توکن ایتا نداشته باشد، Target باید FAILED شود."""
        from product.forward.broadcast.models import BroadcastChannel, BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job

        channel = BroadcastChannel.objects.create(
            user=self.user, platform=self.eitaa_platform,
            chat_id="1404", title="کانال ایتا", bot_is_admin=True, is_active=True,
        )

        job = BroadcastJob.objects.create(message=self.msg)
        target = BroadcastTarget.objects.create(job=job, channel=channel)

        dispatch_job(job.pk)

        target.refresh_from_db()
        self.assertEqual(target.status, BroadcastTarget.Status.FAILED)
        self.assertIn("توکن ایتایار", target.error_message)
