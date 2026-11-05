"""سرویس ارسال پیام (Dispatcher) — هسته اصلی وین فوروارد."""

import logging

from django.utils import timezone
from product.forward.broadcast.models import BroadcastJob, BroadcastMessage, BroadcastTarget
from product.forward.messengers.adapters.base import MessengerError
from product.forward.messengers.adapters.registry import get_adapter

logger = logging.getLogger(__name__)


def dispatch_job(job_id: int) -> dict:
    """
    پردازش یک جاب ارسال (فعلاً به صورت Eager و بدون Celery).
    برای هر Target، پیام را ارسال می‌کند و وضعیت را ذخیره می‌کند.
    """
    try:
        job = BroadcastJob.objects.select_related("message").get(pk=job_id)
    except BroadcastJob.DoesNotExist:
        logger.error(f"Job {job_id} not found.")
        return {"ok": False, "error": "Job not found"}

    if job.is_finished:
        return {"ok": False, "error": "Job already finished"}

    # شروع جاب
    job.status = BroadcastJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    message = job.message
    targets = job.targets.filter(status=BroadcastTarget.Status.PENDING).select_related("channel__platform")

    for target in targets:
        _process_target(target, message)

    # بازشماری نهایی
    job.recalculate_counts()

    return {"ok": True, "job_id": job.pk, "status": job.status}


def _process_target(target: BroadcastTarget, message) -> None:
    """ارسال پیام به یک کانال مشخص و ثبت نتیجه (با پشتیبانی از file_id بدون فایل فیزیکی)."""
    try:
        target.status = BroadcastTarget.Status.RUNNING
        target.save(update_fields=["status"])

        platform_slug = target.channel.platform.slug
        adapter = get_adapter(platform_slug)

        if not adapter:
            target.mark_failed(f"آداپتور پلتفرم {platform_slug} یافت نشد.")
            return

        # ارسال متن
        if message.content_type == BroadcastMessage.ContentType.TEXT:
            result = adapter.send_text(target.channel.chat_id, message.text)

        # ارسال رسانه (عکس/ویدیو/فایل)
        else:
            cached_file_id = message.platform_file_ids.get(platform_slug)

            # 🔑 شرط حیاتی: یا فایل فیزیکی داریم یا file_id از پلتفرم
            if not message.file and not cached_file_id:
                target.mark_failed("نه فایل فیزیکی و نه file_id برای این پیام موجود نیست.")
                return

            result = adapter.send_media(
                target.channel.chat_id,
                message.content_type,
                message.file,          # می‌تونه None باشه
                message.text,
                file_id=cached_file_id,
            )

            # ذخیره file_id جدید برای ارسال‌های بعدی
            new_file_id = result.get("file_id")
            if new_file_id and not cached_file_id:
                message.platform_file_ids[platform_slug] = new_file_id
                message.save(update_fields=["platform_file_ids"])
                logger.info(f"File ID cached for message {message.pk} on {platform_slug}")

        target.mark_success(platform_message_id=result.get("message_id", ""))

    except MessengerError as exc:
        logger.warning(f"Failed to send to {target.channel.title}: {exc}")
        target.mark_failed(str(exc))
    except Exception as exc:
        logger.exception(f"Unexpected error sending to {target.channel.title}")
        target.mark_failed(f"خطای غیرمنتظره: {exc}")
