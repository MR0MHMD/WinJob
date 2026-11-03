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

    def _call(self, method: str, **params):
        """فراخوانی متد API بله و بازگرداندن result در صورت موفقیت."""
        url = self.BASE_URL.format(token=self._token, method=method)
        try:
            response = requests.get(url, params=params, timeout=self.TIMEOUT)
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

    def send_text(self, chat_id: str, text: str) -> dict:
        """ارسال پیام متنی به کانال یا چت مشخص."""
        result = self._call("sendMessage", chat_id=chat_id, text=text)
        return {"message_id": str(result["message_id"])}

    def send_photo(self, chat_id: str, photo, caption: str = "") -> dict:
        """ارسال عکس با کپشن اختیاری."""
        result = self._call("sendPhoto", chat_id=chat_id, photo=photo, caption=caption)
        return {"message_id": str(result["message_id"])}

    def send_video(self, chat_id: str, video, caption: str = "") -> dict:
        """ارسال ویدیو با کپشن اختیاری."""
        result = self._call("sendVideo", chat_id=chat_id, video=video, caption=caption)
        return {"message_id": str(result["message_id"])}

    def send_document(self, chat_id: str, document, caption: str = "") -> dict:
        """ارسال فایل با کپشن اختیاری."""
        result = self._call("sendDocument", chat_id=chat_id, document=document, caption=caption)
        return {"message_id": str(result["message_id"])}

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