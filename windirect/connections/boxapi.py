"""سرویس تعامل با BoxAPI برای ارسال پاسخ به کامنت و دایرکت."""

import logging
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_base_url() -> str:
    """آدرس پایه‌ی BoxAPI را برمی‌گرداند."""
    return getattr(settings, "BOXAPI_BASE_URL", "https://api.sendbox.chat/api/v1")


def _get_api_key() -> str:
    """کلید API را برمی‌گرداند."""
    return getattr(settings, "BOXAPI_API_KEY", "")


def _post_action(action: str, payload: dict) -> Optional[dict]:
    """
    درخواست POST به اکشن BoxAPI می‌فرستد.

    Args:
        action: نام اکشن (مثلاً reply_comment)
        payload: بدنه‌ی درخواست (JSON)

    Returns:
        dict: پاسخ JSON یا None در صورت خطا
    """
    api_key = _get_api_key()
    if not api_key:
        logger.error("❌ BoxAPI API key missing")
        return None

    url = f"{_get_base_url()}/service/actions/{action}"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }

    logger.warning(
        "📤 BoxAPI POST | action=%s | url=%s | payload=%s",
        action, url, payload,
    )

    try:
        response = requests.post(
            url, headers=headers, json=payload, timeout=15,
        )
        logger.warning(
            "📥 BoxAPI RESPONSE | action=%s | status=%s | body=%s",
            action, response.status_code, response.text[:500],
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as exc:
        logger.error(
            "❌ BoxAPI HTTP error | action=%s | status=%s | body=%s",
            action, response.status_code, response.text[:500],
        )
        return None
    except requests.exceptions.RequestException as exc:
        logger.exception("❌ BoxAPI request failed | action=%s | error=%s", action, exc)
        return None
    except ValueError:
        logger.exception("❌ BoxAPI response not JSON | action=%s", action)
        return None


def reply_to_comment(account_id: str, comment_id: str, message: str) -> bool:
    """
    پاسخ به یک کامنت را در همان کامنت ارسال می‌کند.

    Args:
        account_id: شناسه‌ی پیج
        comment_id: شناسه‌ی کامنت
        message: متن پاسخ

    Returns:
        bool: موفقیت یا عدم موفقیت
    """
    logger.warning(
        "💬 reply_to_comment | account_id=%s | comment_id=%s | message_len=%s",
        account_id, comment_id, len(message),
    )
    payload = {
        "account_id": account_id,
        "comment_id": comment_id,
        "message": message,
    }
    result = _post_action("reply_comment", payload)
    if result and result.get("success"):
        logger.warning("✅ Comment reply sent | comment_id=%s", comment_id)
        return True
    logger.error("❌ Comment reply failed | comment_id=%s | result=%s", comment_id, result)
    return False


def send_private_reply(account_id: str, comment_id: str, message: str, buttons: list = None, quick_replies: list = None, ):
    """
    به کامنت‌کننده دایرکت (پیام خصوصی) ارسال می‌کند.

    ⚠️ محدودیت: فقط تا ۷ روز پس از ثبت کامنت.
    ⚠️ این متد فقط برای «اولین» پیام به کاربریه.
    برای ادامه‌ی مکالمه از send_message استفاده کن.

    Args:
        account_id: شناسه‌ی پیج
        comment_id: شناسه‌ی کامنت
        message: متن پیام
        buttons: آرایه‌ای از دکمه‌ها (اختیاری)
        quick_replies: آرایه‌ای از پاسخ‌های سریع (اختیاری)

    Returns:
        bool: موفقیت یا عدم موفقیت
    """
    logger.warning(
        "📩 send_private_reply | account_id=%s | comment_id=%s | message_len=%s | "
        "buttons=%s | quick_replies=%s",
        account_id, comment_id, len(message),
        len(buttons) if buttons else 0,
        len(quick_replies) if quick_replies else 0,
    )

    payload = {
        "account_id": account_id,
        "comment_id": comment_id,
        "message": message,
    }

    if buttons:
        payload["buttons"] = buttons
    if quick_replies:
        payload["quick_replies"] = quick_replies

    result = _post_action("private_reply", payload)

    if result and result.get("success"):
        logger.warning("✅ Private reply sent | comment_id=%s", comment_id)
        return True

    logger.error(
        "❌ Private reply failed | comment_id=%s | result=%s",
        comment_id, result,
    )
    return False


def request_list_posts(account_id: str, fields: list = None, limit: int = 12) -> bool:
    """
    درخواست لیست پست‌های پیج از BoxAPI.

    ⚠️ پاسخ آسنکرون هست و از طریق Webhook میاد.

    Args:
        account_id: شناسه‌ی پیج
        fields: لیست فیلدهای موردنیاز
        limit: تعداد پست

    Returns:
        bool: موفقیت ثبت درخواست
    """
    if not fields:
        fields = ["id", "media_type", "media_url", "permalink", "caption", "timestamp"]

    logger.warning(
        "📸 request_list_posts | account_id=%s | limit=%s | fields=%s",
        account_id, limit, fields,
    )

    payload = {
        "account_id": account_id,
        "fields": fields,
        "limit": limit,
    }
    result = _post_action("list_posts", payload)

    if result and result.get("success"):
        logger.warning(
            "✅ list_posts request accepted | event_id=%s",
            (result.get("data") or {}).get("event_id"),
        )
        return True

    logger.error("❌ list_posts request failed | result=%s", result)
    return False


def get_follow_status(account_id: str, customer_id: str) -> bool:
    """
    درخواست بررسی وضعیت فالو یک کاربر نسبت به پیج.

    ⚠️ آسنکرون: نتیجه از طریق Webhook (event_type=action.follow_status) میاد.

    Args:
        account_id: شناسه‌ی پیج (UUID از BoxAPI)
        customer_id: شناسه‌ی کاربر کامنت‌کننده (data.from.id از Webhook)

    Returns:
        bool: موفقیت ثبت درخواست (نه نتیجه‌ی فالو)
    """
    logger.warning(
        "👤 get_follow_status | account_id=%s | customer_id=%s",
        account_id, customer_id,
    )

    payload = {
        "account_id": account_id,
        "customer_id": customer_id,
    }

    result = _post_action("follow_status", payload)

    if result and result.get("success"):
        logger.warning(
            "✅ follow_status request accepted | customer_id=%s | event_id=%s",
            customer_id,
            (result.get("data") or {}).get("event_id"),
        )
        return True

    logger.error(
        "❌ follow_status request failed | customer_id=%s | result=%s",
        customer_id, result,
    )
    return False


def send_message(account_id: str, recipient_id: str, message: str, buttons: list = None, quick_replies: list = None, ):
    """
    ارسال پیام دایرکت به یک کاربر.

    Args:
        account_id: شناسه‌ی پیج (UUID از BoxAPI)
        recipient_id: شناسه‌ی گیرنده (sender.id از Webhook یا from.id از کامنت)
        message: متن پیام
        buttons: آرایه‌ای از دکمه‌ها (اختیاری)
            هر دکمه: {"type": "postback", "title": "...", "payload": "..."}
            یا {"type": "web_url", "title": "...", "url": "..."}
        quick_replies: آرایه‌ای از پاسخ‌های سریع (اختیاری)

    Returns:
        bool: موفقیت یا عدم موفقیت
    """
    logger.warning(
        "📨 send_message | account_id=%s | recipient_id=%s | message_len=%s | "
        "buttons=%s | quick_replies=%s",
        account_id, recipient_id, len(message),
        len(buttons) if buttons else 0,
        len(quick_replies) if quick_replies else 0,
    )

    payload = {
        "account_id": account_id,
        "recipient_id": recipient_id,
        "message": message,
    }

    if buttons:
        payload["buttons"] = buttons

    if quick_replies:
        payload["quick_replies"] = quick_replies

    result = _post_action("send_message", payload)

    if result and result.get("success"):
        logger.warning("✅ Message sent | recipient_id=%s", recipient_id)
        return True

    logger.error(
        "❌ Message send failed | recipient_id=%s | result=%s",
        recipient_id, result,
    )
    return False


def upload_file(username: str, file_obj, file_type: str = None) -> Optional[dict]:
    """
    آپلود فایل به فضای ابری BoxAPI.

    Args:
        username: نام کاربری پیج (مثل winjob_ir)
        file_obj: فایل (Django UploadedFile یا file object)
        file_type: MIME type (اختیاری، مثل image/jpeg)

    Returns:
        dict: {
            "success": bool,
            "url": str|None,
            "file_id": str|None,
            "raw": dict|None,
        }
    """
    api_key = _get_api_key()
    if not api_key:
        logger.error("❌ BoxAPI API key missing")
        return {"success": False, "url": None, "file_id": None, "raw": None}

    url = f"{_get_base_url()}/service/uploads"
    headers = {
        "X-Api-Key": api_key,
        # ⚠️ Content-Type رو نمی‌ذاریم، چون requests خودش multipart/form-data رو ست می‌کنه
    }

    # ==================== آماده‌سازی فایل ====================
    files = {
        "file": (
            getattr(file_obj, "name", "file"),
            file_obj,
            file_type or getattr(file_obj, "content_type", "application/octet-stream"),
        ),
    }

    data = {
        "username": username,
    }

    if file_type:
        data["type"] = file_type

    logger.warning(
        "📤 BoxAPI UPLOAD | url=%s | username=%s | filename=%s | size=%s | type=%s",
        url, username,
        getattr(file_obj, "name", "?"),
        getattr(file_obj, "size", "?"),
        file_type or "auto",
    )

    try:
        response = requests.post(
            url, headers=headers, files=files, data=data, timeout=60,
        )
        logger.warning(
            "📥 BoxAPI UPLOAD RESPONSE | status=%s | body=%s",
            response.status_code, response.text[:500],
        )
        response.raise_for_status()
        result = response.json()
    except requests.exceptions.HTTPError:
        logger.error(
            "❌ BoxAPI upload HTTP error | status=%s | body=%s",
            response.status_code, response.text[:500],
        )
        return {"success": False, "url": None, "file_id": None, "raw": None}
    except requests.exceptions.RequestException as exc:
        logger.exception("❌ BoxAPI upload request failed | error=%s", exc)
        return {"success": False, "url": None, "file_id": None, "raw": None}
    except ValueError:
        logger.exception("❌ BoxAPI upload response not JSON")
        return {"success": False, "url": None, "file_id": None, "raw": None}

    # ==================== استخراج URL و ID ====================
    # ساختار احتمالی:
    # {"success": true, "data": {"id": "...", "url": "https://dl.sendbox.chat/uploads/..."}}
    data_resp = result.get("data") or {}

    file_url = (
        data_resp.get("url")
        or data_resp.get("file_url")
        or result.get("url")
    )
    file_id = (
        data_resp.get("id")
        or data_resp.get("file_id")
        or data_resp.get("uuid")
    )

    if not result.get("success") or not file_url:
        logger.error(
            "❌ BoxAPI upload failed | success=%s | url=%s | raw=%s",
            result.get("success"), file_url, result,
        )
        return {"success": False, "url": None, "file_id": file_id, "raw": result}

    logger.warning(
        "✅ BoxAPI upload success | file_id=%s | url=%s",
        file_id, file_url,
    )
    return {
        "success": True,
        "url": file_url,
        "file_id": file_id,
        "raw": result,
    }


def delete_file(file_id: str) -> bool:
    """
    حذف فایل از فضای ابری BoxAPI.

    Args:
        file_id: UUID فایل در BoxAPI

    Returns:
        bool: موفقیت یا عدم موفقیت
    """
    if not file_id:
        logger.warning("⚠️ delete_file: no file_id")
        return False

    api_key = _get_api_key()
    if not api_key:
        logger.error("❌ BoxAPI API key missing")
        return False

    url = f"{_get_base_url()}/service/uploads/{file_id}"
    headers = {"X-Api-Key": api_key}

    logger.warning("🗑️ BoxAPI DELETE FILE | url=%s", url)

    try:
        response = requests.delete(url, headers=headers, timeout=15)
        logger.warning(
            "📥 BoxAPI DELETE RESPONSE | status=%s | body=%s",
            response.status_code, response.text[:300],
        )
        response.raise_for_status()
        result = response.json()
    except requests.exceptions.RequestException as exc:
        logger.exception("❌ BoxAPI delete file failed | error=%s", exc)
        return False
    except ValueError:
        logger.exception("❌ BoxAPI delete response not JSON")
        return False

    if result.get("success"):
        logger.warning("✅ File deleted from BoxAPI | file_id=%s", file_id)
        return True

    logger.error("❌ File delete failed | file_id=%s | result=%s", file_id, result)
    return False


def send_attachment(account_id: str, recipient_id: str, attachment_type: str, url: str, ):
    """
    ارسال فایل چندرسانه‌ای (صوت/ویدیو/PDF) در دایرکت.

    Args:
        account_id: شناسه‌ی پیج (UUID از BoxAPI)
        recipient_id: شناسه‌ی گیرنده
        attachment_type: نوع فایل: audio, video, file
        url: URL فایل (از BoxAPI uploads)

    Returns:
        bool: موفقیت یا عدم موفقیت
    """
    logger.warning(
        "📎 send_attachment | account_id=%s | recipient_id=%s | type=%s | url=%s",
        account_id, recipient_id, attachment_type, url[:80] if url else "",
    )

    payload = {
        "account_id": account_id,
        "recipient_id": recipient_id,
        "attachment_type": attachment_type,
        "url": url,
    }

    result = _post_action("send_attachment", payload)

    if result and result.get("success"):
        logger.warning("✅ Attachment sent | recipient_id=%s", recipient_id)
        return True

    logger.error(
        "❌ Attachment send failed | recipient_id=%s | result=%s",
        recipient_id, result,
    )
    return False


def send_image( account_id: str, recipient_id: str, images: list, ):
    """
    ارسال تصویر (۱ تا ۱۰ تا) در دایرکت.

    Args:
        account_id: شناسه‌ی پیج (UUID از BoxAPI)
        recipient_id: شناسه‌ی گیرنده
        images: آرایه‌ای از dict: [{"url": "https://..."}, ...]

    Returns:
        bool: موفقیت یا عدم موفقیت
    """
    logger.warning(
        "🖼️ send_image | account_id=%s | recipient_id=%s | count=%s",
        account_id, recipient_id, len(images) if images else 0,
    )

    payload = {
        "account_id": account_id,
        "recipient_id": recipient_id,
        "images": images,
    }

    result = _post_action("send_image", payload)

    if result and result.get("success"):
        logger.warning("✅ Image sent | recipient_id=%s", recipient_id)
        return True

    logger.error(
        "❌ Image send failed | recipient_id=%s | result=%s",
        recipient_id, result,
    )
    return False
