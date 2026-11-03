"""تست‌های واحد آداپتور بله با mock کردن HTTP API."""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from product.forward.messengers.adapters.base import (
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from product.forward.messengers.adapters.registry import get_adapter, get_registered_slugs


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
    @patch("product.forward.messengers.adapters.bale.requests.get")
    def test_send_media_dispatch_all_types(self, mock_get):
        """send_media برای هر نوع محتوا متد صحیح را صدا می‌زند."""
        mock_get.side_effect = [
            _make_response(True, {"message_id": 1}),
            _make_response(True, {"message_id": 2}),
            _make_response(True, {"message_id": 3}),
        ]
        from product.forward.messengers.adapters.bale import BaleAdapter
        adapter = BaleAdapter()
        self.assertEqual(adapter.send_media("@ch", "photo", "p.jpg", "cap")["message_id"], "1")
        self.assertEqual(adapter.send_media("@ch", "video", "v.mp4", "cap")["message_id"], "2")
        self.assertEqual(adapter.send_media("@ch", "document", "d.pdf", "cap")["message_id"], "3")
        urls = [call[0][0] for call in mock_get.call_args_list]
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
        """آماده‌سازی URL و mock کردن آداپتور."""
        self.url = "/webhooks/bale/"
        from django.test import override_settings
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