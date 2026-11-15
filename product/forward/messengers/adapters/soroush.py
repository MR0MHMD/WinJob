"""آداپتور همگام پیام‌رسان سروش‌پلاس برای وین فوروارد، مبتنی بر SPlusthon و StringSession."""

from __future__ import annotations

import asyncio
import io
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, TypeVar

from .base import (
    MessengerAdapter,
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError, MessengerError,
)
from .registry import register

T = TypeVar("T")


def _run_async(coro_factory: Callable[[asyncio.AbstractEventLoop], Coroutine[Any, Any, T]]) -> T:
    """اجرای امن یک کوروتین غیرهمگام در حلقه رویداد ایزوله برای محیط‌های همگام جنگو.

    :param coro_factory: تابعی که loop را دریافت کرده و کوروتین مورد نظر را می‌سازد.
    :return: خروجی نهایی کوروتین.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro_factory(loop))
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        asyncio.set_event_loop(None)
        loop.close()


@register
class SoroushAdapter(MessengerAdapter):
    """آداپتور همگام سروش‌پلاس با استفاده از نشست کاربر (SPlusthon + StringSession)."""

    platform_slug = "soroush"

    def __init__(self, session_string: Optional[str] = None) -> None:
        """مقداردهی اولیه آداپتور سروش‌پلاس با رشته نشست کاربر.

        :param session_string: رشته StringSession ذخیره‌شده در BotUser.session_data.
        """
        self._session_string = session_string or ""

    @staticmethod
    def _import_splusthon():
        """ایمپورت تنبل کتابخانه SPlusthon جهت جلوگیری از خطای ایمپورت در صورت نصب نبودن."""
        try:
            from splusthon import SoroushClient
            from splusthon.sessions import StringSession
            return SoroushClient, StringSession
        except ImportError as exc:
            raise MessengerAPIError(
                "کتابخانه splusthon نصب نیست. لطفاً دستور pip install splusthon را اجرا کنید."
            ) from exc

    def _with_client(self, session_str: str, fn: Callable[[Any], Coroutine[Any, Any, T]]) -> T:
        """ایجاد نمونه ایزوله SoroushClient، اتصال، اجرای عملیات و قطع اتصال امن.

        :param session_str: رشته StringSession برای بازسازی نشست.
        :param fn: تابع async که نمونه client را دریافت می‌کند.
        :return: خروجی تابع async.
        """
        SoroushClient, StringSession = self._import_splusthon()

        async def _runner(loop: asyncio.AbstractEventLoop) -> T:
            client = SoroushClient(StringSession(session_str), loop=loop)
            await client.connect()
            try:
                return await fn(client)
            finally:
                await client.disconnect()

        try:
            return _run_async(_runner)
        except MessengerAPIError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "not found" in msg or "cannot find any entity" in msg:
                raise MessengerNotFoundError(f"کانال یا کاربر در سروش‌پلاس یافت نشد: {exc}") from exc
            if "admin" in msg or "permission" in msg or "chat_write_forbidden" in msg:
                raise MessengerPermissionError(f"دسترسی ارسال پیام در کانال سروش‌پلاس وجود ندارد: {exc}") from exc
            raise MessengerAPIError(f"خطا در ارتباط با سروش‌پلاس: {exc}") from exc

    def _require_session(self) -> None:
        """بررسی وجود رشته نشست معتبر پیش از اجرای عملیات نیازمند احراز هویت."""
        if not self._session_string:
            raise MessengerPermissionError(
                "نشست سروش‌پلاس برای این کاربر ثبت نشده است. لطفاً ابتدا با شماره موبایل وارد شوید."
            )

    # ============================================================
    # متدهای احراز هویت دو مرحله‌ای (OTP)
    # ============================================================

    def send_code(self, phone_number: str) -> Dict[str, Any]:
        """گام اول لاگین سروش‌پلاس: ارسال کد تایید به شماره موبایل و ذخیره نشست موقت.

        :param phone_number: شماره موبایل کاربر (ترجیحاً با کد کشور مثل +989123456789).
        :return: دیکشنری شامل phone_code_hash و temp_session جهت نگهداری در سشن جنگو.
        """
        async def _op(client):
            sent = await client.send_code_request(phone_number)
            return {
                "phone_code_hash": sent.phone_code_hash,
                "temp_session": client.session.save(),
            }

        return self._with_client("", _op)

    def sign_in(
        self,
        phone_number: str,
        code: str,
        phone_code_hash: str,
        temp_session: str,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """گام دوم لاگین سروش‌پلاس: تایید کد OTP و دریافت StringSession دائمی.

        :param phone_number: شماره موبایل کاربر.
        :param code: کد تایید ارسال‌شده.
        :param phone_code_hash: هش دریافت‌شده از مرحله send_code.
        :param temp_session: رشته نشست موقت تولیدشده در مرحله send_code.
        :param password: رمز تایید دومرحله‌ای در صورت فعال بودن (اختیاری).
        :return: دیکشنری شامل string_session، user_id و username.
        """
        async def _op(client):
            try:
                user = await client.sign_in(
                    phone=phone_number,
                    code=str(code).strip(),
                    phone_code_hash=phone_code_hash,
                )
            except Exception as exc:
                if "password" in str(exc).lower() and password:
                    user = await client.sign_in(password=password)
                else:
                    raise
            final_session = client.session.save()
            return {
                "string_session": final_session,
                "user_id": str(getattr(user, "id", "") or ""),
                "username": getattr(user, "username", "") or "",
            }

        res = self._with_client(temp_session, _op)
        self._session_string = res["string_session"]
        return res

    # ============================================================
    # متدهای کمکی فایل و ارسال محتوا
    # ============================================================

    @staticmethod
    def _to_bytes_io(file_obj: Any, default_filename: str) -> io.BytesIO:
        """تبدیل آبجکت فایل جنگو یا ContentFile به بافر حافظه BytesIO دارای نام فایل.

        :param file_obj: فایل ورودی (FieldFile، ContentFile، یا bytes).
        :param default_filename: نام پیش‌فرض در صورت نداشتن پسوند.
        :return: شیء BytesIO آماده ارسال به SPlusthon.
        """
        if isinstance(file_obj, (bytes, bytearray)):
            buf = io.BytesIO(bytes(file_obj))
            buf.name = default_filename
            return buf

        filename = getattr(file_obj, "name", default_filename) or default_filename
        filename = filename.split("/")[-1].split("\\")[-1]
        if "." not in filename:
            filename = default_filename

        if hasattr(file_obj, "open"):
            file_obj.open("rb")
            try:
                content = file_obj.read()
            finally:
                file_obj.close()
        elif hasattr(file_obj, "read"):
            content = file_obj.read()
        else:
            raise MessengerAPIError("فرمت فایل ورودی برای سروش‌پلاس معتبر نیست.")

        buf = io.BytesIO(content)
        buf.name = filename
        return buf

    @staticmethod
    async def _resolve_entity(client: Any, chat_id: str) -> Any:
        """تبدیل شناسه کانال (عددی یا یوزرنیم) به InputPeerChannel معتبر در SPlusthon.

        در Telethon/SPlusthon، ارسال عدد صحیح مثبت به عنوان User (GetUsersRequest) تفسیر می‌شود؛
        بنابراین برای کانال‌ها از PeerChannel و در صورت خالی بودن کش StringSession از get_dialogs استفاده می‌شود.

        :param client: نمونه متصل‌شده SoroushClient.
        :param chat_id: شناسه کانال (عددی یا یوزرنیم).
        :return: شیء InputPeer معتبر برای ارسال پیام یا فایل.
        """
        cleaned = str(chat_id).strip()
        if cleaned.lstrip("-").isdigit():
            from splusthon.tl.types import PeerChannel

            channel_id = int(cleaned[4:]) if cleaned.startswith("-100") else int(cleaned)
            peer = PeerChannel(channel_id)
            try:
                return await client.get_input_entity(peer)
            except Exception:
                await client.get_dialogs()
                return await client.get_input_entity(peer)
        return await client.get_input_entity(cleaned.lstrip("@"))

    def send_text(self, chat_id: str, text: str, reply_markup: dict = None) -> dict:
        """ارسال پیام متنی به کانال یا گفت‌وگوی سروش‌پلاس.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param text: متن پیام ارسالی.
        :param reply_markup: پارامتر سازگاری با اینترفیس پایه (در کلاینت شخصی استفاده نمی‌شود).
        :return: دیکشنری حاوی message_id.
        """
        self._require_session()

        async def _op(client):
            target = await self._resolve_entity(client, chat_id)
            msg = await client.send_message(target, text)
            return {"message_id": str(getattr(msg, "id", "") or "")}

        return self._with_client(self._session_string, _op)

    def _send_media_file(
        self,
        chat_id: str,
        file_obj: Any,
        default_filename: str,
        caption: str = "",
        **send_kwargs: Any,
    ) -> dict:
        """آپلود و ارسال فایل رسانه به کانال سروش‌پلاس با متد send_file.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param file_obj: آبجکت فایل رسانه.
        :param default_filename: نام پیش‌فرض فایل همراه با پسوند.
        :param caption: متن کپشن اختیاری.
        :return: دیکشنری حاوی message_id و file_id.
        """
        self._require_session()
        buf = self._to_bytes_io(file_obj, default_filename)

        async def _op(client):
            target = await self._resolve_entity(client, chat_id)
            msg = await client.send_file(target, buf, caption=caption or None, **send_kwargs)
            return {"message_id": str(getattr(msg, "id", "") or ""), "file_id": None}

        return self._with_client(self._session_string, _op)

    def send_photo(self, chat_id: str, photo, caption: str = "", file_id: str = None) -> dict:
        """ارسال عکس به کانال سروش‌پلاس همراه با کپشن اختیاری.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param photo: فایل تصویر.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id.
        """
        return self._send_media_file(chat_id, photo, "photo.jpg", caption=caption)

    def send_video(self, chat_id: str, video, caption: str = "", file_id: str = None) -> dict:
        """ارسال ویدیو به کانال سروش‌پلاس همراه با کپشن اختیاری.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param video: فایل ویدیو.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id.
        """
        return self._send_media_file(chat_id, video, "video.mp4", caption=caption, supports_streaming=True)

    def send_audio(self, chat_id: str, audio, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل صوتی به کانال سروش‌پلاس همراه با کپشن اختیاری.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param audio: فایل صوتی.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id.
        """
        return self._send_media_file(chat_id, audio, "audio.mp3", caption=caption)

    def send_voice(self, chat_id: str, voice, caption: str = "", file_id: str = None) -> dict:
        """ارسال پیام صوتی (ویس) به کانال سروش‌پلاس همراه با کپشن اختیاری.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param voice: فایل ویس.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id.
        """
        return self._send_media_file(chat_id, voice, "voice.ogg", caption=caption, voice_note=True)

    def send_document(self, chat_id: str, document, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل عمومی (سند) به کانال سروش‌پلاس همراه با کپشن اختیاری.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param document: فایل ارسالی.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id.
        """
        return self._send_media_file(chat_id, document, "document.bin", caption=caption, force_document=True)

    def send_animation(self, chat_id: str, animation, caption: str = "", file_id: str = None) -> dict:
        """ارسال گیف (انیمیشن) به کانال سروش‌پلاس همراه با کپشن اختیاری.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param animation: فایل گیف.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id.
        """
        return self._send_media_file(chat_id, animation, "animation.gif", caption=caption, nosound_video=True)

    def send_sticker(self, chat_id: str, sticker, file_id: str = None) -> dict:
        """ارسال استیکر به کانال سروش‌پلاس.

        :param chat_id: شناسه کانال یا یوزرنیم مقصد.
        :param sticker: فایل استیکر (webp).
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id.
        """
        return self._send_media_file(chat_id, sticker, "sticker.webp", caption="")

    # ============================================================
    # متدهای مدیریت و همگام‌سازی کانال‌ها
    # ============================================================

    def get_user_channels(self) -> List[Dict[str, str]]:
        """دریافت لیست کانال‌هایی که کاربر در سروش‌پلاس سازنده یا ادمین آن‌هاست.

        :return: لیست دیکشنری‌ها شامل chat_id، title و username هر کانال.
        """
        self._require_session()

        async def _op(client):
            dialogs = await client.get_dialogs()
            results: List[Dict[str, str]] = []
            for dialog in dialogs:
                if not getattr(dialog, "is_channel", False):
                    continue
                entity = getattr(dialog, "entity", None)
                if not entity:
                    continue
                is_creator = bool(getattr(entity, "creator", False))
                admin_rights = getattr(entity, "admin_rights", None)
                can_post = is_creator or bool(admin_rights and getattr(admin_rights, "post_messages", True))
                if not can_post:
                    continue
                results.append(
                    {
                        "chat_id": str(entity.id),
                        "title": getattr(entity, "title", None) or str(entity.id),
                        "username": getattr(entity, "username", "") or "",
                    }
                )
            return results

        return self._with_client(self._session_string, _op)

    def get_chat_info(self, chat_id: str) -> dict:
        """دریافت اطلاعات کانال سروش‌پلاس با شناسه عددی یا نام کاربری.

        :param chat_id: شناسه یا نام کاربری کانال.
        :return: دیکشنری شامل chat_id، title، username و type.
        """
        self._require_session()

        async def _op(client):
            target = await self._resolve_entity(client, chat_id)
            entity = await client.get_entity(target)
            return {
                "chat_id": str(entity.id),
                "title": getattr(entity, "title", "") or getattr(entity, "first_name", "") or str(entity.id),
                "username": getattr(entity, "username", "") or "",
                "type": "channel",
            }

        return self._with_client(self._session_string, _op)

    def check_bot_is_admin(self, chat_id: str) -> bool:
        """بررسی دسترسی ارسال پیام اکانت کاربر در کانال مشخص‌شده در سروش‌پلاس.

        :param chat_id: شناسه کانال یا نام کاربری.
        :return: True در صورت داشتن دسترسی ارسال پیام، در غیر این صورت False.
        """
        self._require_session()

        async def _op(client):
            target = await self._resolve_entity(client, chat_id)
            entity = await client.get_entity(target)
            if getattr(entity, "creator", False):
                return True
            admin_rights = getattr(entity, "admin_rights", None)
            return bool(admin_rights and getattr(admin_rights, "post_messages", True))

        try:
            return self._with_client(self._session_string, _op)
        except MessengerError:
            return False

    def get_bot_username(self) -> str:
        """دریافت نام کاربری ربات (برای سازگاری با اینترفیس پایه؛ در کلاینت شخصی خالی است).

        :return: رشته خالی.
        """
        return ""
