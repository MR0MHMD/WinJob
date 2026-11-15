"""سرویس ارسال پیام (Dispatcher) — هسته اصلی وین فوروارد."""

import logging

from django.core.files.base import ContentFile
from django.utils import timezone

from product.forward.broadcast.models import BroadcastJob, BroadcastMessage, BroadcastTarget
from product.forward.messengers.adapters.registry import get_adapter
from product.forward.messengers.adapters.base import MessengerError, MessengerAPIError

logger = logging.getLogger(__name__)

_PLATFORM_FA_NAMES = {
    "bale": "بله",
    "eitaa": "ایتا",
    "telegram": "تلگرام",
    "rubika": "روبیکا",
    "soroush": "سروش",
}

_PLATFORM_ORDER = ["bale", "eitaa", "telegram", "rubika", "soroush"]


def _platform_fa(slug: str) -> str:
    return _PLATFORM_FA_NAMES.get(slug, slug)


def _download_external_file(source_platform: str, source_file_id: str) -> bytes:
    """دانلود فایل از پلتفرم دیگر (فعلاً فقط بله)."""
    if source_platform == "bale":
        from product.forward.messengers.adapters.bale import BaleAdapter
        bale = BaleAdapter()
        file_info = bale.get_file(source_file_id)
        file_path = (file_info or {}).get("file_path")
        if not file_path:
            raise MessengerAPIError("پاسخ getFile از بله فاقد file_path است.")
        return bale.download_file(file_path)
    raise MessengerAPIError(f"دانلود از پلتفرم «{_platform_fa(source_platform)}» پشتیبانی نمی‌شود.")


def _make_filename(message) -> str:
    """ساخت نام فایل با پسوند صحیح."""
    ext_map = {
        "photo": "jpg",
        "video": "mp4",
        "audio": "mp3",
        "voice": "ogg",
        "document": "bin",
        "animation": "gif",  # 🔑 پسوند gif برای ایتا
        "sticker": "webp",
    }
    ext = ext_map.get(message.content_type, "bin")
    return f"forwarded_{message.pk}.{ext}"


class ProgressTracker:
    """مدیریت پیام وضعیت واحد که با تغییر مرحله ویرایش می‌شه."""

    def __init__(self, adapter, chat_id):
        self.adapter = adapter
        self.chat_id = chat_id
        self.message_id = None
        self._current_text = None

    def _update(self, text: str):
        if text == self._current_text:
            return
        self._current_text = text
        if self.message_id:
            try:
                self.adapter.edit_message_text(self.chat_id, self.message_id, text)
                return
            except Exception as e:
                logger.warning(f"edit_message_text failed, falling back to send: {e}")
                self.message_id = None
        try:
            result = self.adapter.send_text(self.chat_id, text)
            self.message_id = result.get("message_id")
        except Exception as e:
            logger.warning(f"Failed to send progress message: {e}")

    def start_download(self):
        self._update("📥 در حال دانلود فایل از بله...")

    def start_upload(self, platform_slug: str = "eitaa"):
        self._update(f"📤 در حال آپلود فایل به {_platform_fa(platform_slug)}...")

    def finish(self, job):
        self._update(self._build_final_text(job))

    @staticmethod
    def _build_final_text(job) -> str:
        stats = {}
        for t in job.targets.select_related("channel__platform").all():
            slug = t.channel.platform.slug
            if slug not in stats:
                stats[slug] = {"success": 0, "failed": 0}
            if t.status == BroadcastTarget.Status.SUCCESS:
                stats[slug]["success"] += 1
            elif t.status == BroadcastTarget.Status.FAILED:
                stats[slug]["failed"] += 1

        if not stats:
            return "⚠️ هیچ کانالی برای ارسال وجود نداشت."

        ordered_slugs = [s for s in _PLATFORM_ORDER if s in stats]
        for s in stats:
            if s not in ordered_slugs:
                ordered_slugs.append(s)

        lines = ["✅ پیام شما پردازش شد.", ""]
        total_success = 0
        total_failed = 0
        for slug in ordered_slugs:
            s = stats[slug]
            lines.append(f"📱 {_platform_fa(slug)}")
            lines.append(f"✅ موفق: {s['success']} | ❌ ناموفق: {s['failed']}")
            lines.append("")
            total_success += s["success"]
            total_failed += s["failed"]

        if len(ordered_slugs) > 1:
            lines.append(f"📊 مجموع: ✅ {total_success} | ❌ {total_failed}")

        return "\n".join(lines).strip()


# ============================================================
# Dispatch
# ============================================================


def dispatch_job(job_id: int, progress_chat_id: str = None) -> dict:
    """پردازش یک جاب ارسال."""
    try:
        job = BroadcastJob.objects.select_related("message").get(pk=job_id)
    except BroadcastJob.DoesNotExist:
        logger.error(f"Job {job_id} not found.")
        return {"ok": False, "error": "Job not found"}

    if job.is_finished:
        return {"ok": False, "error": "Job already finished"}

    job.status = BroadcastJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    message = job.message
    all_targets = list(
        job.targets.filter(status=BroadcastTarget.Status.PENDING)
        .select_related("channel__platform")
    )

    bale_targets = [t for t in all_targets if t.channel.platform.slug == "bale"]
    non_bale_targets = [t for t in all_targets if t.channel.platform.slug != "bale"]

    context = {
        "bale_file_id": message.platform_file_ids.get("bale"),
        "downloaded_file_bytes": None,
    }

    tracker = None
    if progress_chat_id:
        try:
            bale_adapter = get_adapter("bale")
            if bale_adapter:
                tracker = ProgressTracker(bale_adapter, progress_chat_id)
        except Exception as e:
            logger.warning(f"Failed to init tracker: {e}")

    try:
        for target in bale_targets:
            _process_target(target, message, context=context, tracker=None)

        for target in non_bale_targets:
            _process_target(target, message, context=context, tracker=tracker)
    finally:
        job.recalculate_counts()
        if tracker:
            try:
                tracker.finish(job)
            except Exception as e:
                logger.exception(f"Failed to send final status: {e}")

    return {"ok": True, "job_id": job.pk, "status": job.status}


def _get_adapter_for_channel(channel):
    """دریافت آداپتور مناسب برای کانال."""
    slug = channel.platform.slug
    if slug == "eitaa":
        from product.forward.messengers.models import BotUser

        # 🔑 خواندن مستقیم از دیتابیس در هر بار صدا زدن
        eitaa_bot_user = BotUser.objects.filter(
            user=channel.user, platform=channel.platform
        ).first()

        # لاگ برای دیباگ دقیق
        logger.info(f"Fetching Eitaa token for user ID: {channel.user.id} ({channel.user.phone_number})")

        if not eitaa_bot_user:
            logger.error(f"No BotUser found for user {channel.user.id} on platform {channel.platform.slug}")
            raise MessengerAPIError(
                f"رکورد BotUser برای کاربر {channel.user.phone_number} در پلتفرم ایتا یافت نشد. "
                "لطفاً ابتدا از پنل وب توکن خود را ثبت کنید."
            )

        if not eitaa_bot_user.api_token:
            logger.error(f"BotUser found for user {channel.user.id} but api_token is EMPTY.")
            raise MessengerAPIError(
                f"توکن ایتایار برای کاربر {channel.user.phone_number} در دیتابیس خالی است. "
                "لطفاً از پنل وب ثبت کنید."
            )

        logger.info(f"Successfully fetched token from DB for user {channel.user.id}. Token starts with: {eitaa_bot_user.api_token[:6]}...")
        return get_adapter(slug, token=eitaa_bot_user.api_token)

    if slug == "rubika":
        from product.forward.messengers.models import BotUser

        rubika_bot_user = BotUser.objects.filter(
            user=channel.user, platform=channel.platform
        ).first()

        if not rubika_bot_user or not rubika_bot_user.has_rubika_session:
            raise MessengerAPIError(
                f"نشست روبیکا برای کاربر {channel.user.phone_number} ثبت یا تایید نشده است. "
                "لطفاً ابتدا از پنل وب وارد حساب روبیکای خود شوید."
            )

        session_data = rubika_bot_user.session_data or {}
        return get_adapter(
            slug,
            auth=session_data.get("auth"),
            private_key=session_data.get("private_key"),
        )

    if slug == "soroush":
        from product.forward.messengers.models import BotUser

        soroush_bot_user = BotUser.objects.filter(
            user=channel.user, platform=channel.platform
        ).first()

        if not soroush_bot_user or not soroush_bot_user.has_soroush_session:
            raise MessengerAPIError(
                f"نشست سروش‌پلاس برای کاربر {channel.user.phone_number} ثبت یا تایید نشده است. "
                "لطفاً ابتدا از پنل وب وارد حساب سروش‌پلاس خود شوید."
            )

        session_data = soroush_bot_user.session_data or {}
        return get_adapter(slug, session_string=session_data.get("string_session"))

    return get_adapter(slug)


def _process_target(target: BroadcastTarget, message, context=None, tracker=None) -> None:
    """ارسال پیام به یک کانال مشخص."""
    if context is None:
        context = {}

    try:
        target.status = BroadcastTarget.Status.RUNNING
        target.save(update_fields=["status"])

        platform_slug = target.channel.platform.slug
        from product.forward.subscriptions.access import user_has_platform_access

        if not user_has_platform_access(target.channel.user, platform_slug):
            target.mark_failed(f"اشتراک فعال وین فوروارد برای پلتفرم {_platform_fa(platform_slug)} وجود ندارد.")
            return

        adapter = _get_adapter_for_channel(target.channel)

        if not adapter:
            target.mark_failed(f"آداپتور پلتفرم {platform_slug} یافت نشد.")
            return

        # ==================== متن ====================
        if message.content_type == BroadcastMessage.ContentType.TEXT:
            result = adapter.send_text(target.channel.chat_id, message.text)
            target.mark_success(platform_message_id=result.get("message_id", ""))
            return

        # ==================== رسانه ====================
        cached_file_id = message.platform_file_ids.get(platform_slug)
        new_file_id_to_cache = None

        # ۱. file_id کش‌شده (فقط برای پلتفرم‌هایی که پشتیبانی می‌کنن مثل بله)
        if cached_file_id and platform_slug not in ("eitaa", "rubika", "soroush"):
            logger.info(f"[{platform_slug}] Using cached file_id for msg {message.pk}")
            result = adapter.send_media(
                target.channel.chat_id, message.content_type, None,
                message.text, file_id=cached_file_id,
            )

        # ۲. فایل فیزیکی (از پنل وب)
        elif message.file:
            if tracker:
                tracker.start_upload(platform_slug)
            logger.info(f"[{platform_slug}] Uploading physical file for msg {message.pk}")
            result = adapter.send_media(
                target.channel.chat_id, message.content_type, message.file,
                message.text, file_id=None,
            )
            new_file_id_to_cache = result.get("file_id")

        # ۳. فایل بین‌پلتفرمی (دانلود از بله)
        else:
            bale_file_id = context.get("bale_file_id")
            if not bale_file_id:
                target.mark_failed("file_id بله برای دانلود موجود نیست.")
                return

            # مرحله دانلود (فقط یک‌بار)
            if context.get("downloaded_file_bytes") is None:
                if tracker:
                    tracker.start_download()
                logger.info(f"[{platform_slug}] Downloading from bale for msg {message.pk}")
                context["downloaded_file_bytes"] = _download_external_file("bale", bale_file_id)

            downloaded_file_bytes = context["downloaded_file_bytes"]

            # 🔑 ارسال فایل بدون هیچ تبدیل و دستکاری (خود ایتا هندل می‌کند)
            if tracker:
                tracker.start_upload(platform_slug)

            logger.info(
                f"[{platform_slug}] Uploading {len(downloaded_file_bytes)} bytes for msg {message.pk}"
            )
            file_obj = ContentFile(downloaded_file_bytes, name=_make_filename(message))
            result = adapter.send_media(
                target.channel.chat_id, message.content_type, file_obj,
                message.text, file_id=None,
            )

        # کش file_id جدید (فقط برای پلتفرم‌های دارای file_id)
        if new_file_id_to_cache and not cached_file_id and platform_slug not in ("eitaa", "rubika", "soroush"):
            message.platform_file_ids[platform_slug] = new_file_id_to_cache
            message.save(update_fields=["platform_file_ids"])
            logger.info(f"[{platform_slug}] Cached file_id for msg {message.pk}")

        target.mark_success(platform_message_id=result.get("message_id", ""))

    except MessengerError as exc:
        logger.warning(f"Failed to send to {target.channel.title}: {exc}")
        target.mark_failed(str(exc))
    except Exception as exc:
        logger.exception(f"Unexpected error sending to {target.channel.title}")
        target.mark_failed(f"خطای غیرمنتظره: {exc}")