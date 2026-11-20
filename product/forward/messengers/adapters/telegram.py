"""آداپتور پیام‌رسان تلگرام برای وین فوروارد با پشتیبانی از پروکسی دائمی Xray."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, NoReturn, Optional

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from product.forward.messengers.telegram_proxy import (
    ensure_telegram_proxy,
    get_telegram_proxies,
)
from .base import (
    MessengerAdapter,
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from .registry import register

logger = logging.getLogger(__name__)


@register
class TelegramAdapter(MessengerAdapter):
    """پیاده‌سازی آداپتور تلگرام بر پایه Bot API رسمی و پروکسی Xray محلی."""

    platform_slug = "telegram"
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"
    FILE_URL = "https://api.telegram.org/file/bot{token}/{file_path}"
    TIMEOUT = 30
    _CACHED_BOT_USERNAME: str = ""

    def __init__(self, token: Optional[str] = None) -> None:
        """مقداردهی اولیه با توکن ربات تلگرام و ساخت نشست مقاوم با Retry."""
        resolved = token or getattr(settings, "FORWARD_TELEGRAM_TOKEN", "")
        if not resolved:
            raise MessengerAPIError("توکن ربات تلگرام (FORWARD_TELEGRAM_TOKEN) تنظیم نشده است.")
        self._token = resolved
        self._session = requests.Session()
        retry_cfg = Retry(
            total=2,
            backoff_factor=0.6,
            allowed_methods=["GET", "POST"],
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry_cfg))

    def _prepare_proxies(self) -> Optional[Dict[str, str]]:
        """اطمینان از آماده بودن پروکسی تلگرام پیش از هر درخواست."""
        proxies = get_telegram_proxies()
        if proxies:
            ensure_telegram_proxy()
        return proxies

    def _call(
        self,
        method: str,
        http_method: str = "GET",
        as_form: bool = False,
        **params: Any,
    ) -> Any:
        """فراخوانی متد رسمی Telegram Bot API از طریق پروکسی."""
        url = self.BASE_URL.format(token=self._token, method=method)
        proxies = self._prepare_proxies()
        try:
            if http_method == "GET":
                response = self._session.get(url, params=params, proxies=proxies, timeout=self.TIMEOUT)
            else:
                if as_form:
                    response = self._session.post(url, data=params, proxies=proxies, timeout=self.TIMEOUT)
                else:
                    response = self._session.post(url, json=params, proxies=proxies, timeout=self.TIMEOUT)
            data = response.json()
        except requests.RequestException as exc:
            raise MessengerAPIError(f"خطا در ارتباط با API تلگرام: {exc}") from exc
        except ValueError as exc:
            raise MessengerAPIError(f"پاسخ نامعتبر از تلگرام: {exc}") from exc

        if not data.get("ok"):
            self._handle_api_error(
                code=data.get("error_code", 0),
                description=data.get("description", "Unknown error"),
            )
        return data.get("result")

    def _handle_api_error(self, code: int, description: str) -> NoReturn:
        """تبدیل کدهای خطای تلگرام به استثناهای استاندارد آداپتور."""
        desc_lower = (description or "").lower()
        if "chat not found" in desc_lower or "user not found" in desc_lower or "not found" in desc_lower:
            raise MessengerNotFoundError(description)
        if (
            "not enough rights" in desc_lower
            or "forbidden" in desc_lower
            or "kicked" in desc_lower
            or "not a member" in desc_lower
            or code == 403
        ):
            raise MessengerPermissionError(description)
        if code == 429 or "too many requests" in desc_lower:
            match = re.search(r"retry after (\d+)", desc_lower)
            retry_after = int(match.group(1)) if match else 0
            raise MessengerRateLimitError(retry_after=retry_after, message=description)
        raise MessengerAPIError(f"{code}: {description}")

    def send_text(self, chat_id: str, text: str, reply_markup: dict = None, parse_mode: str = None) -> dict:
        """ارسال پیام متنی به کانال یا چت تلگرام."""
        params: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_markup:
            params["reply_markup"] = reply_markup
        result = self._call("sendMessage", http_method="POST", **params)
        return {"message_id": str(result["message_id"])}

    def _call_multipart(
        self,
        method: str,
        chat_id: str,
        media_field: str,
        media_file,
        media_filename: str,
        caption: str = "",
    ) -> dict:
        """آپلود و ارسال فایل با multipart/form-data به تلگرام."""
        url = self.BASE_URL.format(token=self._token, method=method)
        proxies = self._prepare_proxies()

        media_file.open("rb")
        try:
            file_bytes = media_file.read()
        finally:
            media_file.close()

        lower_name = media_filename.lower()
        if lower_name.endswith(".gif"):
            mime_type = "image/gif"
        elif lower_name.endswith(".webp"):
            mime_type = "image/webp"
        elif lower_name.endswith(".tgs"):
            mime_type = "application/x-tgsticker"
        elif lower_name.endswith(".webm"):
            mime_type = "video/webm"
        elif lower_name.endswith(".mp4"):
            mime_type = "video/mp4"
        elif lower_name.endswith((".jpg", ".jpeg")):
            mime_type = "image/jpeg"
        elif lower_name.endswith(".png"):
            mime_type = "image/png"
        elif lower_name.endswith(".mp3"):
            mime_type = "audio/mpeg"
        elif lower_name.endswith((".ogg", ".oga")):
            mime_type = "audio/ogg"
        else:
            mime_type = "application/octet-stream"

        files = {media_field: (media_filename, file_bytes, mime_type)}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption

        try:
            response = self._session.post(
                url,
                data=data,
                files=files,
                proxies=proxies,
                timeout=self.TIMEOUT * 4,
            )
            result = response.json()
        except requests.RequestException as exc:
            raise MessengerAPIError(f"خطا در ارتباط با API تلگرام: {exc}") from exc
        except ValueError as exc:
            raise MessengerAPIError(f"پاسخ نامعتبر از تلگرام: {exc}") from exc

        if not result.get("ok"):
            self._handle_api_error(
                code=result.get("error_code", 0),
                description=result.get("description", "Unknown error"),
            )
        return result.get("result")

    def send_photo(self, chat_id: str, photo, caption: str = "", file_id: str = None) -> dict:
        """ارسال عکس به تلگرام (با file_id کش‌شده یا آپلود فایل)."""
        if file_id:
            params: Dict[str, Any] = {"chat_id": chat_id, "photo": file_id}
            if caption:
                params["caption"] = caption
            result = self._call("sendPhoto", http_method="POST", **params)
        else:
            filename = getattr(photo, "name", "photo.jpg").split("/")[-1]
            result = self._call_multipart("sendPhoto", chat_id, "photo", photo, filename, caption)

        extracted_file_id = result.get("photo", [])[-1].get("file_id") if result.get("photo") else None
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_video(self, chat_id: str, video, caption: str = "", file_id: str = None) -> dict:
        """ارسال ویدیو به تلگرام (با file_id کش‌شده یا آپلود فایل)."""
        if file_id:
            params: Dict[str, Any] = {"chat_id": chat_id, "video": file_id}
            if caption:
                params["caption"] = caption
            result = self._call("sendVideo", http_method="POST", **params)
        else:
            filename = getattr(video, "name", "video.mp4").split("/")[-1]
            result = self._call_multipart("sendVideo", chat_id, "video", video, filename, caption)

        extracted_file_id = result.get("video", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_document(self, chat_id: str, document, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل یا سند به تلگرام (با file_id کش‌شده یا آپلود فایل)."""
        if file_id:
            params: Dict[str, Any] = {"chat_id": chat_id, "document": file_id}
            if caption:
                params["caption"] = caption
            result = self._call("sendDocument", http_method="POST", **params)
        else:
            filename = getattr(document, "name", "document.pdf").split("/")[-1]
            result = self._call_multipart("sendDocument", chat_id, "document", document, filename, caption)

        extracted_file_id = result.get("document", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_audio(self, chat_id: str, audio, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل صوتی (موزیک/پادکست) به تلگرام."""
        if file_id:
            params: Dict[str, Any] = {"chat_id": chat_id, "audio": file_id}
            if caption:
                params["caption"] = caption
            result = self._call("sendAudio", http_method="POST", **params)
        else:
            filename = getattr(audio, "name", "audio.mp3").split("/")[-1]
            result = self._call_multipart("sendAudio", chat_id, "audio", audio, filename, caption)

        extracted_file_id = result.get("audio", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_voice(self, chat_id: str, voice, caption: str = "", file_id: str = None) -> dict:
        """ارسال پیام صوتی (ویس) به تلگرام."""
        if file_id:
            params: Dict[str, Any] = {"chat_id": chat_id, "voice": file_id}
            if caption:
                params["caption"] = caption
            result = self._call("sendVoice", http_method="POST", **params)
        else:
            filename = getattr(voice, "name", "voice.ogg").split("/")[-1]
            result = self._call_multipart("sendVoice", chat_id, "voice", voice, filename, caption)

        extracted_file_id = result.get("voice", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_animation(self, chat_id: str, animation, caption: str = "", file_id: str = None) -> dict:
        """ارسال گیف/انیمیشن به تلگرام."""
        if file_id:
            params: Dict[str, Any] = {"chat_id": chat_id, "animation": file_id}
            if caption:
                params["caption"] = caption
            result = self._call("sendAnimation", http_method="POST", **params)
        else:
            filename = getattr(animation, "name", "animation.gif").split("/")[-1]
            result = self._call_multipart("sendAnimation", chat_id, "animation", animation, filename, caption)

        extracted_file_id = result.get("animation", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_sticker(self, chat_id: str, sticker, file_id: str = None) -> dict:
        """ارسال استیکر به تلگرام."""
        if file_id:
            result = self._call("sendSticker", http_method="POST", chat_id=chat_id, sticker=file_id)
        else:
            filename = getattr(sticker, "name", "sticker.webp").split("/")[-1]
            if not filename.lower().endswith((".webp", ".tgs", ".webm")):
                filename = "sticker.webp"
            result = self._call_multipart("sendSticker", chat_id, "sticker", sticker, filename)

        extracted_file_id = result.get("sticker", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def check_bot_is_admin(self, chat_id: str) -> bool:
        """بررسی ادمین بودن ربات در کانال تلگرام با متد getChatMember."""
        me = self._call("getMe")
        member = self._call("getChatMember", chat_id=chat_id, user_id=me["id"])
        return member.get("status") in ("creator", "administrator")

    def get_chat_info(self, chat_id: str) -> dict:
        """دریافت عنوان، یوزرنیم و نوع چت/کانال از تلگرام."""
        chat = self._call("getChat", chat_id=chat_id)
        return {
            "chat_id": str(chat.get("id", chat_id)),
            "title": chat.get("title", "") or chat.get("first_name", "") or "",
            "username": chat.get("username", "") or "",
            "type": chat.get("type", "channel"),
        }

    def get_bot_username(self) -> str:
        """دریافت نام کاربری ربات تلگرام (بدون @) با کش داخلی."""
        if self.__class__._CACHED_BOT_USERNAME:
            return self.__class__._CACHED_BOT_USERNAME
        me = self._call("getMe")
        username = me.get("username", "") or ""
        if username:
            self.__class__._CACHED_BOT_USERNAME = username
        return username

    def answer_callback_query(self, callback_query_id: str, text: str = "", show_alert: bool = False) -> bool:
        """بستن وضعیت لودینگ دکمه‌های شیشه‌ای در تلگرام (answerCallbackQuery)."""
        if not callback_query_id:
            return False
        try:
            params: Dict[str, Any] = {"callback_query_id": callback_query_id}
            if text:
                params["text"] = text
                params["show_alert"] = show_alert
            self._call("answerCallbackQuery", http_method="POST", **params)
            return True
        except Exception:
            return False

    def edit_message_reply_markup(self, chat_id: str, message_id: int, reply_markup: dict) -> bool:
        """ویرایش کیبورد شیشه‌ای پیام در تلگرام (با نادیده گرفتن خطای عدم تغییر)."""
        try:
            self._call(
                "editMessageReplyMarkup",
                http_method="POST",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )
            return True
        except MessengerAPIError as exc:
            if "message is not modified" in str(exc).lower():
                return True
            return False
        except Exception:
            return False

    def delete_message(self, chat_id: str, message_id: int) -> bool:
        """حذف یک پیام از چت در تلگرام."""
        try:
            self._call("deleteMessage", http_method="POST", chat_id=chat_id, message_id=message_id)
            return True
        except Exception:
            return False

    def edit_message_text(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        reply_markup: dict = None,
        parse_mode: str = None,
    ) -> dict:
        """ویرایش متن پیام ارسال‌شده در تلگرام."""
        params: Dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_markup:
            params["reply_markup"] = reply_markup
        try:
            return self._call("editMessageText", http_method="POST", **params)
        except MessengerAPIError as exc:
            if "message is not modified" in str(exc).lower():
                return {"message_id": message_id}
            raise

    def get_file(self, file_id: str) -> dict:
        """دریافت مسیر فایل از تلگرام با متد getFile."""
        return self._call("getFile", file_id=file_id)

    def download_file(self, file_path: str) -> bytes:
        """دانلود بایت‌های فایل از سرور فایل تلگرام از طریق پروکسی."""
        url = self.FILE_URL.format(token=self._token, file_path=file_path)
        proxies = self._prepare_proxies()
        response = self._session.get(url, proxies=proxies, timeout=self.TIMEOUT * 4)
        if response.status_code != 200:
            raise MessengerAPIError(f"خطا در دانلود فایل از تلگرام (HTTP {response.status_code})")
        return response.content

    def download_chat_avatar(self, chat_id: str) -> Optional[bytes]:
        """دریافت و دانلود بایت‌های عکس پروفایل کانال تلگرام با getChat و getFile."""
        try:
            chat = self._call("getChat", chat_id=chat_id) or {}
            photo = chat.get("photo") or {}
            file_id = photo.get("big_file_id") or photo.get("small_file_id") if isinstance(photo, dict) else None
            if not file_id:
                logger.info("[telegram] No photo found in getChat for chat_id=%s", chat_id)
                return None
            file_info = self.get_file(file_id) or {}
            file_path = file_info.get("file_path")
            if not file_path:
                return None
            return self.download_file(file_path)
        except Exception as exc:
            logger.warning("[telegram] download_chat_avatar failed for %s: %s", chat_id, exc)
            return None
