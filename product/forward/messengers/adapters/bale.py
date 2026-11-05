"""آداپتور پیام‌رسان بله برای وین فوروارد، با استفاده مستقیم از HTTP API."""

import re
from typing import NoReturn

import requests
from django.conf import settings

from .base import (
    MessengerAdapter,
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from .registry import register


@register
class BaleAdapter(MessengerAdapter):
    """پیاده‌سازی آداپتور بله با استفاده مستقیم از HTTP API (بدون وابستگی به Balethon)."""

    platform_slug = "bale"
    BASE_URL = "https://tapi.bale.ai/bot{token}/{method}"
    TIMEOUT = 30

    def __init__(self):
        """مقداردهی اولیه با توکن مخصوص وین فوروارد."""
        token = getattr(settings, "FORWARD_BALE_TOKEN", None)
        if not token:
            raise MessengerAPIError("توکن ربات بله برای وین فوروارد تنظیم نشده است.")
        self._token = token

    def _call(self, method: str, http_method: str = "GET", **params):
        """فراخوانی متد API بله (به صورت GET یا POST)."""
        url = self.BASE_URL.format(token=self._token, method=method)
        try:
            if http_method == "GET":
                response = requests.get(url, params=params, timeout=self.TIMEOUT)
            else:
                response = requests.post(url, json=params, timeout=self.TIMEOUT)
            data = response.json()
        except requests.RequestException as exc:
            raise MessengerAPIError(f"خطا در ارتباط با API بله: {exc}") from exc
        except ValueError as exc:
            raise MessengerAPIError(f"پاسخ نامعتبر از بله: {exc}") from exc

        if not data.get("ok"):
            self._handle_api_error(
                code=data.get("error_code", 0),
                description=data.get("description", "Unknown error"),
            )
        return data.get("result")

    def _handle_api_error(self, code: int, description: str) -> NoReturn:
        """تبدیل خطای API بله به خطای معنادار آداپتور."""
        desc_lower = description.lower()
        if "not found" in desc_lower:
            raise MessengerNotFoundError(description)
        if "not enough rights" in desc_lower or "forbidden" in desc_lower or code == 403:
            raise MessengerPermissionError(description)
        if code == 429 or "too many requests" in desc_lower:
            match = re.search(r"retry after (\d+)", desc_lower)
            retry_after = int(match.group(1)) if match else 0
            raise MessengerRateLimitError(retry_after=retry_after, message=description)
        raise MessengerAPIError(f"{code}: {description}")

    def send_text(self, chat_id: str, text: str, reply_markup: dict = None) -> dict:
        """ارسال پیام متنی به کانال یا چت مشخص، با پشتیبانی از کیبورد شیشه‌ای."""
        import json
        params = {"chat_id": chat_id, "text": text}
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)  # بله کیبورد رو به صورت رشته JSON می‌خواد
        result = self._call("sendMessage", **params)
        return {"message_id": str(result["message_id"])}

    def _call_multipart(self, method: str, chat_id: str, media_field: str, media_file, media_filename: str,
                        caption: str = "") -> dict:
        """فراخوانی متدهای ارسال فایل با multipart/form-data."""
        url = self.BASE_URL.format(token=self._token, method=method)

        media_file.open("rb")
        try:
            file_bytes = media_file.read()
        finally:
            media_file.close()

        files = {media_field: (media_filename, file_bytes, "application/octet-stream")}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption

        try:
            response = requests.post(url, data=data, files=files, timeout=self.TIMEOUT * 3)
            result = response.json()
        except requests.RequestException as exc:
            raise MessengerAPIError(f"خطا در ارتباط با API بله: {exc}") from exc
        except ValueError as exc:
            raise MessengerAPIError(f"پاسخ نامعتبر از بله: {exc}") from exc

        if not result.get("ok"):
            self._handle_api_error(
                code=result.get("error_code", 0),
                description=result.get("description", "Unknown error"),
            )
        return result.get("result")

    def send_photo(self, chat_id: str, photo, caption: str = "", file_id: str = None) -> dict:
        """ارسال عکس با کپشن اختیاری (با استفاده از file_id در صورت وجود)."""
        if file_id:
            result = self._call("sendPhoto", http_method="POST", chat_id=chat_id, photo=file_id, caption=caption)
        else:
            filename = getattr(photo, "name", "photo.jpg").split("/")[-1]
            result = self._call_multipart("sendPhoto", chat_id, "photo", photo, filename, caption)

        extracted_file_id = result.get("photo", [])[-1].get("file_id") if result.get("photo") else None
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_video(self, chat_id: str, video, caption: str = "", file_id: str = None) -> dict:
        """ارسال ویدیو با کپشن اختیاری (با استفاده از file_id در صورت وجود)."""
        if file_id:
            result = self._call("sendVideo", http_method="POST", chat_id=chat_id, video=file_id, caption=caption)
        else:
            filename = getattr(video, "name", "video.mp4").split("/")[-1]
            result = self._call_multipart("sendVideo", chat_id, "video", video, filename, caption)

        extracted_file_id = result.get("video", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_document(self, chat_id: str, document, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل با کپشن اختیاری (با استفاده از file_id در صورت وجود)."""
        if file_id:
            result = self._call("sendDocument", http_method="POST", chat_id=chat_id, document=file_id, caption=caption)
        else:
            filename = getattr(document, "name", "document.pdf").split("/")[-1]
            result = self._call_multipart("sendDocument", chat_id, "document", document, filename, caption)

        extracted_file_id = result.get("document", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def check_bot_is_admin(self, chat_id: str) -> bool:
        """بررسی ادمین بودن ربات در کانال با استفاده از getChatMember."""
        me = self._call("getMe")
        member = self._call("getChatMember", chat_id=chat_id, user_id=me["id"])
        return member.get("status") in ("creator", "administrator")

    def get_chat_info(self, chat_id: str) -> dict:
        """دریافت اطلاعات کانال (عنوان، نام کاربری، نوع)."""
        chat = self._call("getChat", chat_id=chat_id)
        return {
            "title": chat.get("title", "") or chat.get("first_name", "") or "",
            "username": chat.get("username", "") or "",
            "type": chat.get("type", "channel"),
        }

    def get_bot_username(self) -> str:
        """دریافت نام کاربری ربات برای ساخت Deep Link (بدون @)."""
        me = self._call("getMe")
        return me.get("username", "") or ""

    def edit_message_reply_markup(self, chat_id: str, message_id: int, reply_markup: dict) -> bool:
        """ویرایش کیبورد شیشه‌ای یک پیام ارسال‌شده (بدون تغییر متن)."""
        import json
        try:
            self._call(
                "editMessageReplyMarkup",
                http_method="POST",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=json.dumps(reply_markup)
            )
            return True
        except Exception:
            return False
