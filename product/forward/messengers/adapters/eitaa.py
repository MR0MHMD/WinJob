"""آداپتور پیام‌رسان ایتا برای وین فوروارد، با استفاده از API ایتایار."""

from typing import NoReturn

import requests
from .base import (
    MessengerAdapter,
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from .registry import register


@register
class EitaaAdapter(MessengerAdapter):
    """پیاده‌سازی آداپتور ایتا با استفاده مستقیم از HTTP API ایتایار."""

    platform_slug = "eitaa"
    BASE_URL = "https://eitaayar.ir/api/{token}/{method}"
    TIMEOUT = 30

    def __init__(self, token: str = None):
        if token:
            self._token = token
        else:
            from django.conf import settings
            self._token = getattr(settings, "EITAA_BOT_TOKEN", None)
        if not self._token:
            raise MessengerAPIError("توکن ایتایار تنظیم نشده است.")

    def _call(self, method: str, http_method: str = "POST", **params):
        url = self.BASE_URL.format(token=self._token, method=method)
        try:
            if http_method == "GET":
                response = requests.get(url, params=params, timeout=self.TIMEOUT)
            else:
                response = requests.post(url, json=params, timeout=self.TIMEOUT)
            data = response.json()
        except requests.RequestException as exc:
            raise MessengerAPIError(f"خطا در ارتباط با API ایتا: {exc}") from exc
        except ValueError as exc:
            raise MessengerAPIError(f"پاسخ نامعتبر از ایتا: {exc}") from exc

        if not data.get("ok"):
            description = data.get("description", "") or data.get("error", "") or "Unknown error"
            self._handle_api_error(description)
        return data.get("result")

    def _handle_api_error(self, description: str) -> NoReturn:
        desc_lower = description.lower()
        if "not found" in desc_lower or "chat not found" in desc_lower:
            raise MessengerNotFoundError(description)
        if "forbidden" in desc_lower or "not enough" in desc_lower or "access" in desc_lower:
            raise MessengerPermissionError(description)
        if "too many" in desc_lower or "rate limit" in desc_lower:
            raise MessengerRateLimitError(0, description)
        raise MessengerAPIError(description)

    def send_text(self, chat_id: str, text: str, reply_markup: dict = None) -> dict:
        result = self._call("sendMessage", chat_id=chat_id, text=text)
        return {"message_id": str(result.get("message_id", "")) if isinstance(result, dict) else ""}

    # ============================================================
    # Media helpers
    # ============================================================

    def _extract_file_id(self, result):
        """استخراج file_id از پاسخ sendFile."""
        if not isinstance(result, dict):
            return None
        if result.get("file_id"):
            return result["file_id"]
        if isinstance(result.get("file"), dict):
            return result["file"].get("file_id")
        if isinstance(result.get("message"), dict):
            msg_file = result["message"].get("file")
            if isinstance(msg_file, dict):
                return msg_file.get("file_id")
        return None

    def _build_media_response(self, result) -> dict:
        if not isinstance(result, dict):
            return {"message_id": "", "file_id": None}
        return {
            "message_id": str(result.get("message_id", "")),
            "file_id": self._extract_file_id(result),
        }

    def _upload_and_send(self, chat_id: str, file_obj, filename: str,
                         file_type: str, caption: str = "") -> dict:
        """آپلود فایل جدید به ایتا."""
        url = self.BASE_URL.format(token=self._token, method="sendFile")

        file_obj.open("rb")
        try:
            file_bytes = file_obj.read()
        finally:
            file_obj.close()

        files = {"file": (filename, file_bytes, "application/octet-stream")}
        data = {"chat_id": chat_id, "type": file_type}
        if caption:
            data["caption"] = caption

        try:
            response = requests.post(url, data=data, files=files, timeout=self.TIMEOUT * 5)
            result = response.json()
        except requests.RequestException as exc:
            raise MessengerAPIError(f"خطا در ارتباط با API ایتا (آپلود): {exc}") from exc
        except ValueError as exc:
            raise MessengerAPIError(f"پاسخ نامعتبر از ایتا (آپلود): {exc}") from exc

        if not result.get("ok"):
            description = result.get("description", "") or result.get("error", "") or "Unknown error"
            self._handle_api_error(description)
        return result.get("result")

    def _send_with_file_id(self, chat_id: str, file_id: str,
                           file_type: str, caption: str = "") -> dict:
        """ارسال فایل با استفاده از file_id موجود."""
        params = {"chat_id": chat_id, "file_id": file_id, "type": file_type}
        if caption:
            params["caption"] = caption
        return self._call("sendFile", **params)

    def send_photo(self, chat_id: str, photo, caption: str = "", file_id: str = None) -> dict:
        if file_id:
            result = self._send_with_file_id(chat_id, file_id, "Image", caption)
        else:
            filename = getattr(photo, "name", "photo.jpg").split("/")[-1]
            result = self._upload_and_send(chat_id, photo, filename, "Image", caption)
        return self._build_media_response(result)

    def send_video(self, chat_id: str, video, caption: str = "", file_id: str = None) -> dict:
        if file_id:
            result = self._send_with_file_id(chat_id, file_id, "Video", caption)
        else:
            filename = getattr(video, "name", "video.mp4").split("/")[-1]
            result = self._upload_and_send(chat_id, video, filename, "Video", caption)
        return self._build_media_response(result)

    def send_document(self, chat_id: str, document, caption: str = "", file_id: str = None) -> dict:
        if file_id:
            result = self._send_with_file_id(chat_id, file_id, "File", caption)
        else:
            filename = getattr(document, "name", "document.pdf").split("/")[-1]
            result = self._upload_and_send(chat_id, document, filename, "File", caption)
        return self._build_media_response(result)

    def send_animation(self, chat_id: str, animation, caption: str = "", file_id: str = None) -> dict:
        """
        ارسال گیف به ایتا.
        طبق مستندات ایتایار: فایل باید با پسوند .gif و type="Gif" ارسال شود.
        """
        filename = getattr(animation, "name", "animation.gif")
        if not filename.lower().endswith(".gif"):
            filename = "animation.gif"

        result = self._upload_and_send(chat_id, animation, filename, "Gif", caption)
        return self._build_media_response(result)

    def send_sticker(self, chat_id: str, sticker, file_id: str = None) -> dict:
        """
        ارسال استیکر به ایتا.
        طبق مستندات ایتایار: فایل باید با پسوند .webp و type="Sticker" ارسال شود.
        """
        filename = getattr(sticker, "name", "sticker.webp")
        if not filename.lower().endswith(".webp"):
            filename = "sticker.webp"

        result = self._upload_and_send(chat_id, sticker, filename, "Sticker", "")
        return self._build_media_response(result)

    def check_bot_is_admin(self, chat_id: str) -> bool:
        return True

    def get_chat_info(self, chat_id: str) -> dict:
        return {"title": "", "username": "", "type": "channel"}

    def get_bot_username(self) -> str:
        me = self._call("getMe")
        return me.get("username", "") or ""
