"""آداپتور اختصاصی سروش‌پلاس (Soroush+) مبتنی بر MTProto/WebSocket (SPlusthon) با ورکر ایزوله.

سروش‌پلاس در وین‌فوروارد فقط برای ورود OTP، همگام‌سازی کانال‌ها و ارسال پیام متنی / کپشن استفاده می‌شود
و تمام عملیات asyncio در یک subprocess کوتاه‌عمر (soroush_worker.py) بدون تداخل با GeventWorker اجرا می‌گردد.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import sys
import threading
from typing import Any

from .base import (
    MessengerAPIError,
    MessengerAdapter,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from .registry import register

logger = logging.getLogger(__name__)

_WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soroush_worker.py")
_WORKER_CONCURRENCY = threading.Semaphore(3)
_MEDIA_UNSUPPORTED_MSG = "سروش‌پلاس در حال حاضر فقط از ارسال پیام متنی و کپشن پشتیبانی می‌کند."


def normalize_iran_phone(raw: str) -> str:
    """نرمال‌سازی شماره موبایل ایران به فرمت بین‌المللی (+989...)."""
    digits = "".join(ch for ch in (raw or "").strip() if ch.isdigit())
    if digits.startswith("0098"):
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = "98" + digits[1:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "98" + digits
    if not digits:
        raise ValueError("شماره موبایل معتبر وارد نشده است.")
    return "+" + digits


def _raise_worker_error(resp: dict) -> None:
    """تبدیل خطای بازگشتی از ورکر سروش‌پلاس به سلسله‌مراتب استاندارد خطاهای وین‌فوروارد."""
    msg = str(resp.get("error") or "خطای ناشناخته در ارتباط با سروش‌پلاس")
    kind = resp.get("error_kind", "")
    upper = msg.upper()

    if kind == "permission":
        raise MessengerPermissionError(msg)
    if "FLOOD" in upper:
        sec = int(resp.get("seconds") or 10)
        raise MessengerRateLimitError(
            retry_after=sec,
            message=f"محدودیت نرخ ارسال سروش‌پلاس؛ لطفاً {sec} ثانیه صبر کنید.",
        )
    if any(k in upper for k in ("AUTH_KEY_UNREGISTERED", "SESSION_REVOKED", "USER_DEACTIVATED", "KEY IS NOT REGISTERED")):
        raise MessengerPermissionError(
            "نشست سروش‌پلاس شما منقضی شده یا باطل شده است؛ لطفاً از پنل وین‌فوروارد دوباره وارد شوید."
        )
    if any(k in upper for k in ("CHAT_WRITE_FORBIDDEN", "CHAT_ADMIN_REQUIRED", "CHANNEL_PRIVATE", "USER_BANNED")):
        raise MessengerPermissionError(
            "اکانت سروش‌پلاس شما دسترسی ارسال پیام یا ادمینی در این کانال را ندارد."
        )
    if any(k in upper for k in ("USERNAME_NOT_OCCUPIED", "PEER_ID_INVALID", "CANNOT FIND ANY ENTITY")):
        raise MessengerNotFoundError("کانال مورد نظر در سروش‌پلاس پیدا نشد.")
    raise MessengerAPIError(f"خطای سروش‌پلاس: {msg}")


def _call_worker(payload: dict, timeout: int = 60) -> Any:
    """فراخوانی ورکر ایزوله سروش‌پلاس با JSON از طریق stdin/stdout."""
    raw_in = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with _WORKER_CONCURRENCY:
        try:
            proc = subprocess.run(
                [sys.executable, _WORKER_SCRIPT],
                input=raw_in,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise MessengerAPIError("زمان ارتباط با سرورهای سروش‌پلاس به پایان رسید (Timeout).") from exc
        except Exception as exc:
            raise MessengerAPIError(f"خطا در اجرای سرویس سروش‌پلاس: {exc}") from exc

    stdout_text = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if not stdout_text:
        stderr_text = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        if "No module named 'splusthon'" in stderr_text:
            raise MessengerAPIError("کتابخانه splusthon روی سرور نصب نیست (pip install splusthon).")
        raise MessengerAPIError(f"پاسخ نامعتبر از سرویس سروش‌پلاس: {stderr_text[:300]}")

    last_line = stdout_text.splitlines()[-1]
    try:
        resp = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise MessengerAPIError(f"خطا در خواندن پاسخ سروش‌پلاس: {stdout_text[:300]}") from exc

    if not resp.get("ok"):
        _raise_worker_error(resp)
    return resp.get("data")


@register
class SoroushAdapter(MessengerAdapter):
    """آداپتور سبک و ایزوله سروش‌پلاس (فقط متن و کپشن · سازگار با Gunicorn + GeventWorker)."""

    platform_slug = "soroush"

    def __init__(self, string_session: str = "", channel_hashes: dict | None = None, **kwargs):
        """مقداردهی آداپتور با StringSession و نقشه access_hash کانال‌ها برای ارسال فوری."""
        self.string_session = (string_session or "").strip()
        self.channel_hashes = dict(channel_hashes or {})

    def send_code(self, phone_number: str) -> dict:
        """گام اول ورود: ارسال کد تایید (OTP) به حساب سروش‌پلاس کاربر."""
        phone = normalize_iran_phone(phone_number)
        return _call_worker({"action": "send_code", "phone_number": phone}, timeout=60)

    def sign_in(
        self,
        phone_number: str,
        phone_code: str,
        phone_code_hash: str,
        tmp_session: str,
        password: str = "",
    ) -> dict:
        """گام دوم ورود: تایید کد OTP (و رمز دو مرحله‌ای در صورت نیاز) و بازگرداندن StringSession دائمی."""
        phone = normalize_iran_phone(phone_number)
        code = "".join(ch for ch in (phone_code or "").strip() if ch.isdigit())
        return _call_worker(
            {
                "action": "sign_in",
                "phone_number": phone,
                "phone_code": code,
                "phone_code_hash": phone_code_hash,
                "tmp_session": tmp_session,
                "password": password or "",
            },
            timeout=60,
        )

    def logout(self) -> bool:
        """خروج کامل و ابطال نشست فعلی سروش‌پلاس روی سرور."""
        if not self.string_session:
            return True
        try:
            return bool(_call_worker({"action": "logout", "string_session": self.string_session}, timeout=30))
        except Exception as exc:
            logger.warning("خروج از سروش‌پلاس با خطا مواجه شد: %s", exc)
            return False

    def get_user_channels(self, include_avatars: bool = True) -> list[dict]:
        """واکشی خودکار کانال‌هایی که کاربر در آن‌ها سازنده یا ادمین با دسترسی ارسال است."""
        if not self.string_session:
            raise MessengerPermissionError("نشست سروش‌پلاس تنظیم نشده است.")
        rows = _call_worker(
            {
                "action": "get_user_channels",
                "string_session": self.string_session,
                "include_avatars": include_avatars,
            },
            timeout=120,
        )
        result = []
        for row in rows or []:
            av_b64 = row.pop("avatar_b64", "")
            row["avatar_bytes"] = base64.b64decode(av_b64) if av_b64 else None
            result.append(row)
        return result

    def send_text(self, chat_id: str, text: str, reply_markup: dict = None) -> dict:
        """ارسال پیام متنی به کانال سروش‌پلاس (با استفاده از access_hash کش‌شده در صورت وجود)."""
        if not self.string_session:
            raise MessengerPermissionError("نشست سروش‌پلاس متصل نیست.")
        cid_str = str(chat_id or "").strip()
        access_hash = (
            self.channel_hashes.get(cid_str)
            or self.channel_hashes.get(cid_str.lstrip("-@"))
            or ""
        )
        return _call_worker(
            {
                "action": "send_text",
                "string_session": self.string_session,
                "chat_id": cid_str,
                "access_hash": str(access_hash),
                "text": text or "",
            },
            timeout=60,
        )

    def send_photo(self, chat_id: str, photo, caption: str = "", file_id: str = None) -> dict:
        raise MessengerAPIError(_MEDIA_UNSUPPORTED_MSG)

    def send_video(self, chat_id: str, video, caption: str = "", file_id: str = None) -> dict:
        raise MessengerAPIError(_MEDIA_UNSUPPORTED_MSG)

    def send_document(self, chat_id: str, document, caption: str = "", file_id: str = None) -> dict:
        raise MessengerAPIError(_MEDIA_UNSUPPORTED_MSG)

    def send_audio(self, chat_id: str, audio, caption: str = "", file_id: str = None) -> dict:
        raise MessengerAPIError(_MEDIA_UNSUPPORTED_MSG)

    def send_voice(self, chat_id: str, voice, caption: str = "", file_id: str = None) -> dict:
        raise MessengerAPIError(_MEDIA_UNSUPPORTED_MSG)

    def send_animation(self, chat_id: str, animation, caption: str = "", file_id: str = None) -> dict:
        raise MessengerAPIError(_MEDIA_UNSUPPORTED_MSG)

    def send_sticker(self, chat_id: str, sticker, file_id: str = None) -> dict:
        raise MessengerAPIError(_MEDIA_UNSUPPORTED_MSG)

    def check_bot_is_admin(self, chat_id: str) -> bool:
        return bool(self.string_session)

    def get_chat_info(self, chat_id: str) -> dict:
        return {"title": chat_id, "username": chat_id.lstrip("@"), "type": "channel"}

    def get_bot_username(self) -> str:
        return ""
