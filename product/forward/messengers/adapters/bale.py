"""آداپتور پیام‌رسان بله برای وین فوروارد، با استفاده مستقیم از HTTP API."""

import logging
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

logger = logging.getLogger(__name__)


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

    def _call(self, method: str, http_method: str = "GET", as_form: bool = False, **params):
        """فراخوانی متد API بله (با قابلیت ارسال به صورت form-data یا JSON)."""
        url = self.BASE_URL.format(token=self._token, method=method)
        try:
            if http_method == "GET":
                response = requests.get(url, params=params, timeout=self.TIMEOUT)
            else:
                if as_form:
                    response = requests.post(url, data=params, timeout=self.TIMEOUT)
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
        """فراخوانی متدهای ارسال فایل با multipart/form-data (با MIME type صحیح)."""
        url = self.BASE_URL.format(token=self._token, method=method)

        media_file.open("rb")
        try:
            file_bytes = media_file.read()
        finally:
            media_file.close()

        # تعیین MIME type بر اساس پسوند فایل
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

    def send_audio(self, chat_id: str, audio, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل صوتی با کپشن اختیاری (با استفاده از file_id در صورت وجود)."""
        if file_id:
            result = self._call("sendAudio", http_method="POST", chat_id=chat_id, audio=file_id, caption=caption)
        else:
            filename = getattr(audio, "name", "audio.mp3").split("/")[-1]
            result = self._call_multipart("sendAudio", chat_id, "audio", audio, filename, caption)

        extracted_file_id = result.get("audio", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_voice(self, chat_id: str, voice, caption: str = "", file_id: str = None) -> dict:
        """ارسال پیام صوتی (ویس) با کپشن اختیاری (با استفاده از file_id در صورت وجود)."""
        if file_id:
            result = self._call("sendVoice", http_method="POST", chat_id=chat_id, voice=file_id, caption=caption)
        else:
            filename = getattr(voice, "name", "voice.ogg").split("/")[-1]
            result = self._call_multipart("sendVoice", chat_id, "voice", voice, filename, caption)

        extracted_file_id = result.get("voice", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_animation(self, chat_id: str, animation, caption: str = "", file_id: str = None) -> dict:
        """ارسال گیف (با file_id یا آپلود جدید)."""
        if file_id:
            # 🔑 استفاده از as_form=True برای جلوگیری از خطای malformed request
            result = self._call("sendAnimation", http_method="POST", as_form=True, chat_id=chat_id, animation=file_id,
                                caption=caption)
        else:
            filename = getattr(animation, "name", "animation.gif").split("/")[-1]
            result = self._call_multipart("sendAnimation", chat_id, "animation", animation, filename, caption)

        extracted_file_id = result.get("animation", {}).get("file_id")
        return {"message_id": str(result["message_id"]), "file_id": extracted_file_id}

    def send_sticker(self, chat_id: str, sticker, file_id: str = None) -> dict:
        """ارسال استیکر (با file_id یا آپلود جدید)."""
        if file_id:
            # 🔑 استفاده از as_form=True برای جلوگیری از خطای malformed request
            result = self._call("sendSticker", http_method="POST", as_form=True, chat_id=chat_id, sticker=file_id)
        else:
            filename = getattr(sticker, "name", "sticker.webp").split("/")[-1]
            if not filename.lower().endswith(('.webp', '.tgs', '.webm')):
                filename = "sticker.webp"
            result = self._call_multipart("sendSticker", chat_id, "sticker", sticker, filename)

        extracted_file_id = result.get("sticker", {}).get("file_id")
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

    def delete_message(self, chat_id: str, message_id: int) -> bool:
        """حذف یک پیام از چت در بله (deleteMessage) با مدیریت امن خطا."""
        try:
            self._call("deleteMessage", http_method="POST", chat_id=chat_id, message_id=message_id)
            return True
        except Exception:
            return False

    def edit_message_text(self, chat_id: str, message_id: int, text: str, reply_markup: dict = None) -> dict:
        """ویرایش متن یک پیام ارسال‌شده (editMessageText)."""
        import json
        params = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        return self._call("editMessageText", http_method="POST", **params)

    def get_file(self, file_id: str) -> dict:
        """اطلاعات فایل را از بله دریافت میکند (getFile)."""
        result = self._call("getFile", file_id=file_id)
        return result

    def download_file(self, file_path: str) -> bytes:
        """فایل را از سرور بله دانلود میکند و بایتهای آن را برمیگرداند."""
        url = f"https://tapi.bale.ai/file/bot{self._token}/{file_path}"
        response = requests.get(url, timeout=self.TIMEOUT * 3)
        if response.status_code != 200:
            raise MessengerAPIError(f"خطا در دانلود فایل از بله (HTTP {response.status_code})")
        return response.content

    def download_chat_avatar(self, chat_id: str):
        """دریافت و دانلود بایت‌های عکس پروفایل کانال بله از طریق getChat و getFile."""
        try:
            chat = self._call("getChat", chat_id=chat_id) or {}
            photo = chat.get("photo") or {}
            file_id = photo.get("big_file_id") or photo.get("small_file_id") if isinstance(photo, dict) else None
            if not file_id:
                logger.info(f"[bale] No photo found in getChat for chat_id={chat_id}: keys={list(chat.keys())}")
                return None
            file_info = self.get_file(file_id) or {}
            file_path = file_info.get("file_path")
            if not file_path:
                logger.warning(f"[bale] getFile missing file_path for file_id={file_id}")
                return None
            return self.download_file(file_path)
        except Exception as exc:
            logger.warning(f"[bale] download_chat_avatar failed for {chat_id}: {exc}")
            return None
