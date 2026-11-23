"""تست‌های جامع وین‌فوروارد (channel_sync، تعرفه توکن، امضای AI، دیسپچر ۴فازی، پاک‌سازی فوری مدیا، ProgressTracker و دسترسی ساپورت)."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from core.models import Platform
from product.forward.broadcast.models import (
    BroadcastChannel,
    BroadcastJob,
    BroadcastMessage,
    BroadcastTarget,
)
from product.forward.broadcast.services import channel_sync
from product.forward.broadcast.services.ai_watermark import apply_channel_watermark
from product.forward.broadcast.services.dispatcher import dispatch_job
from product.forward.broadcast.services.progress import ProgressTracker
from product.forward.constants import (
    TOKEN_COST_AI_WATERMARK,
    TOKEN_COST_CAPTION_EXTRA,
    TOKEN_COST_HUB_EXTRA,
    TOKEN_COST_MEDIA_5_TO_10MB,
    TOKEN_COST_MEDIA_10_TO_20MB,
    TOKEN_COST_MEDIA_UNDER_5MB,
    TOKEN_COST_PHOTO,
    TOKEN_COST_STICKER_GIF,
    TOKEN_COST_TEXT,
)
from product.forward.messengers.adapters.base import MessengerAdapter, MessengerAPIError
from product.forward.messengers.adapters.registry import (
    get_adapter_class,
    register,
    unregister,
)
from product.forward.messengers.models import BotUser
from product.forward.subscriptions.models import ForwardTokenTransaction
from product.forward.subscriptions.services import (
    calculate_delivery_token_cost,
    credit_tokens_atomic,
)


def _give_tokens(user, amount: int = 500) -> None:
    """شارژ سریع کیف توکن کاربر برای تست‌های ارسال."""
    credit_tokens_atomic(
        user,
        amount,
        tx_type=ForwardTokenTransaction.TxType.ADMIN_ADJUST,
        description="شارژ تستی",
    )


class MockAdapter(MessengerAdapter):
    """آداپتور mock بله برای تست — بدون تماس با API واقعی."""

    platform_slug = "bale"

    def __init__(self, is_admin=True):
        self.is_admin = is_admin

    def send_text(self, chat_id, text):
        return {"message_id": "mock_text_1"}

    def send_photo(self, chat_id, photo, caption=""):
        return {"message_id": "mock_photo_1"}

    def send_video(self, chat_id, video, caption=""):
        return {"message_id": "mock_video_1"}

    def send_document(self, chat_id, document, caption=""):
        return {"message_id": "mock_doc_1"}

    def check_bot_is_admin(self, chat_id):
        return self.is_admin

    def get_chat_info(self, chat_id):
        return {"title": "Mock", "username": "mock", "type": "channel"}

    def get_bot_username(self):
        return "mock_bot"


class ChannelSyncBaseTestCase(TestCase):
    """تست پایه — ساخت داده‌های مشترک و ثبت MockAdapter."""

    def setUp(self):
        self._saved_bale = get_adapter_class("bale")
        self.user = CustomUser(phone_number="09120000001", nickname="Tester")
        self.user.set_unusable_password()
        self.user.save()
        self.platform = Platform.objects.create(
            name="Bale", slug="bale", description="Bale test", is_active=True
        )
        self.channel = BroadcastChannel.objects.create(
            user=self.user,
            platform=self.platform,
            chat_id="@test_channel",
            title="کانال تست",
        )
        register(MockAdapter, slug="bale")

    def tearDown(self):
        unregister("bale")
        if self._saved_bale is not None:
            register(self._saved_bale, slug="bale")


class ChannelSyncTests(ChannelSyncBaseTestCase):
    """تست‌های تولید توکن، دیپ‌لینک، بررسی ادمین و نهایی‌سازی تایید مالکیت."""

    def test_generate_token_and_overwrite(self):
        token1 = channel_sync.generate_verification_token(self.channel)
        self.channel.refresh_from_db()
        self.assertEqual(len(token1), 12)
        self.assertEqual(self.channel.verification_token, token1)
        token2 = channel_sync.generate_verification_token(self.channel)
        self.assertNotEqual(token1, token2)

    def test_bale_deep_link_success_and_failures(self):
        channel_sync.generate_verification_token(self.channel)
        self.channel.refresh_from_db()
        link = channel_sync.build_deep_link(self.channel, bot_username="Win_Forward_bot")
        self.assertEqual(
            link,
            f"https://ble.ir/Win_Forward_bot?start=verify_{self.channel.verification_token}",
        )
        self.channel.verification_token = ""
        self.channel.save(update_fields=["verification_token"])
        with self.assertRaises(ValueError):
            channel_sync.build_deep_link(self.channel, bot_username="Win_Forward_bot")

    def test_finalize_success_expired_and_not_admin(self):
        token = channel_sync.generate_verification_token(self.channel)
        res = channel_sync.finalize_verification(token, "bale", bot_chat_id="123456")
        self.assertTrue(res["ok"])
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.bot_is_admin)
        self.assertTrue(
            BotUser.objects.filter(user=self.user, platform=self.platform, chat_id="123456").exists()
        )

        # توکن منقضی
        token2 = channel_sync.generate_verification_token(self.channel)
        self.channel.verification_token_created_at = timezone.now() - timedelta(minutes=15)
        self.channel.save(update_fields=["verification_token_created_at"])
        res_exp = channel_sync.finalize_verification(token2, "bale")
        self.assertFalse(res_exp["ok"])
        self.assertEqual(res_exp["error"], "expired_token")

        # ربات ادمین نیست
        unregister("bale")

        class NotAdminMock(MockAdapter):
            def __init__(self):
                super().__init__(is_admin=False)

        register(NotAdminMock, slug="bale")
        token3 = channel_sync.generate_verification_token(self.channel)
        res_na = channel_sync.finalize_verification(token3, "bale")
        self.assertFalse(res_na["ok"])
        self.assertEqual(res_na["error"], "bot_not_admin")


class TokenPricingConstantsTests(TestCase):
    """تست محاسبه تعرفه توکن از روی constants.py بدون نیاز به مدل دیتابیسی."""

    def test_text_photo_sticker_media_and_addons(self):
        self.assertEqual(calculate_delivery_token_cost("text"), TOKEN_COST_TEXT)
        self.assertEqual(calculate_delivery_token_cost("photo", has_caption=False), TOKEN_COST_PHOTO)
        self.assertEqual(
            calculate_delivery_token_cost("photo", has_caption=True),
            TOKEN_COST_PHOTO + TOKEN_COST_CAPTION_EXTRA,
        )
        self.assertEqual(calculate_delivery_token_cost("sticker"), TOKEN_COST_STICKER_GIF)
        self.assertEqual(
            calculate_delivery_token_cost("video", has_caption=False, file_size_bytes=2 * 1024 * 1024),
            TOKEN_COST_MEDIA_UNDER_5MB,
        )
        self.assertEqual(
            calculate_delivery_token_cost("video", has_caption=True, file_size_bytes=7 * 1024 * 1024),
            TOKEN_COST_MEDIA_5_TO_10MB + TOKEN_COST_CAPTION_EXTRA,
        )
        self.assertEqual(
            calculate_delivery_token_cost("document", has_caption=False, file_size_bytes=15 * 1024 * 1024),
            TOKEN_COST_MEDIA_10_TO_20MB,
        )
        self.assertEqual(
            calculate_delivery_token_cost("text", is_hub=True, use_ai_watermark=True),
            TOKEN_COST_TEXT + TOKEN_COST_HUB_EXTRA + TOKEN_COST_AI_WATERMARK,
        )


class AIWatermarkApplyTests(TestCase):
    """تست‌های اعمال امضای اختصاصی (حذف+امضا و بازسازی هوشمند متناسب با پلتفرم)."""

    def test_remove_append_mode(self):
        ch = SimpleNamespace(
            title="کانال ما",
            username="our_ch",
            watermark_mode="remove_append",
            custom_signature="🆔 @our_ch",
            watermark_display_id="",
            platform=SimpleNamespace(slug="bale", name="بله"),
        )
        ai_res = {
            "ok": True,
            "cleaned_text": "متن تمیز خبر",
            "templated_text": "متن تمیز خبر\n{{CHANNEL_ID}}",
        }
        out = apply_channel_watermark("متن اصلی @old", ch, ai_res)
        self.assertEqual(out, "متن تمیز خبر\n\n🆔 @our_ch")

    def test_rewrite_mode_platform_aware_and_private_channel(self):
        ai_res = {
            "ok": True,
            "cleaned_text": "خبر مهم",
            "templated_text": "خبر مهم\n\n*{{CHANNEL_NAME}}*\n🆔[کانال {{PLATFORM_NAME}}]({{CHANNEL_URL}})\n{{CHANNEL_ID}}",
        }
        ch_eitaa = SimpleNamespace(
            title="کانال خبری",
            username="khabar_ir",
            watermark_mode="rewrite",
            custom_signature="",
            watermark_display_id="",
            platform=SimpleNamespace(slug="eitaa", name="ایتا"),
        )
        out_eitaa = apply_channel_watermark("raw", ch_eitaa, ai_res)
        self.assertIn("https://eitaa.com/khabar_ir", out_eitaa)
        self.assertIn("کانال ایتا", out_eitaa)
        self.assertIn("@khabar_ir", out_eitaa)

        # کانال خصوصی بدون آیدی نباید لینک شکسته یا تگ خام باقی بگذارد
        ch_private = SimpleNamespace(
            title="کانال خصوصی",
            username="",
            watermark_mode="rewrite",
            custom_signature="",
            watermark_display_id="",
            platform=SimpleNamespace(slug="telegram", name="تلگرام"),
        )
        out_priv = apply_channel_watermark("raw", ch_private, ai_res)
        self.assertNotIn("{{CHANNEL_URL}}", out_priv)
        self.assertNotIn("{{CHANNEL_ID}}", out_priv)
        self.assertIn("کانال خصوصی", out_priv)


class DispatcherCoreAndCleanupTests(TestCase):
    """تست‌های دیسپچر ۴فازی، سیاست سروش‌پلاس، کش file_id و حذف فوری فایل مدیا."""

    def setUp(self):
        self.user = CustomUser(phone_number="09001386427", nickname="DispatcherUser")
        self.user.set_unusable_password()
        self.user.save()
        _give_tokens(self.user, 500)

        self.bale = Platform.objects.create(name="Bale", slug="bale", description="Bale", is_active=True)
        self.tg = Platform.objects.create(name="Telegram", slug="telegram", description="TG", is_active=True)
        self.soroush = Platform.objects.create(name="Soroush+", slug="soroush", description="S+", is_active=True)

        self.ch_bale1 = BroadcastChannel.objects.create(
            user=self.user, platform=self.bale, chat_id="-1001", title="بله ۱", bot_is_admin=True
        )
        self.ch_bale2 = BroadcastChannel.objects.create(
            user=self.user, platform=self.bale, chat_id="-1002", title="بله ۲", bot_is_admin=True
        )
        self.ch_tg = BroadcastChannel.objects.create(
            user=self.user, platform=self.tg, chat_id="-2001", title="تلگرام ۱", bot_is_admin=True
        )
        self.ch_soroush = BroadcastChannel.objects.create(
            user=self.user, platform=self.soroush, chat_id="sr_ch_1", title="سروش ۱", bot_is_admin=True
        )
        BotUser.objects.create(
            user=self.user,
            platform=self.soroush,
            chat_id="sr_user",
            is_verified=True,
            session_data={"string_session": "fake_session_data", "channel_hashes": {}},
        )

    def test_message_validation_requires_file_for_non_text(self):
        with self.assertRaises(ValidationError):
            BroadcastMessage.objects.create(user=self.user, content_type="photo", text="بدون فایل")

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_uploaded_media_is_deleted_immediately_after_job(self, mock_get_adapter):
        """فایل آپلودشده از پنل وب باید بلافاصله بعد از پایان جاب از دیسک و فیلد DB پاک شود."""
        mock_adapter = MagicMock()
        mock_adapter.send_media.return_value = {"message_id": "100", "file_id": "cached_bale_id"}
        mock_get_adapter.return_value = mock_adapter

        photo = SimpleUploadedFile("cleanup_test.jpg", b"fake_jpeg_bytes", content_type="image/jpeg")
        msg = BroadcastMessage.objects.create(user=self.user, content_type="photo", text="کپشن", file=photo)
        storage = msg.file.storage
        saved_name = msg.file.name
        self.assertTrue(storage.exists(saved_name))

        job = BroadcastJob.objects.create(message=msg)
        BroadcastTarget.objects.create(job=job, channel=self.ch_bale1)
        BroadcastTarget.objects.create(job=job, channel=self.ch_bale2)

        res = dispatch_job(job.pk)
        self.assertTrue(res["ok"])

        # بررسی استفاده از file_id در کانال دوم
        self.assertEqual(mock_adapter.send_media.call_count, 2)
        self.assertIsNone(mock_adapter.send_media.call_args_list[0][1].get("file_id"))
        self.assertEqual(mock_adapter.send_media.call_args_list[1][1].get("file_id"), "cached_bale_id")

        # بررسی پاک‌سازی فوری فایل فیزیکی و فیلد file در دیتابیس
        msg.refresh_from_db()
        self.assertEqual(msg.file.name, "")
        self.assertFalse(storage.exists(saved_name))
        self.assertEqual(msg.platform_file_ids.get("bale"), "cached_bale_id")

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_four_phase_execution_order_download_ai_source_then_cross(self, mock_get_adapter):
        """ترتیب دقیق اجرا: ۱) دانلود از مبدا ۲) امضای AI ۳) ارسال به مبدا با file_id ۴) ارسال به پلتفرم دیگر."""
        events = []

        bale_adapter = MagicMock()
        bale_adapter.platform_slug = "bale"
        bale_adapter.get_file.side_effect = lambda fid: (events.append("download_meta"), {"file_path": "p/img.jpg"})[1]
        bale_adapter.download_file.side_effect = lambda fp: (events.append("download_bytes"), b"raw_img")[1]
        bale_adapter.send_media.side_effect = lambda cid, ct, fobj, cap, file_id=None: (
            events.append(f"send_bale:file_id={file_id}:has_obj={fobj is not None}"),
            {"message_id": "b1"},
        )[1]

        tg_adapter = MagicMock()
        tg_adapter.platform_slug = "telegram"
        tg_adapter.send_media.side_effect = lambda cid, ct, fobj, cap, file_id=None: (
            events.append(f"send_tg:file_id={file_id}:has_obj={fobj is not None}"),
            {"message_id": "t1"},
        )[1]

        mock_get_adapter.side_effect = lambda slug, **kw: bale_adapter if slug == "bale" else tg_adapter

        self.ch_bale1.watermark_mode = "remove_append"
        self.ch_bale1.custom_signature = "@my_bale"
        self.ch_bale1.save(update_fields=["watermark_mode", "custom_signature"])

        msg = BroadcastMessage.objects.create(
            user=self.user,
            content_type="photo",
            text="خبر مهم @old_src",
            platform_file_ids={"source_platform": "bale", "bale": "bale_fid_99"},
        )
        job = BroadcastJob.objects.create(message=msg)
        # عمداً تلگرام را اول اضافه می‌کنیم تا مطمئن شویم دیسپچر خودش ترتیب مبدا → سایرین را رعایت می‌کند
        BroadcastTarget.objects.create(job=job, channel=self.ch_tg)
        BroadcastTarget.objects.create(job=job, channel=self.ch_bale1)

        with patch(
            "product.forward.broadcast.services.ai_watermark.analyze_text_watermark",
            side_effect=lambda txt: (
                events.append("ai_watermark"),
                {"ok": True, "cleaned_text": "خبر مهم", "templated_text": "خبر مهم"},
            )[1],
        ):
            res = dispatch_job(job.pk)

        self.assertTrue(res["ok"])
        self.assertEqual(
            events,
            [
                "download_meta",
                "download_bytes",
                "ai_watermark",
                "send_bale:file_id=bale_fid_99:has_obj=False",
                "send_tg:file_id=None:has_obj=True",
            ],
        )

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_soroush_text_caption_only_and_skipped_recalculate_counts(self, mock_get_adapter):
        """سروش‌پلاس رسانه بدون کپشن را SKIPPED می‌کند و recalculate_counts وضعیت جاب را درست می‌بندد."""
        bale_adapter = MagicMock()
        bale_adapter.send_media.return_value = {"message_id": "b1"}
        soroush_adapter = MagicMock()
        soroush_adapter.send_text.return_value = {"message_id": "s1"}
        mock_get_adapter.side_effect = lambda slug, **kw: soroush_adapter if slug == "soroush" else bale_adapter

        # ۱) عکس بدون کپشن → بله موفق، سروش‌پلاس SKIPPED → وضعیت کل جاب DONE
        msg_no_cap = BroadcastMessage.objects.create(
            user=self.user,
            content_type="photo",
            text="",
            platform_file_ids={"source_platform": "bale", "bale": "fid_1"},
        )
        job1 = BroadcastJob.objects.create(message=msg_no_cap)
        t_bale = BroadcastTarget.objects.create(job=job1, channel=self.ch_bale1)
        t_sr = BroadcastTarget.objects.create(job=job1, channel=self.ch_soroush)

        dispatch_job(job1.pk)
        t_bale.refresh_from_db()
        t_sr.refresh_from_db()
        job1.refresh_from_db()

        self.assertEqual(t_bale.status, BroadcastTarget.Status.SUCCESS)
        self.assertEqual(t_sr.status, BroadcastTarget.Status.SKIPPED)
        self.assertEqual(job1.status, BroadcastJob.Status.DONE)
        self.assertEqual(job1.success_count, 1)
        self.assertEqual(job1.failed_count, 0)
        soroush_adapter.send_text.assert_not_called()

        # ۲) عکس با کپشن → سروش‌پلاس فقط کپشن را با send_text می‌فرستد
        msg_with_cap = BroadcastMessage.objects.create(
            user=self.user,
            content_type="photo",
            text="کپشن خبر فوری",
            platform_file_ids={"source_platform": "bale", "bale": "fid_2"},
        )
        job2 = BroadcastJob.objects.create(message=msg_with_cap)
        BroadcastTarget.objects.create(job=job2, channel=self.ch_soroush)
        dispatch_job(job2.pk)
        soroush_adapter.send_text.assert_called_once_with("sr_ch_1", "کپشن خبر فوری")


class ProgressTrackerHubFallbackTests(TestCase):
    """تست ارسال گزارش به مالک هاب همراه با نام فرستنده وقتی فرستنده در گروه ربات را استارت نکرده باشد."""

    def test_fallback_to_hub_owner_includes_hub_and_sender_name(self):
        adapter = MagicMock()
        adapter.platform_slug = "bale"
        sent_messages = []

        def fake_send_text(chat_id, text, **kwargs):
            if str(chat_id) == "sender_not_started":
                raise MessengerAPIError("Forbidden: bot can't initiate conversation")
            sent_messages.append((str(chat_id), text))
            return {"message_id": "m_owner_1"}

        adapter.send_text.side_effect = fake_send_text

        tracker = ProgressTracker(
            adapter,
            "sender_not_started",
            fallback_chat_id="hub_owner_99",
            hub_title="گروه تحریریه",
            hub_sender_name="علی رضایی (@ali_r)",
            is_file_msg=False,
            source_platform="bale",
            platform_totals={"bale": 1},
        )
        tracker.start()

        self.assertTrue(tracker.is_fallback_to_owner)
        self.assertEqual(tracker.chat_id, "hub_owner_99")
        self.assertEqual(len(sent_messages), 1)
        dest, body = sent_messages[0]
        self.assertEqual(dest, "hub_owner_99")
        self.assertIn("گروه تحریریه", body)
        self.assertIn("علی رضایی (@ali_r)", body)


class SupportWinForwardAccessTests(TestCase):
    """تست محدودیت دسترسی پنل ساپورت وین‌فوروارد (فقط مدیرعامل و توسعه‌دهنده)."""

    def setUp(self):
        self.normal_user = CustomUser(phone_number="09120000111", nickname="Normal")
        self.normal_user.set_unusable_password()
        self.normal_user.save()

        self.top_manager = CustomUser(
            phone_number="09120000222",
            nickname="CEO",
            is_staff=True,
            is_superuser=True,
        )
        self.top_manager.set_unusable_password()
        self.top_manager.save()

    def test_non_top_manager_denied_and_top_manager_allowed(self):
        self.client.force_login(self.normal_user)
        for name in (
            "support:forward_dashboard",
            "support:forward_finance",
            "support:forward_jobs",
            "support:forward_channels",
            "support:forward_tokens",
        ):
            resp = self.client.get(reverse(name))
            self.assertIn(resp.status_code, (302, 403), msg=f"Route {name} should block normal users")

        if getattr(self.top_manager, "is_top_manager", False):
            self.client.force_login(self.top_manager)
            for name in (
                "support:forward_dashboard",
                "support:forward_finance",
                "support:forward_jobs",
                "support:forward_channels",
                "support:forward_tokens",
            ):
                resp = self.client.get(reverse(name))
                self.assertEqual(resp.status_code, 200, msg=f"Route {name} should return 200 for top manager")
