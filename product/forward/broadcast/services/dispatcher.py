"""سرویس ارسال پیام (Dispatcher) — هسته اصلی وین فوروارد با اجرای دقیق و مرتب از بالا به پایین.

ترتیب فازهای اجرا در هر جاب:
1. فاز ۱ (پیش‌دانلود از مبدا): در صورت نیاز به فایل بین‌پلتفرمی، ابتدا یک‌بار از مبدا دانلود می‌شود.
2. فاز ۲ (امضای هوشمند AI): در صورت فعال بودن امضای AI روی حداقل یک کانال مقصد، یک‌بار پردازش و کش می‌شود.
3. فاز ۳ (ارسال به پلتفرم مبدا): بلافاصله با file_id کش‌شده (بدون آپلود مجدد فایل دانلودشده).
4. فاز ۴ (ارسال پشت‌سرهم به سایر پلتفرم‌ها): گروه‌بندی‌شده به ترتیب پلتفرم‌ها تا فاصله ارسال کانال‌ها حداقل باشد.
5. پاک‌سازی فوری مدیا: پس از پایان جاب، فایل فیزیکی آپلودشده از دیسک و فیلد دیتابیس فوراً پاک می‌شود.
"""

from __future__ import annotations

import logging
import os
import threading

from django.core.files.base import ContentFile
from django.db import close_old_connections
from django.utils import timezone

from product.forward.broadcast.models import BroadcastJob, BroadcastMessage, BroadcastTarget
from product.forward.broadcast.services.progress import ProgressTracker, platform_fa
from product.forward.messengers.adapters.base import MessengerAPIError, MessengerError
from product.forward.messengers.adapters.registry import get_adapter

logger = logging.getLogger(__name__)

_PLATFORM_ORDER = ["bale", "telegram", "rubika", "eitaa", "soroush"]


def _cleanup_uploaded_media(message: BroadcastMessage, current_job_id: int) -> None:
    """حذف فوری فایل فیزیکی آپلودشده از پنل وب پس از پایان ارسال (در صورت نبودن جاب فعال مشترک)."""
    if not message or not message.file:
        return

    has_other_active_job = (
        BroadcastJob.objects.filter(
            message_id=message.pk,
            status__in=[BroadcastJob.Status.PENDING, BroadcastJob.Status.RUNNING],
        )
        .exclude(pk=current_job_id)
        .exists()
    )
    if has_other_active_job:
        return

    file_name = getattr(message.file, "name", "")
    try:
        message.file.delete(save=False)
    except Exception as exc:
        logger.warning(
            "Failed to delete uploaded media '%s' for message %s: %s",
            file_name,
            message.pk,
            exc,
        )

    # استفاده از update مستقیم تا BroadcastMessage.clean() برای پیام‌های غیرمتنی خطا ندهد
    BroadcastMessage.objects.filter(pk=message.pk).update(file="")
    message.file = ""


def _download_external_file(source_platform: str, source_file_id: str) -> tuple[bytes, str]:
    """دانلود فایل از پلتفرم مبدا (بله یا تلگرام) و بازگرداندن بایت‌ها همراه با مسیر فایل."""
    if source_platform in ("bale", "telegram"):
        adapter = get_adapter(source_platform)
        if not adapter:
            raise MessengerAPIError(f"آداپتور «{platform_fa(source_platform)}» ثبت نشده است.")
        file_info = adapter.get_file(source_file_id)
        file_path = (file_info or {}).get("file_path")
        if not file_path:
            raise MessengerAPIError(f"پاسخ getFile از {platform_fa(source_platform)} فاقد file_path است.")
        return adapter.download_file(file_path), str(file_path)
    raise MessengerAPIError(f"دانلود از پلتفرم «{platform_fa(source_platform)}» پشتیبانی نمی‌شود.")


def _make_filename(message, downloaded_file_path: str = "") -> str:
    """ساخت نام فایل با حفظ نام و پسوند اصلی فایل در صورت موجود بودن."""
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
        "animation": "gif",
        "sticker": "webp",
    }
    ext = ext_map.get(message.content_type, "bin")
    if saved_name:
        return f"{saved_name}.{ext}"
    return f"forwarded_{message.pk}.{ext}"


def enqueue_dispatch_job(
    job_id: int,
    progress_chat_id: str = None,
    fallback_progress_chat_id: str = None,
    reaction_chat_id: str = None,
    reaction_message_id: int = None,
    reaction_platform: str = None,
) -> None:
    """قرار دادن عملیات ارسال همگانی در صف پس‌زمینه (سازگار با gevent و threading بدون نیاز به Redis)."""
    def _background_runner():
        close_old_connections()
        try:
            dispatch_job(
                job_id,
                progress_chat_id=progress_chat_id,
                fallback_progress_chat_id=fallback_progress_chat_id,
                reaction_chat_id=reaction_chat_id,
                reaction_message_id=reaction_message_id,
                reaction_platform=reaction_platform,
            )
        except Exception as exc:
            logger.exception("Background dispatch_job failed for job %s: %s", job_id, exc)
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
    fallback_progress_chat_id: str = None,
    reaction_chat_id: str = None,
    reaction_message_id: int = None,
    reaction_platform: str = None,
) -> dict:
    """پردازش منظم و مرحله‌به‌مرحله یک جاب ارسال همگانی (دانلود → امضای AI → ارسال به مبدا با file_id → سایر پلتفرم‌ها)."""
    close_old_connections()
    try:
        job = BroadcastJob.objects.select_related("message").get(pk=job_id)
    except BroadcastJob.DoesNotExist:
        logger.error("Job %s not found.", job_id)
        return {"ok": False, "error": "Job not found"}

    if job.is_finished or job.status == BroadcastJob.Status.RUNNING:
        return {"ok": False, "error": "Job already running or finished"}

    job.status = BroadcastJob.Status.RUNNING
    job.started_at = timezone.now()
    job.total_targets = job.targets.count()
    job.save(update_fields=["status", "started_at", "total_targets"])

    message = job.message
    all_targets = list(
        job.targets.filter(status=BroadcastTarget.Status.PENDING).select_related("channel__platform")
    )

    file_ids = message.platform_file_ids or {}
    source_platform = file_ids.get("source_platform") or (
        "telegram" if file_ids.get("telegram") and not file_ids.get("bale") else "bale"
    )
    source_file_id = file_ids.get(source_platform) or file_ids.get("bale") or file_ids.get("telegram")

    same_source_targets = [t for t in all_targets if t.channel.platform.slug == source_platform]
    cross_targets = [t for t in all_targets if t.channel.platform.slug != source_platform]

    # مرتب‌سازی مقاصد غیرمبدا بر اساس ترتیب یکسان پلتفرم‌ها تا خطوط برد زنده دقیقاً یکی‌یکی تیک بخورند
    cross_targets.sort(
        key=lambda t: (
            _PLATFORM_ORDER.index(t.channel.platform.slug)
            if t.channel.platform.slug in _PLATFORM_ORDER
            else 99
        )
    )
    ordered_targets = same_source_targets + cross_targets

    is_file_msg = message.content_type != BroadcastMessage.ContentType.TEXT
    has_text_for_ai = bool((message.text or "").strip()) and (
        message.content_type != BroadcastMessage.ContentType.STICKER
    )
    needs_ai = has_text_for_ai and any(
        (getattr(t.channel, "watermark_mode", "off") or "off") != "off"
        for t in ordered_targets
    )
    needs_download = (
        is_file_msg
        and (not message.file)
        and bool(source_file_id)
        and any(
            t.channel.platform.slug not in (source_platform, "soroush")
            and not file_ids.get(t.channel.platform.slug)
            for t in cross_targets
        )
    )

    context = {
        "source_platform": source_platform,
        "source_file_id": source_file_id,
        "downloaded_file_bytes": None,
        "downloaded_file_path": "",
        "download_error": "",
        "rubika_file_inline": file_ids.get("rubika_file_inline"),
        "adapters": {},
    }

    tracker = None
    if progress_chat_id and ordered_targets:
        try:
            tracker_adapter = get_adapter(source_platform)
            if tracker_adapter:
                platform_totals: dict[str, int] = {}
                for t in ordered_targets:
                    pslug = t.channel.platform.slug
                    platform_totals[pslug] = platform_totals.get(pslug, 0) + 1
                tracker = ProgressTracker(
                    tracker_adapter,
                    progress_chat_id,
                    fallback_chat_id=fallback_progress_chat_id,
                    hub_title=str(file_ids.get("hub_title") or ""),
                    hub_sender_name=str(file_ids.get("hub_sender_name") or ""),
                    is_file_msg=is_file_msg,
                    source_platform=source_platform,
                    needs_download=needs_download,
                    needs_ai=needs_ai,
                    platform_totals=platform_totals,
                )
                tracker.start()
        except Exception as exc:
            logger.warning("Failed to init tracker: %s", exc)

    try:
        # ── فاز ۱: دانلود فایل از پلتفرم مبدا پیش از شروع ارسال به هر کانالی ──
        if needs_download:
            from product.forward.subscriptions.services import get_max_file_size_bytes

            max_bytes = get_max_file_size_bytes()
            if tracker:
                tracker.start_download(source_platform)
            try:
                file_bytes, remote_path = _download_external_file(source_platform, source_file_id)
                if len(file_bytes) > max_bytes:
                    context["download_error"] = (
                        f"حجم فایل بیشتر از سقف مجاز ({max_bytes // (1024 * 1024)} مگابایت) است و ارسال نشد."
                    )
                    if tracker:
                        tracker.finish_download(ok=False)
                else:
                    context["downloaded_file_bytes"] = file_bytes
                    context["downloaded_file_path"] = remote_path
                    if tracker:
                        tracker.finish_download(ok=True)
            except Exception as exc:
                logger.warning("Pre-download from %s failed for job %s: %s", source_platform, job.pk, exc)
                context["download_error"] = f"خطا در دانلود فایل از {platform_fa(source_platform)}: {exc}"
                if tracker:
                    tracker.finish_download(ok=False)

        # ── فاز ۲: پردازش یک‌باره امضای هوشمند AI پیش از ارسال به کانال‌ها ──
        if needs_ai:
            from product.forward.broadcast.services.ai_watermark import analyze_text_watermark

            if tracker:
                tracker.start_ai()
            ai_res = analyze_text_watermark(message.text or "")
            context["ai_watermark_result"] = ai_res
            if tracker:
                tracker.finish_ai(ok=bool(ai_res.get("ok")))

        # ── فاز ۳: ارسال به کانال‌های پلتفرم مبدا (فقط با file_id و بدون آپلود مجدد) ──
        for target in same_source_targets:
            _process_target(target, message, context=context, tracker=tracker)

        # ── فاز ۴: ارسال ترتیبی و پشت‌سرهم به سایر پلتفرم‌ها ──
        for target in cross_targets:
            _process_target(target, message, context=context, tracker=tracker)
    finally:
        job.recalculate_counts()
        _cleanup_uploaded_media(message, job.pk)
        if tracker:
            try:
                tracker.finish(job)
            except Exception as exc:
                logger.warning("Failed to send final status to %s: %s", progress_chat_id, exc)
        if reaction_chat_id and reaction_message_id and job.success_count > 0:
            try:
                r_adapter = get_adapter(reaction_platform or source_platform)
                if r_adapter and hasattr(r_adapter, "set_message_reaction"):
                    r_adapter.set_message_reaction(str(reaction_chat_id), int(reaction_message_id), "✅")
            except Exception as exc:
                logger.debug("Failed to set reaction on hub message: %s", exc)

    return {"ok": True, "job_id": job.pk, "status": job.status}


def _get_adapter_for_channel(channel):
    """دریافت آداپتور مناسب برای کانال."""
    from product.forward.messengers.models import BotUser

    slug = channel.platform.slug
    if slug == "eitaa":
        eitaa_bot_user = BotUser.objects.filter(user=channel.user, platform=channel.platform).first()
        if not eitaa_bot_user or not eitaa_bot_user.api_token:
            raise MessengerAPIError(
                f"توکن ایتایار برای کاربر {channel.user.phone_number} ثبت نشده است. "
                "لطفاً ابتدا از پنل وب توکن خود را ثبت کنید."
            )
        return get_adapter(slug, token=eitaa_bot_user.api_token)

    if slug == "rubika":
        rubika_bot_user = BotUser.objects.filter(user=channel.user, platform=channel.platform).first()
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
        soroush_bot_user = BotUser.objects.filter(user=channel.user, platform=channel.platform).first()
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
    """ارسال پیام به یک کانال مشخص با استفاده از خروجی آماده فازهای دانلود و امضای AI."""
    if context is None:
        context = {}

    platform_slug = target.channel.platform.slug
    outcome = "failed"
    try:
        target.status = BroadcastTarget.Status.RUNNING
        target.save(update_fields=["status"])

        from product.forward.subscriptions.access import get_user_token_balance
        from product.forward.subscriptions.services import (
            calculate_delivery_token_cost,
            deduct_tokens_atomic,
            get_max_file_size_bytes,
        )

        file_ids_meta = message.platform_file_ids or {}
        is_hub_msg = bool(file_ids_meta.get("hub_id"))
        clean_text = (message.text or "").strip()
        has_caption = bool(clean_text)

        # اعمال خروجی کش‌شده امضای هوشمند AI (در فاز ۲ تولید شده است)
        channel_wm_mode = getattr(target.channel, "watermark_mode", "off") or "off"
        wants_ai_wm = (
            (channel_wm_mode != "off")
            and has_caption
            and (message.content_type != BroadcastMessage.ContentType.STICKER)
        )
        ai_applied = False
        effective_text = message.text or ""

        if wants_ai_wm:
            from product.forward.broadcast.services.ai_watermark import (
                analyze_text_watermark,
                apply_channel_watermark,
            )

            if "ai_watermark_result" not in context:
                context["ai_watermark_result"] = analyze_text_watermark(message.text or "")
            ai_res = context["ai_watermark_result"]
            if ai_res.get("ok"):
                max_len = (
                    4096
                    if (message.content_type == BroadcastMessage.ContentType.TEXT or platform_slug == "soroush")
                    else 1024
                )
                effective_text = apply_channel_watermark(
                    message.text or "", target.channel, ai_res, max_length=max_len
                )
                ai_applied = True

        use_ai_wm = ai_applied

        # ==================== سیاست اختصاصی سروش‌پلاس (فقط متن و کپشن) ====================
        if platform_slug == "soroush":
            if message.content_type in (
                BroadcastMessage.ContentType.STICKER,
                BroadcastMessage.ContentType.ANIMATION,
            ):
                target.mark_skipped("ارسال استیکر و گیف در سروش‌پلاس پشتیبانی نمی‌شود.")
                outcome = "skipped"
                return

            if message.content_type != BroadcastMessage.ContentType.TEXT and not has_caption:
                target.mark_skipped("رسانه بدون کپشن به سروش‌پلاس ارسال نمی‌شود.")
                outcome = "skipped"
                return

            soroush_unit_cost = calculate_delivery_token_cost(
                content_type=BroadcastMessage.ContentType.TEXT,
                has_caption=False,
                file_size_bytes=0,
                is_hub=is_hub_msg,
                use_ai_watermark=use_ai_wm,
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

            if tracker:
                tracker.start_platform_target(platform_slug)
            send_body = effective_text if message.content_type == BroadcastMessage.ContentType.TEXT else effective_text.strip()
            result = adapter.send_text(target.channel.chat_id, send_body)
            target.mark_success(platform_message_id=result.get("message_id", ""))
            outcome = "success"
            desc_kind = "متن" if message.content_type == BroadcastMessage.ContentType.TEXT else "کپشن"
            ai_suffix = " + امضای AI" if use_ai_wm else ""
            deduct_tokens_atomic(
                target.channel.user,
                soroush_unit_cost,
                description=f"ارسال {desc_kind}{ai_suffix} به «{target.channel.title}» ({platform_fa(platform_slug)})",
                broadcast_job_id=target.job_id,
            )
            return

        # ==================== سایر پلتفرم‌ها (بله، تلگرام، ایتا، روبیکا) ====================
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

        # متن ساده
        if message.content_type == BroadcastMessage.ContentType.TEXT:
            if tracker:
                tracker.start_platform_target(platform_slug)
            result = adapter.send_text(target.channel.chat_id, effective_text)
            target.mark_success(platform_message_id=result.get("message_id", ""))
            outcome = "success"
            ai_suffix = " + امضای AI" if use_ai_wm else ""
            deduct_tokens_atomic(
                target.channel.user,
                unit_cost,
                description=f"ارسال متن{ai_suffix} به «{target.channel.title}» ({platform_fa(platform_slug)})",
                broadcast_job_id=target.job_id,
            )
            return

        # رسانه
        cached_file_id = message.platform_file_ids.get(platform_slug)
        new_file_id_to_cache = None

        # ۱. file_id کش‌شده (اولویت اول برای پلتفرم مبدا — بدون آپلود مجدد فایل دانلودشده)
        if cached_file_id and platform_slug not in ("eitaa", "rubika", "soroush"):
            if tracker:
                tracker.start_platform_target(platform_slug)
            result = adapter.send_media(
                target.channel.chat_id,
                message.content_type,
                None,
                effective_text,
                file_id=cached_file_id,
            )

        # ۲. فایل فیزیکی آپلودشده از پنل وب
        elif message.file:
            if tracker:
                tracker.start_platform_target(platform_slug)
            rubika_cached = context.get("rubika_file_inline") if platform_slug == "rubika" else None
            result = adapter.send_media(
                target.channel.chat_id,
                message.content_type,
                message.file,
                effective_text,
                file_id=rubika_cached,
            )
            if platform_slug == "rubika" and result.get("rubika_file_inline"):
                context["rubika_file_inline"] = result["rubika_file_inline"]
            new_file_id_to_cache = result.get("file_id")

        # ۳. فایل بین‌پلتفرمی (قبلاً در فاز ۱ دانلود و در context ذخیره شده است)
        else:
            if context.get("download_error"):
                target.mark_failed(context["download_error"])
                return

            if context.get("downloaded_file_bytes") is None:
                source_platform = context.get("source_platform", "bale")
                source_file_id = context.get("source_file_id")
                if not source_file_id:
                    target.mark_failed(f"file_id {platform_fa(source_platform)} برای دانلود موجود نیست.")
                    return
                file_bytes, remote_path = _download_external_file(source_platform, source_file_id)
                if len(file_bytes) > max_bytes:
                    target.mark_failed(f"حجم فایل بیشتر از سقف مجاز ({max_bytes // (1024 * 1024)} مگابایت) است و ارسال نشد.")
                    return
                context["downloaded_file_bytes"] = file_bytes
                context["downloaded_file_path"] = remote_path

            downloaded_file_bytes = context["downloaded_file_bytes"]
            resolved_filename = _make_filename(message, context.get("downloaded_file_path", ""))

            if tracker:
                tracker.start_platform_target(platform_slug)

            send_content_type = message.content_type
            if send_content_type == "document" and resolved_filename.lower().endswith(
                (".mp3", ".m4a", ".wav", ".flac", ".aac")
            ):
                send_content_type = "audio"
            file_obj = ContentFile(downloaded_file_bytes, name=resolved_filename)
            rubika_cached = context.get("rubika_file_inline") if platform_slug == "rubika" else None
            result = adapter.send_media(
                target.channel.chat_id,
                send_content_type,
                file_obj,
                effective_text,
                file_id=rubika_cached,
            )
            if platform_slug == "rubika" and result.get("rubika_file_inline"):
                context["rubika_file_inline"] = result["rubika_file_inline"]

        if (
            platform_slug == "rubika"
            and context.get("rubika_file_inline")
            and not message.platform_file_ids.get("rubika_file_inline")
        ):
            message.platform_file_ids["rubika_file_inline"] = context["rubika_file_inline"]
            message.save(update_fields=["platform_file_ids"])
        elif new_file_id_to_cache and not cached_file_id and platform_slug not in ("eitaa", "rubika"):
            message.platform_file_ids[platform_slug] = new_file_id_to_cache
            message.save(update_fields=["platform_file_ids"])

        target.mark_success(platform_message_id=result.get("message_id", ""))
        outcome = "success"
        ai_suffix = " + امضای AI" if use_ai_wm else ""
        deduct_tokens_atomic(
            target.channel.user,
            unit_cost,
            description=f"ارسال {message.get_content_type_display()}{ai_suffix} به «{target.channel.title}» ({platform_fa(platform_slug)})",
            broadcast_job_id=target.job_id,
        )

    except MessengerError as exc:
        logger.warning("Failed to send to %s: %s", target.channel.title, exc)
        target.mark_failed(str(exc))
        outcome = "failed"
    except Exception as exc:
        logger.exception("Unexpected error sending to %s", target.channel.title)
        target.mark_failed(f"خطای غیرمنتظره: {exc}")
        outcome = "failed"
    finally:
        if tracker:
            tracker.complete_platform_target(platform_slug, outcome)
