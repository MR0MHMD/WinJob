"""سرویس ارسال پیام (Dispatcher) — هسته اصلی وین فوروارد."""

import logging

import threading
from django.core.files.base import ContentFile
from django.db import close_old_connections
from django.utils import timezone

from product.forward.broadcast.models import BroadcastJob, BroadcastMessage, BroadcastTarget
from product.forward.messengers.adapters.registry import get_adapter
from product.forward.messengers.adapters.base import MessengerError, MessengerAPIError

logger = logging.getLogger(__name__)

_PLATFORM_FA_NAMES = {
    "bale": "بله",
    "eitaa": "ایتا",
    "telegram": "تلگرام",
    "soroush": "سروش‌پلاس",
    "rubika": "روبیکا",
}

_PLATFORM_ORDER = ["bale", "eitaa", "telegram", "rubika", "soroush"]


def _platform_fa(slug: str) -> str:
    return _PLATFORM_FA_NAMES.get(slug, slug)


def _download_external_file(source_platform: str, source_file_id: str) -> tuple[bytes, str]:
    """دانلود فایل از پلتفرم مبدا (بله یا تلگرام) و بازگرداندن بایت‌ها همراه با مسیر فایل."""
    if source_platform in ("bale", "telegram"):
        adapter = get_adapter(source_platform)
        if not adapter:
            raise MessengerAPIError(f"آداپتور «{_platform_fa(source_platform)}» ثبت نشده است.")
        file_info = adapter.get_file(source_file_id)
        file_path = (file_info or {}).get("file_path")
        if not file_path:
            raise MessengerAPIError(f"پاسخ getFile از {_platform_fa(source_platform)} فاقد file_path است.")
        return adapter.download_file(file_path), str(file_path)
    raise MessengerAPIError(f"دانلود از پلتفرم «{_platform_fa(source_platform)}» پشتیبانی نمی‌شود.")


def _make_filename(message, downloaded_file_path: str = "") -> str:
    """ساخت نام فایل با حفظ نام و پسوند اصلی فایل در صورت موجود بودن."""
    import os

    file_ids = message.platform_file_ids or {}
    saved_name = file_ids.get("bale_file_name") or file_ids.get("telegram_file_name") or ""
    saved_name = os.path.basename(str(saved_name).strip())
    if saved_name and "." in saved_name:
        return saved_name

    if downloaded_file_path and "." in os.path.basename(downloaded_file_path):
        real_ext = os.path.basename(downloaded_file_path).rsplit(".", 1)[-1].lower()
        if real_ext and len(real_ext) <= 8 and real_ext.isalnum():
            if saved_name:
                return f"{saved_name}.{real_ext}"
            return f"forwarded_{message.pk}.{real_ext}"

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
    if saved_name:
        return f"{saved_name}.{ext}"
    return f"forwarded_{message.pk}.{ext}"


class ProgressTracker:
    """مدیریت پیام وضعیت واحد که با تغییر مرحله ویرایش می‌شه."""

    def __init__(self, adapter, chat_id):
        self.adapter = adapter
        self.chat_id = chat_id
        self.message_id = None
        self._current_text = None

    def _update(self, text: str, parse_mode: str = None):
        if text == self._current_text:
            return
        self._current_text = text
        is_tg = getattr(self.adapter, "platform_slug", "") == "telegram"
        if self.message_id:
            try:
                if is_tg and parse_mode:
                    self.adapter.edit_message_text(self.chat_id, self.message_id, text, parse_mode=parse_mode)
                else:
                    self.adapter.edit_message_text(self.chat_id, self.message_id, text)
                return
            except Exception as e:
                logger.warning(f"edit_message_text failed, falling back to send: {e}")
                self.message_id = None
        try:
            if is_tg and parse_mode:
                result = self.adapter.send_text(self.chat_id, text, parse_mode=parse_mode)
            else:
                result = self.adapter.send_text(self.chat_id, text)
            self.message_id = result.get("message_id")
        except Exception as e:
            logger.warning(f"Failed to send progress message: {e}")

    def start_download(self, source_platform: str = "bale"):
        self._update(f"📥 در حال دانلود فایل از {_platform_fa(source_platform)}...")

    def start_upload(self, platform_slug: str = "eitaa"):
        self._update(f"📤 در حال آپلود فایل به {_platform_fa(platform_slug)}...")

    def finish(self, job):
        self._update(self._build_final_text(job), parse_mode="Markdown")

    @staticmethod
    def _build_final_text(job) -> str:
        total_targets = int(job.total_targets or job.targets.count())
        success_count = int(job.success_count or 0)
        if total_targets == 0:
            return "⚠️ هیچ کانالی برای ارسال وجود نداشت."

        if job.status == BroadcastJob.Status.DONE or (success_count == total_targets and total_targets > 0):
            status_label = "🟢 موفق"
        elif job.status == BroadcastJob.Status.PARTIAL or (0 < success_count < total_targets):
            status_label = "🟡 نیمه‌موفق"
        else:
            status_label = "🔴 ناموفق"

        spent = 0
        try:
            from product.forward.subscriptions.models import ForwardTokenTransaction

            spent = sum(
                abs(int(x))
                for x in ForwardTokenTransaction.objects.filter(
                    user=job.message.user,
                    tx_type=ForwardTokenTransaction.TxType.SPEND,
                    broadcast_job_id=job.pk,
                ).values_list("amount", flat=True)
            )
        except Exception:
            spent = 0

        report_url = job.get_public_report_url()
        return (
            "عملیات انجام شد ✅\n"
            f"وضعیت ارسال: {status_label}\n"
            f"ارسال موفق به *{success_count}* از {total_targets} کانال\n"
            f"تعداد توکن مصرفی: {spent:,}\n"
            f"[مشاهده تکمیلی]({report_url})"
        )


# ============================================================
# Dispatch
# ============================================================


def enqueue_dispatch_job(
    job_id: int,
    progress_chat_id: str = None,
    reaction_chat_id: str = None,
    reaction_message_id: int = None,
    reaction_platform: str = None,
) -> None:
    """قرار دادن عملیات ارسال همگانی در صف پس‌زمینه (سازگار با gevent و threading بدون نیاز به Redis).

    با اجرای غیرمسدودکننده، درخواست HTTP وب‌هوک بله و پنل وب بلافاصله آزاد می‌شود و از بروز خطای Timeout
    یا ارسال تکراری وب‌هوک جلوگیری می‌گردد.

    :param job_id: شناسه جاب ارسال (BroadcastJob.pk).
    :param progress_chat_id: شناسه چت کاربر در بله جهت ارسال و ویرایش پیام پیشرفت (اختیاری).
    """
    def _background_runner():
        close_old_connections()
        try:
            dispatch_job(job_id, progress_chat_id=progress_chat_id, reaction_chat_id=reaction_chat_id, reaction_message_id=reaction_message_id, reaction_platform=reaction_platform)
        except Exception as exc:
            logger.exception(f"Background dispatch_job failed for job {job_id}: {exc}")
        finally:
            close_old_connections()

    try:
        import gevent
        from gevent import monkey

        if monkey.is_module_patched("socket"):
            gevent.spawn(_background_runner)
            return
    except ImportError:
        pass

    worker_thread = threading.Thread(
        target=_background_runner,
        name=f"winforward-job-{job_id}",
        daemon=True,
    )
    worker_thread.start()


def dispatch_job(
    job_id: int,
    progress_chat_id: str = None,
    reaction_chat_id: str = None,
    reaction_message_id: int = None,
    reaction_platform: str = None,
) -> dict:
    """پردازش یک جاب ارسال همگانی به تمامی کانال‌های هدف."""
    close_old_connections()
    try:
        job = BroadcastJob.objects.select_related("message").get(pk=job_id)
    except BroadcastJob.DoesNotExist:
        logger.error(f"Job {job_id} not found.")
        return {"ok": False, "error": "Job not found"}

    if job.is_finished or job.status == BroadcastJob.Status.RUNNING:
        return {"ok": False, "error": "Job already running or finished"}

    job.status = BroadcastJob.Status.RUNNING
    job.started_at = timezone.now()
    job.total_targets = job.targets.count()
    job.save(update_fields=["status", "started_at", "total_targets"])

    message = job.message
    all_targets = list(
        job.targets.filter(status=BroadcastTarget.Status.PENDING)
        .select_related("channel__platform")
    )

    file_ids = message.platform_file_ids or {}
    source_platform = file_ids.get("source_platform") or ("telegram" if file_ids.get("telegram") and not file_ids.get("bale") else "bale")

    same_source_targets = [t for t in all_targets if t.channel.platform.slug == source_platform]
    cross_targets = [t for t in all_targets if t.channel.platform.slug != source_platform]

    context = {
        "source_platform": source_platform,
        "source_file_id": file_ids.get(source_platform) or file_ids.get("bale") or file_ids.get("telegram"),
        "downloaded_file_bytes": None,
        "downloaded_file_path": "",
        "rubika_file_inline": file_ids.get("rubika_file_inline"),
        "adapters": {},
    }

    tracker = None
    if progress_chat_id:
        try:
            tracker_adapter = get_adapter(source_platform)
            if tracker_adapter:
                tracker = ProgressTracker(tracker_adapter, progress_chat_id)
        except Exception as e:
            logger.warning(f"Failed to init tracker: {e}")

    try:
        for target in same_source_targets:
            _process_target(target, message, context=context, tracker=None)

        for target in cross_targets:
            _process_target(target, message, context=context, tracker=tracker)
    finally:
        job.recalculate_counts()
        if tracker:
            try:
                tracker.finish(job)
            except Exception as e:
                logger.warning(f"Failed to send final status to {progress_chat_id}: {e}")
        if reaction_chat_id and reaction_message_id and job.success_count > 0:
            try:
                r_adapter = get_adapter(reaction_platform or source_platform)
                if r_adapter and hasattr(r_adapter, "set_message_reaction"):
                    r_adapter.set_message_reaction(str(reaction_chat_id), int(reaction_message_id), "✅")
            except Exception as e:
                logger.debug(f"Failed to set reaction on hub message: {e}")

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
        return get_adapter(
            slug,
            string_session=session_data.get("string_session", ""),
            channel_hashes=session_data.get("channel_hashes") or {},
        )

    return get_adapter(slug)


def _process_target(target: BroadcastTarget, message, context=None, tracker=None) -> None:
    """ارسال پیام به یک کانال مشخص."""
    if context is None:
        context = {}

    try:
        target.status = BroadcastTarget.Status.RUNNING
        target.save(update_fields=["status"])

        platform_slug = target.channel.platform.slug
        from product.forward.subscriptions.access import get_user_token_balance
        from product.forward.subscriptions.services import (
            calculate_delivery_token_cost,
            deduct_tokens_atomic,
            get_max_file_size_bytes,
        )

        file_ids_meta = message.platform_file_ids or {}
        is_hub_msg = bool(file_ids_meta.get("hub_id"))
        use_ai_wm = bool(file_ids_meta.get("use_ai_watermark"))
        clean_text = (message.text or "").strip()
        has_caption = bool(clean_text)

        # ==================== سیاست اختصاصی سروش‌پلاس (فقط متن و کپشن · ۲ توکن) ====================
        if platform_slug == "soroush":
            if message.content_type in (
                BroadcastMessage.ContentType.STICKER,
                BroadcastMessage.ContentType.ANIMATION,
            ):
                target.mark_skipped("ارسال استیکر و گیف در سروش‌پلاس پشتیبانی نمی‌شود.")
                return

            if message.content_type != BroadcastMessage.ContentType.TEXT and not has_caption:
                target.mark_skipped("رسانه بدون کپشن به سروش‌پلاس ارسال نمی‌شود.")
                return

            soroush_unit_cost = calculate_delivery_token_cost(
                content_type=BroadcastMessage.ContentType.TEXT,
                has_caption=False,
                file_size_bytes=0,
                is_hub=is_hub_msg,
                use_ai_watermark=False,
            )
            if get_user_token_balance(target.channel.user) < soroush_unit_cost:
                target.mark_failed(f"موجودی توکن کافی نیست (نیاز به {soroush_unit_cost} توکن برای این کانال).")
                return

            adapter_key = (platform_slug, target.channel.user_id)
            adapter = context["adapters"].get(adapter_key)
            if adapter is None:
                adapter = _get_adapter_for_channel(target.channel)
                if adapter is not None:
                    context["adapters"][adapter_key] = adapter
            if not adapter:
                target.mark_failed("آداپتور پلتفرم سروش‌پلاس یافت نشد.")
                return

            send_body = message.text if message.content_type == BroadcastMessage.ContentType.TEXT else clean_text
            result = adapter.send_text(target.channel.chat_id, send_body)
            target.mark_success(platform_message_id=result.get("message_id", ""))
            desc_kind = "متن" if message.content_type == BroadcastMessage.ContentType.TEXT else "کپشن"
            deduct_tokens_atomic(
                target.channel.user,
                soroush_unit_cost,
                description=f"ارسال {desc_kind} به «{target.channel.title}» ({_platform_fa(platform_slug)})",
                broadcast_job_id=target.job_id,
            )
            return

        max_bytes = get_max_file_size_bytes()
        detected_size = int(file_ids_meta.get("file_size") or 0)
        if message.file:
            try:
                detected_size = int(message.file.size or detected_size)
            except Exception:
                pass
        if context.get("downloaded_file_bytes") is not None:
            detected_size = len(context["downloaded_file_bytes"])

        if detected_size > max_bytes:
            target.mark_failed(f"حجم فایل بیشتر از سقف مجاز ({max_bytes // (1024 * 1024)} مگابایت) است و ارسال نشد.")
            return

        unit_cost = calculate_delivery_token_cost(
            content_type=message.content_type,
            has_caption=has_caption,
            file_size_bytes=detected_size,
            is_hub=is_hub_msg,
            use_ai_watermark=use_ai_wm,
        )

        if get_user_token_balance(target.channel.user) < unit_cost:
            target.mark_failed(f"موجودی توکن کافی نیست (نیاز به {unit_cost} توکن برای این کانال).")
            return

        adapter_key = (platform_slug, target.channel.user_id)
        adapter = context["adapters"].get(adapter_key)
        if adapter is None:
            adapter = _get_adapter_for_channel(target.channel)
            if adapter is not None:
                context["adapters"][adapter_key] = adapter

        if not adapter:
            target.mark_failed(f"آداپتور پلتفرم {platform_slug} یافت نشد.")
            return

        # ==================== متن ====================
        if message.content_type == BroadcastMessage.ContentType.TEXT:
            result = adapter.send_text(target.channel.chat_id, message.text)
            target.mark_success(platform_message_id=result.get("message_id", ""))
            deduct_tokens_atomic(
                target.channel.user,
                unit_cost,
                description=f"ارسال متن به «{target.channel.title}» ({_platform_fa(platform_slug)})",
                broadcast_job_id=target.job_id,
            )
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
            rubika_cached = context.get("rubika_file_inline") if platform_slug == "rubika" else None
            result = adapter.send_media(
                target.channel.chat_id, message.content_type, message.file,
                message.text, file_id=rubika_cached,
            )
            if platform_slug == "rubika" and result.get("rubika_file_inline"):
                context["rubika_file_inline"] = result["rubika_file_inline"]
            new_file_id_to_cache = result.get("file_id")

        # ۳. فایل بین‌پلتفرمی (دانلود از مبدا بله یا تلگرام)
        else:
            source_platform = context.get("source_platform", "bale")
            source_file_id = context.get("source_file_id")
            if not source_file_id:
                target.mark_failed(f"file_id {_platform_fa(source_platform)} برای دانلود موجود نیست.")
                return

            # مرحله دانلود (فقط یک‌بار برای کل جاب)
            if context.get("downloaded_file_bytes") is None:
                if tracker:
                    tracker.start_download(source_platform)
                logger.info(f"[{platform_slug}] Downloading from {source_platform} for msg {message.pk}")
                file_bytes, remote_path = _download_external_file(source_platform, source_file_id)
                if len(file_bytes) > max_bytes:
                    target.mark_failed(f"حجم فایل بیشتر از سقف مجاز ({max_bytes // (1024 * 1024)} مگابایت) است و ارسال نشد.")
                    return
                context["downloaded_file_bytes"] = file_bytes
                context["downloaded_file_path"] = remote_path
                detected_size = len(file_bytes)
                unit_cost = calculate_delivery_token_cost(
                    content_type=message.content_type,
                    has_caption=has_caption,
                    file_size_bytes=detected_size,
                    is_hub=is_hub_msg,
                    use_ai_watermark=use_ai_wm,
                )
                if get_user_token_balance(target.channel.user) < unit_cost:
                    target.mark_failed(f"موجودی توکن کافی نیست (نیاز به {unit_cost} توکن برای این کانال).")
                    return

            downloaded_file_bytes = context["downloaded_file_bytes"]
            resolved_filename = _make_filename(message, context.get("downloaded_file_path", ""))

            # 🔑 ارسال فایل بدون هیچ تبدیل و دستکاری (خود ایتا هندل می‌کند)
            if tracker:
                tracker.start_upload(platform_slug)

            logger.info(
                f"[{platform_slug}] Uploading {len(downloaded_file_bytes)} bytes ({resolved_filename}) for msg {message.pk}"
            )
            send_content_type = message.content_type
            if send_content_type == "document" and resolved_filename.lower().endswith((".mp3", ".m4a", ".wav", ".flac", ".aac")):
                send_content_type = "audio"
            file_obj = ContentFile(downloaded_file_bytes, name=resolved_filename)
            rubika_cached = context.get("rubika_file_inline") if platform_slug == "rubika" else None
            result = adapter.send_media(
                target.channel.chat_id, send_content_type, file_obj,
                message.text, file_id=rubika_cached,
            )
            if platform_slug == "rubika" and result.get("rubika_file_inline"):
                context["rubika_file_inline"] = result["rubika_file_inline"]

        # کش file_id جدید (بله و متادیتای file_inline روبیکا)
        if platform_slug == "rubika" and context.get("rubika_file_inline") and not message.platform_file_ids.get("rubika_file_inline"):
            message.platform_file_ids["rubika_file_inline"] = context["rubika_file_inline"]
            message.save(update_fields=["platform_file_ids"])
            logger.info(f"[rubika] Persisted rubika_file_inline for msg {message.pk}")
        elif new_file_id_to_cache and not cached_file_id and platform_slug not in ("eitaa", "rubika"):
            message.platform_file_ids[platform_slug] = new_file_id_to_cache
            message.save(update_fields=["platform_file_ids"])
            logger.info(f"[{platform_slug}] Cached file_id for msg {message.pk}")

        target.mark_success(platform_message_id=result.get("message_id", ""))
        deduct_tokens_atomic(
            target.channel.user,
            unit_cost,
            description=f"ارسال {message.get_content_type_display()} به «{target.channel.title}» ({_platform_fa(platform_slug)})",
            broadcast_job_id=target.job_id,
        )

    except MessengerError as exc:
        logger.warning(f"Failed to send to {target.channel.title}: {exc}")
        target.mark_failed(str(exc))
    except Exception as exc:
        logger.exception(f"Unexpected error sending to {target.channel.title}")
        target.mark_failed(f"خطای غیرمنتظره: {exc}")
