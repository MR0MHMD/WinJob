"""تست‌های واحد سرویس همگام‌سازی کانال (channel_sync)."""

from datetime import timedelta
from unittest.mock import patch, MagicMock

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
        channel_tg = BroadcastChannel.objects.create(user=self.user, platform=platform_tg, chat_id="@tg_channel",
                                                     title="کانال تلگرام")
        token_bale = channel_sync.generate_verification_token(self.channel)
        token_tg = channel_sync.generate_verification_token(channel_tg)
        r1 = channel_sync.finalize_verification(token_bale, "bale", bot_chat_id="bale_111")
        r2 = channel_sync.finalize_verification(token_tg, "telegram", bot_chat_id="tg_222")
        self.assertTrue(r1["ok"])
        self.assertTrue(r2["ok"])
        self.assertEqual(BotUser.objects.filter(user=self.user).count(), 2)


class DispatcherTests(TestCase):
    """تست‌های سرویس ارسال (Dispatcher) در حالت Eager."""

    def setUp(self):
        """آماده‌سازی کاربر، پلتفرم، کانال و پیام."""
        from accounts.models import CustomUser
        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel, BroadcastMessage, BroadcastJob, BroadcastTarget

        self.user = CustomUser(phone_number="09001386427", nickname="DispatcherUser")
        self.user.set_unusable_password()
        self.user.save()

        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)

        self.channel_ok = BroadcastChannel.objects.create(
            user=self.user, platform=self.platform, chat_id="-1001", title="کانال موفق", bot_is_admin=True
        )
        self.channel_fail = BroadcastChannel.objects.create(
            user=self.user, platform=self.platform, chat_id="-1002", title="کانال ناموفق", bot_is_admin=True
        )

        self.msg_text = BroadcastMessage.objects.create(user=self.user, content_type="text", text="سلام دنیا")
        self.msg_photo = BroadcastMessage.objects.create(user=self.user, content_type="photo", text="کپشن",
                                                         file="test.jpg")

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_dispatch_text_success(self, mock_get_adapter):
        """ارسال متن باید موفق شود و وضعیت Target و Job آپدیت شود."""
        from product.forward.broadcast.models import BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job

        mock_adapter = MagicMock()
        mock_adapter.send_text.return_value = {"message_id": "12345"}
        mock_get_adapter.return_value = mock_adapter

        job = BroadcastJob.objects.create(message=self.msg_text)
        target = BroadcastTarget.objects.create(job=job, channel=self.channel_ok)

        result = dispatch_job(job.pk)

        self.assertTrue(result["ok"])

        target.refresh_from_db()
        self.assertEqual(target.status, BroadcastTarget.Status.SUCCESS)
        self.assertEqual(target.platform_message_id, "12345")

        job.refresh_from_db()
        self.assertEqual(job.status, BroadcastJob.Status.DONE)
        self.assertEqual(job.success_count, 1)
        self.assertEqual(job.failed_count, 0)

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_dispatch_text_api_error(self, mock_get_adapter):
        """خطای API باید باعث FAILED شدن Target و PARTIAL شدن Job شود."""
        from product.forward.broadcast.models import BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job
        from product.forward.messengers.adapters.base import MessengerAPIError

        mock_adapter = MagicMock()
        mock_adapter.send_text.side_effect = MessengerAPIError("Chat not found")
        mock_get_adapter.return_value = mock_adapter

        job = BroadcastJob.objects.create(message=self.msg_text)
        target = BroadcastTarget.objects.create(job=job, channel=self.channel_fail)

        dispatch_job(job.pk)

        target.refresh_from_db()
        self.assertEqual(target.status, BroadcastTarget.Status.FAILED)
        self.assertIn("Chat not found", target.error_message)

        job.refresh_from_db()
        self.assertEqual(job.status, BroadcastJob.Status.FAILED)
        self.assertEqual(job.failed_count, 1)

    def test_message_validation_requires_file_for_non_text(self):
        """مدل پیام اجازه نمی‌دهد content_type غیرمتنی بدون فایل ایجاد شود."""
        from django.core.exceptions import ValidationError
        from product.forward.broadcast.models import BroadcastMessage

        with self.assertRaises(ValidationError):
            BroadcastMessage.objects.create(user=self.user, content_type="photo", text="کپشن بدون فایل")


class DispatcherFileAndMultiChannelTests(TestCase):
    """تست‌های ارسال فایل و چند کانال در Dispatcher."""

    def setUp(self):
        """آماده‌سازی کاربر، پلتفرم و دو کانال."""
        from accounts.models import CustomUser
        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel

        self.user = CustomUser(phone_number="09001386427", nickname="FileUser")
        self.user.set_unusable_password()
        self.user.save()

        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)

        self.ch1 = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-1001",
                                                   title="کانال ۱", bot_is_admin=True)
        self.ch2 = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-1002",
                                                   title="کانال ۲", bot_is_admin=True)

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_dispatch_photo_uses_send_media(self, mock_get_adapter):
        """ارسال عکس باید send_media را با message.file صدا بزند."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from product.forward.broadcast.models import BroadcastMessage, BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job

        mock_adapter = MagicMock()
        mock_adapter.send_media.return_value = {"message_id": "999"}
        mock_get_adapter.return_value = mock_adapter

        photo = SimpleUploadedFile("test.jpg", b"fake_jpeg_bytes", content_type="image/jpeg")
        msg = BroadcastMessage.objects.create(user=self.user, content_type="photo", text="کپشن", file=photo)

        job = BroadcastJob.objects.create(message=msg)
        BroadcastTarget.objects.create(job=job, channel=self.ch1)

        dispatch_job(job.pk)

        mock_adapter.send_media.assert_called_once()
        args, _ = mock_adapter.send_media.call_args
        self.assertEqual(args[0], "-1001")
        self.assertEqual(args[1], "photo")
        self.assertEqual(args[3], "کپشن")

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_dispatch_multi_channel_all_success(self, mock_get_adapter):
        """ارسال به دو کانال موفق → وضعیت DONE."""
        from product.forward.broadcast.models import BroadcastMessage, BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job

        mock_adapter = MagicMock()
        mock_adapter.send_text.return_value = {"message_id": "123"}
        mock_get_adapter.return_value = mock_adapter

        msg = BroadcastMessage.objects.create(user=self.user, content_type="text", text="سلام")
        job = BroadcastJob.objects.create(message=msg)
        BroadcastTarget.objects.create(job=job, channel=self.ch1)
        BroadcastTarget.objects.create(job=job, channel=self.ch2)

        dispatch_job(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, BroadcastJob.Status.DONE)
        self.assertEqual(job.success_count, 2)
        self.assertEqual(job.failed_count, 0)
        self.assertEqual(mock_adapter.send_text.call_count, 2)

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_dispatch_partial_failure(self, mock_get_adapter):
        """یک کانال موفق، یک ناموفق → PARTIAL."""
        from product.forward.broadcast.models import BroadcastMessage, BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job
        from product.forward.messengers.adapters.base import MessengerAPIError

        mock_adapter = MagicMock()
        mock_adapter.send_text.side_effect = [
            {"message_id": "1"},
            MessengerAPIError("chat not found"),
        ]
        mock_get_adapter.return_value = mock_adapter

        msg = BroadcastMessage.objects.create(user=self.user, content_type="text", text="سلام")
        job = BroadcastJob.objects.create(message=msg)
        BroadcastTarget.objects.create(job=job, channel=self.ch1)
        BroadcastTarget.objects.create(job=job, channel=self.ch2)

        dispatch_job(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, BroadcastJob.Status.PARTIAL)
        self.assertEqual(job.success_count, 1)
        self.assertEqual(job.failed_count, 1)


class WebPanelTests(TestCase):
    """تست‌های پنل وب وین فوروارد."""

    def setUp(self):
        """آماده‌سازی کاربر، پلتفرم (با لوگوی فیک) و کانال."""
        from accounts.models import CustomUser
        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.user = CustomUser(phone_number="09001386427", nickname="WebUser")
        self.user.set_unusable_password()
        self.user.save()

        self.client.force_login(self.user)
        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)

        # 🔑 راه‌حل: دادن یه عکس فیک به لوگوی پلتفرم برای جلوگیری از خطای ValueError
        self.platform.logo = SimpleUploadedFile("test_logo.png", b"fake_image_data", content_type="image/png")
        self.platform.save()

        self.channel = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-1001",
                                                       title="کانال تست", bot_is_admin=True, is_active=True)

    def test_form_filters_channels_by_user(self):
        """فرم فقط باید کانال‌های کاربر فعلی را نشان دهد."""
        from accounts.models import CustomUser
        from product.forward.broadcast.models import BroadcastChannel
        from product.forward.broadcast.forms import BroadcastSendForm

        other_user = CustomUser(phone_number="09120000000", nickname="Other")
        other_user.set_unusable_password()
        other_user.save()
        BroadcastChannel.objects.create(user=other_user, platform=self.platform, chat_id="-2002", title="کانال دیگران",
                                        bot_is_admin=True, is_active=True)

        form = BroadcastSendForm(user=self.user)
        self.assertEqual(form.fields["channels"].queryset.count(), 1)
        self.assertEqual(form.fields["channels"].queryset.first(), self.channel)

    @patch("product.forward.broadcast.views.dispatch_job")
    def test_send_broadcast_view_creates_job(self, mock_dispatch):
        """ویو ارسال باید جاب و تارگت بسازد و دیسپچر را صدا بزند."""
        from product.forward.broadcast.models import BroadcastJob, BroadcastTarget

        response = self.client.post("/broadcast/send/", {
            "content_type": "text",
            "text": "پیام تستی",
            "channels": [self.channel.pk]
        })

        self.assertEqual(response.status_code, 302)  # Redirect to job_detail
        self.assertEqual(BroadcastJob.objects.count(), 1)
        self.assertEqual(BroadcastTarget.objects.count(), 1)
        mock_dispatch.assert_called_once()

    def test_job_detail_view_access(self):
        """صفحه جزئیات باید فقط برای صاحب جاب قابل دسترسی باشد."""
        from product.forward.broadcast.models import BroadcastMessage, BroadcastJob, BroadcastTarget

        msg = BroadcastMessage.objects.create(user=self.user, content_type="text", text="سلام")
        job = BroadcastJob.objects.create(message=msg)
        BroadcastTarget.objects.create(job=job, channel=self.channel)

        response = self.client.get(f"/broadcast/job/{job.pk}/")
        self.assertEqual(response.status_code, 200)


class JobListViewTests(TestCase):
    """تست‌های صفحه تاریخچه ارسال‌ها (Job List)."""

    def setUp(self):
        """آماده‌سازی دو کاربر، پلتفرم و جاب‌های آن‌ها."""
        from accounts.models import CustomUser
        from core.models import Platform
        from product.forward.broadcast.models import BroadcastMessage, BroadcastJob
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)
        self.platform.logo = SimpleUploadedFile("logo.png", b"fake", content_type="image/png")
        self.platform.save()

        self.user1 = CustomUser(phone_number="09001386427", nickname="User1")
        self.user1.set_unusable_password()
        self.user1.save()

        self.user2 = CustomUser(phone_number="09121111111", nickname="User2")
        self.user2.set_unusable_password()
        self.user2.save()

        # پیام و جاب برای کاربر ۱
        msg1 = BroadcastMessage.objects.create(user=self.user1, content_type="text", text="سلام از کاربر ۱")
        self.job1 = BroadcastJob.objects.create(message=msg1)

        # پیام و جاب برای کاربر ۲
        msg2 = BroadcastMessage.objects.create(user=self.user2, content_type="text", text="سلام از کاربر ۲")
        self.job2 = BroadcastJob.objects.create(message=msg2)

    def test_job_list_requires_login(self):
        """دسترسی به لیست بدون لاگین باید به صفحه ورود ریدایرکت شود."""
        response = self.client.get("/broadcast/jobs/")
        self.assertEqual(response.status_code, 302)  # Redirects to login
        self.assertIn("/accounts/login/", response.url)  # یا هر آدرسی که برای لاگین داری

    def test_job_list_shows_only_user_jobs(self):
        """لیست باید فقط جاب‌های کاربر لاگین‌شده را نشان دهد."""
        self.client.force_login(self.user1)
        response = self.client.get("/broadcast/jobs/")

        self.assertEqual(response.status_code, 200)
        jobs = response.context["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].pk, self.job1.pk)
        self.assertNotEqual(jobs[0].pk, self.job2.pk)

    def test_job_list_renders_correct_template(self):
        """صفحه لیست باید با تمپلیت صحیح رندر شود."""
        self.client.force_login(self.user1)
        response = self.client.get("/broadcast/jobs/")
        self.assertTemplateUsed(response, "product/forward/broadcast/job_list.html")


class FileIdOptimizationTests(TestCase):
    """تست‌های بهینه‌سازی سرعت با استفاده از file_id."""

    def setUp(self):
        from accounts.models import CustomUser
        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.user = CustomUser(phone_number="09001386427", nickname="OptUser")
        self.user.set_unusable_password()
        self.user.save()
        self.platform = Platform.objects.create(name="Bale", slug="bale", description="Test", is_active=True)
        self.platform.logo = SimpleUploadedFile("logo.png", b"fake", content_type="image/png")
        self.platform.save()

        self.ch1 = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-1",
                                                   title="کانال ۱", bot_is_admin=True)
        self.ch2 = BroadcastChannel.objects.create(user=self.user, platform=self.platform, chat_id="-2",
                                                   title="کانال ۲", bot_is_admin=True)

    @patch("product.forward.broadcast.services.dispatcher.get_adapter")
    def test_file_id_cached_and_used(self, mock_get_adapter):
        """آپلود فایل باید فقط یک بار انجام شود و بار دوم از file_id استفاده شود."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from product.forward.broadcast.models import BroadcastMessage, BroadcastJob, BroadcastTarget
        from product.forward.broadcast.services.dispatcher import dispatch_job

        # ماک کردن آداپتور
        mock_adapter = MagicMock()
        # بار اول یه file_id برمی‌گردونه، بار دوم نباید اصلا فایل آپلود کنه
        mock_adapter.send_media.return_value = {"message_id": "100", "file_id": "cached_id_123"}
        mock_get_adapter.return_value = mock_adapter

        photo = SimpleUploadedFile("test.jpg", b"fake_bytes", content_type="image/jpeg")
        msg = BroadcastMessage.objects.create(user=self.user, content_type="photo", text="کپشن", file=photo)

        job = BroadcastJob.objects.create(message=msg)
        BroadcastTarget.objects.create(job=job, channel=self.ch1)
        BroadcastTarget.objects.create(job=job, channel=self.ch2)

        dispatch_job(job.pk)

        # چک کردن فراخوانی آداپتور
        self.assertEqual(mock_adapter.send_media.call_count, 2)

        # بار اول بدون file_id، بار دوم با file_id
        first_call = mock_adapter.send_media.call_args_list[0][1]
        second_call = mock_adapter.send_media.call_args_list[1][1]

        self.assertIsNone(first_call.get("file_id"))
        self.assertEqual(second_call.get("file_id"), "cached_id_123")

        # چک کردن ذخیره شدن در دیتابیس
        msg.refresh_from_db()
        self.assertEqual(msg.platform_file_ids.get("bale"), "cached_id_123")
