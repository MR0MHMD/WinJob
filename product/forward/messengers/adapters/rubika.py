"""آداپتور همگام پیام‌رسان روبیکا برای وین فوروارد، بر پایه API کلاینت (نسخه ۶) و کتابخانه requests."""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
import time
import re
import secrets
import string
from string import ascii_lowercase, ascii_uppercase, digits
from typing import Any, Dict, List, NoReturn, Optional, Tuple

import requests
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Util.Padding import pad, unpad

from .base import (
    MessengerAdapter,
    MessengerAPIError,
    MessengerNotFoundError,
    MessengerPermissionError,
    MessengerRateLimitError,
)
from .registry import register

logger = logging.getLogger(__name__)


class RubikaCrypto:
    """مجموعه ابزارهای رمزنگاری و امضای دیجیتال سازگار با پروتکل روبیکا (نسخه ۶)."""

    AES_IV: bytes = b"\x00" * 16

    _LOWER_TABLE = str.maketrans(
        ascii_lowercase,
        "".join(chr(((32 - (ord(c) - 97)) % 26) + 97) for c in ascii_lowercase),
    )
    _UPPER_TABLE = str.maketrans(
        ascii_uppercase,
        "".join(chr(((29 - (ord(c) - 65)) % 26) + 65) for c in ascii_uppercase),
    )

    @classmethod
    def decode_auth(cls, auth: str) -> str:
        """تبدیل کاراکترهای رشته auth یا کلید عمومی برای ارسال در بدنه درخواست‌های روبیکا.

        :param auth: رشته احراز هویت یا کلید عمومی رمزنگاری‌شده با Base64.
        :return: رشته تبدیل‌شده مطابق الگوریتم جایگزینی روبیکا.
        """
        result: List[str] = []
        for char in auth:
            if char in ascii_lowercase:
                result.append(char.translate(cls._LOWER_TABLE))
            elif char in ascii_uppercase:
                result.append(char.translate(cls._UPPER_TABLE))
            elif char in digits:
                result.append(chr(((13 - (ord(char) - 48)) % 10) + 48))
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def secret(length: int = 32) -> str:
        """تولید رشته تصادفی ۳۲ کاراکتری با حروف کوچک انگلیسی برای نشست موقت (tmp_session).

        :param length: طول رشته مورد نیاز (پیش‌فرض ۳۲).
        :return: رشته تصادفی امن.
        """
        return "".join(secrets.choice(string.ascii_lowercase) for _ in range(length))

    @staticmethod
    def passphrase(auth: str) -> str:
        """استخراج کلید ۳۲ بایتی AES از روی رشته auth یا tmp_session.

        :param auth: رشته ۳۲ کاراکتری احراز هویت یا نشست موقت.
        :return: کلید ۳۲ کاراکتری برای رمزگذاری و رمزگشایی AES-256-CBC.
        :raises ValueError: در صورتی که طول رشته ۳۲ کاراکتر نباشد.
        """
        if len(auth) != 32:
            raise ValueError("طول رشته auth باید دقیقاً ۳۲ کاراکتر باشد.")
        chunks = re.findall(r"\S{8}", auth)
        if len(chunks) != 4:
            raise ValueError("فرمت رشته auth برای استخراج کلید نامعتبر است.")
        reordered = chunks[2] + chunks[0] + chunks[3] + chunks[1]
        return "".join(chr(((ord(ch) - 97 + 9) % 26) + 97) for ch in reordered)

    @classmethod
    def encrypt(cls, data: Dict[str, Any] | str, key: str) -> str:
        """رمزگذاری داده متنی یا دیکشنری با الگوریتم AES-256-CBC و خروجی Base64.

        :param data: دیکشنری JSON یا رشته متنی برای رمزگذاری.
        :param key: کلید ۳۲ کاراکتری استخراج‌شده از passphrase.
        :return: رشته رمزگذاری‌شده با Base64.
        """
        if isinstance(data, dict):
            data = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        raw = pad(data.encode("utf-8"), AES.block_size)
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, cls.AES_IV)
        return base64.b64encode(cipher.encrypt(raw)).decode("utf-8")

    @classmethod
    def decrypt(cls, data_enc: str, key: str) -> Dict[str, Any]:
        """رمزگشایی پاسخ رمزنگاری‌شده سرور روبیکا به دیکشنری پایتون.

        :param data_enc: رشته رمزنگاری‌شده دریافتی از سرور.
        :param key: کلید ۳۲ کاراکتری استخراج‌شده از passphrase.
        :return: دیکشنری JSON رمزگشایی‌شده.
        """
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, cls.AES_IV)
        raw = base64.urlsafe_b64decode(data_enc.encode("utf-8"))
        decrypted = unpad(cipher.decrypt(raw), AES.block_size).decode("utf-8")
        return json.loads(decrypted)

    @staticmethod
    def create_keys() -> Tuple[str, str]:
        """تولید جفت کلید RSA-1024 برای امضای درخواست‌ها پس از ورود.

        :return: تاپل شامل (کلید عمومی کدگذاری‌شده برای روبیکا، کلید خصوصی با فرمت PEM).
        """
        rsa_key = RSA.generate(1024)
        public_b64 = base64.b64encode(rsa_key.publickey().export_key()).decode("utf-8")
        decoded_public_key = RubikaCrypto.decode_auth(public_b64)
        private_key_pem = rsa_key.export_key().decode("utf-8")
        return decoded_public_key, private_key_pem

    @staticmethod
    def decrypt_rsa_oaep(private_key_pem: str, data: str) -> str:
        """رمزگشایی رشته auth رمزنگاری‌شده با RSA-OAEP توسط سرور در مرحله signIn.

        :param private_key_pem: کلید خصوصی RSA در قالب PEM.
        :param data: رشته رمزنگاری‌شده با Base64 دریافتی از پاسخ signIn.
        :return: رشته ۳۲ کاراکتری auth رمزگشایی‌شده.
        """
        rsa_key = RSA.import_key(private_key_pem)
        cipher = PKCS1_OAEP.new(rsa_key)
        decrypted = cipher.decrypt(base64.b64decode(data))
        return decrypted.decode("utf-8")

    @staticmethod
    def sign(private_key_pem: str, data_enc: str) -> str:
        """تولید امضای دیجیتال RSA PKCS#1 v1.5 (با هش SHA-256) روی داده رمزگذاری‌شده.

        :param private_key_pem: کلید خصوصی RSA در قالب PEM.
        :param data_enc: رشته رمزگذاری‌شده payload.
        :return: امضای دیجیتال کدگذاری‌شده با Base64.
        """
        rsa_key = RSA.import_key(private_key_pem)
        signer = pkcs1_15.new(rsa_key)
        digest = SHA256.new(data_enc.encode("utf-8"))
        return base64.b64encode(signer.sign(digest)).decode("utf-8")


@register
class RubikaAdapter(MessengerAdapter):
    """آداپتور همگام روبیکا با استفاده از کلاینت اکانت شخصی و کتابخانه requests."""

    platform_slug = "rubika"
    API_VERSION = "6"
    DC_DISCOVERY_URL = "https://getdcmess.iranlms.ir/"
    FALLBACK_API_URLS = [
        "https://messengerg2c1.iranlms.ir",
        "https://messengerg2c2.iranlms.ir",
        "https://messengerg2c4.iranlms.ir",
    ]
    TIMEOUT = 30
    CHUNK_SIZE = 524288  # ۵۱۲ کیلوبایت برای آپلود پایدارتر و سریع‌تر
    _CACHED_API_URL: Optional[str] = None
    _CACHED_API_URL_TS: float = 0.0
    _DC_CACHE_TTL: float = 600.0

    DEFAULT_CLIENT = {
        "app_name": "Main",
        "app_version": "2.4.6",
        "platform": "PWA",
        "package": "m.rubika.ir",
        "lang_code": "fa",
    }

    def __init__(
        self,
        auth: Optional[str] = None,
        private_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ) -> None:
        """مقداردهی اولیه آداپتور روبیکا با اطلاعات نشست کاربر.

        :param auth: توکن دائمی ۳۲ کاراکتری اکانت روبیکا.
        :param private_key: کلید خصوصی RSA در قالب PEM.
        :param api_url: آدرس اختیاری سرور API روبیکا (DC).
        """
        self._auth = auth
        self._private_key = private_key
        self._api_url = api_url
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Origin": "https://web.rubika.ir",
                "Referer": "https://web.rubika.ir/",
                "Content-Type": "application/json",
            }
        )

    def _get_api_url(self) -> str:
        """دریافت آدرس دیتاسنتر فعال روبیکا با کش ۱۰ دقیقه‌ای برای حذف تاخیر اضافی در هر ارسال.

        :return: آدرس URL دیتاسنتر روبیکا.
        """
        if self._api_url:
            return self._api_url
        now = time.monotonic()
        if self.__class__._CACHED_API_URL and (now - self.__class__._CACHED_API_URL_TS) < self._DC_CACHE_TTL:
            self._api_url = self.__class__._CACHED_API_URL
            return self._api_url
        try:
            resp = requests.get(self.DC_DISCOVERY_URL, timeout=8)
            resp.raise_for_status()
            payload = resp.json()
            urls = payload.get("data", {}).get("default_api_urls", [])
            if urls:
                self._api_url = urls[0]
                self.__class__._CACHED_API_URL = self._api_url
                self.__class__._CACHED_API_URL_TS = now
                return self._api_url
        except requests.RequestException:
            pass
        self._api_url = self.FALLBACK_API_URLS[0]
        return self._api_url

    def _handle_api_error(self, status: str, status_det: str) -> NoReturn:
        """تبدیل کدهای وضعیت خطای روبیکا به استثناهای استاندارد آداپتور.

        :param status: وضعیت کلی خطا (مانند ERROR_GENERIC یا INVALID_AUTH).
        :param status_det: جزئیات دقیق خطا از سمت سرور.
        """
        combined = f"{status} {status_det}".lower()
        if "not_registered" in combined or "invalid_input" in combined or "not_found" in combined:
            raise MessengerNotFoundError(f"{status}: {status_det}")
        if "invalid_auth" in combined or "not_admin" in combined or "permission" in combined or "forbidden" in combined:
            raise MessengerPermissionError(f"{status}: {status_det}")
        if "too_requests" in combined or "flood" in combined or "rate" in combined:
            raise MessengerRateLimitError(0, f"{status}: {status_det}")
        raise MessengerAPIError(f"خطای روبیکا ({status}): {status_det}")

    def _request(
        self,
        method: str,
        input_data: Dict[str, Any],
        use_tmp_session: bool = False,
        tmp_session: Optional[str] = None,
    ) -> Dict[str, Any]:
        """رمزگذاری، امضا و ارسال درخواست همگام به API روبیکا و رمزگشایی پاسخ.

        :param method: نام متد در API روبیکا (مانند sendCode، sendMessage و ...).
        :param input_data: دیکشنری پارامترهای ورودی متد.
        :param use_tmp_session: در صورت True بودن از نشست موقت بدون امضای RSA استفاده می‌شود.
        :param tmp_session: رشته ۳۲ کاراکتری نشست موقت (در صورت وجود).
        :return: دیکشنری data استخراج‌شده از پاسخ رمزگشایی‌شده.
        """
        inner_payload = {
            "client": self.DEFAULT_CLIENT,
            "method": method,
            "input": input_data,
        }

        if use_tmp_session:
            session_token = tmp_session or RubikaCrypto.secret(32)
            aes_key = RubikaCrypto.passphrase(session_token)
            data_enc = RubikaCrypto.encrypt(inner_payload, aes_key)
            body: Dict[str, Any] = {
                "api_version": self.API_VERSION,
                "tmp_session": session_token,
                "data_enc": data_enc,
            }
        else:
            if not self._auth or not self._private_key:
                raise MessengerPermissionError("نشست روبیکا (auth و private_key) ثبت یا تایید نشده است.")
            aes_key = RubikaCrypto.passphrase(self._auth)
            data_enc = RubikaCrypto.encrypt(inner_payload, aes_key)
            body = {
                "api_version": self.API_VERSION,
                "auth": RubikaCrypto.decode_auth(self._auth),
                "data_enc": data_enc,
                "sign": RubikaCrypto.sign(self._private_key, data_enc),
            }

        try:
            response = self._session.post(self._get_api_url(), json=body, timeout=self.TIMEOUT)
            response.raise_for_status()
            res_json = response.json()
        except requests.RequestException as exc:
            raise MessengerAPIError(f"خطا در ارتباط با سرور روبیکا: {exc}") from exc
        except ValueError as exc:
            raise MessengerAPIError(f"پاسخ نامعتبر از سرور روبیکا: {exc}") from exc

        if "data_enc" in res_json:
            try:
                decrypted = RubikaCrypto.decrypt(res_json["data_enc"], aes_key)
            except Exception as exc:
                raise MessengerAPIError(f"خطا در رمزگشایی پاسخ روبیکا: {exc}") from exc
        else:
            decrypted = res_json

        status = decrypted.get("status", "")
        if status and status != "OK":
            self._handle_api_error(status, decrypted.get("status_det", ""))
        return decrypted.get("data", decrypted)

    # ============================================================
    # متدهای احراز هویت دو مرحله‌ای (OTP)
    # ============================================================

    def send_code(
        self,
        phone_number: str,
        pass_key: Optional[str] = None,
        send_type: str = "SMS",
    ) -> Dict[str, Any]:
        """ارسال کد تایید یک‌بارمصرف (OTP) به شماره موبایل کاربر در روبیکا.

        :param phone_number: شماره موبایل کاربر (ترجیحاً با فرمت 98912... یا 0912...).
        :param pass_key: رمز عبور دومرحله‌ای در صورت فعال بودن (اختیاری).
        :param send_type: روش ارسال کد ('SMS' یا 'Internal').
        :return: دیکشنری شامل phone_code_hash و tmp_session جهت نگهداری در سشن جنگو.
        """
        tmp_session = RubikaCrypto.secret(32)
        data = self._request(
            method="sendCode",
            input_data={
                "phone_number": phone_number,
                "pass_key": pass_key,
                "send_type": send_type,
            },
            use_tmp_session=True,
            tmp_session=tmp_session,
        )
        return {
            "phone_code_hash": data.get("phone_code_hash"),
            "tmp_session": tmp_session,
            "raw": data,
        }

    def sign_in(
        self,
        phone_number: str,
        phone_code: str,
        phone_code_hash: str,
        tmp_session: str,
    ) -> Dict[str, Any]:
        """تکمیل فرآیند ورود با کد تایید و دریافت توکن دائمی و کلید خصوصی.

        :param phone_number: شماره موبایل کاربر.
        :param phone_code: کد تایید ۵ رقمی واردشده توسط کاربر.
        :param phone_code_hash: هش دریافت‌شده از مرحله send_code.
        :param tmp_session: شناسه نشست موقت تولیدشده در مرحله send_code.
        :return: دیکشنری شامل auth، private_key و اطلاعات کاربر در روبیکا.
        """
        decoded_public_key, private_key_pem = RubikaCrypto.create_keys()
        data = self._request(
            method="signIn",
            input_data={
                "phone_code": str(phone_code).strip(),
                "phone_number": phone_number,
                "phone_code_hash": phone_code_hash,
                "public_key": decoded_public_key,
            },
            use_tmp_session=True,
            tmp_session=tmp_session,
        )

        raw_auth = data.get("auth")
        if not raw_auth:
            status = data.get("status", "SIGN_IN_FAILED")
            raise MessengerAPIError(f"ورود با کد تایید ناموفق بود: {status}")

        try:
            auth_token = RubikaCrypto.decrypt_rsa_oaep(private_key_pem, raw_auth)
        except Exception as exc:
            raise MessengerAPIError(f"خطا در رمزگشایی توکن auth با RSA-OAEP: {exc}") from exc

        self._auth = auth_token
        self._private_key = private_key_pem

        # ثبت دستگاه در سرور روبیکا برای فعال‌سازی رسمی نشست در لیست نشست‌های کاربر
        self.register_device(device_model="WinForward")

        return {
            "auth": auth_token,
            "private_key": private_key_pem,
            "user": data.get("user", {}),
            "raw": data,
        }

    def register_device(self, device_model: str = "WinForward") -> Dict[str, Any]:
        """ثبت دستگاه و نشست کلاینت در سرور روبیکا (registerDevice) بلافاصله پس از ورود.

        :param device_model: نام نمایشی دستگاه در لیست نشست‌های فعال روبیکا.
        :return: پاسخ سرور روبیکا برای ثبت دستگاه.
        """
        user_agent = self._session.headers.get("User-Agent", "")
        device_hash = "2" + "".join(re.findall(r"\d+", user_agent))
        return self._request(
            "registerDevice",
            {
                "token": "",
                "lang_code": self.DEFAULT_CLIENT["lang_code"],
                "token_type": "Firebase",
                "app_version": f"PW_{self.DEFAULT_CLIENT['app_version']}",
                "system_version": "Windows 10",
                "device_model": device_model,
                "device_hash": device_hash,
            },
        )

    # ============================================================
    # متدهای آپلود تکه‌ای و ارسال انواع پیام و رسانه
    # ============================================================

    @staticmethod
    def _read_file_bytes(file_obj: Any) -> Tuple[bytes, str]:
        """خواندن بایت‌ها و استخراج نام فایل از آبجکت‌های فایل جنگو، ContentFile یا bytes.

        :param file_obj: فایل ارسالی (FieldFile، ContentFile، مسیر یا بایت خام).
        :return: تاپل شامل (بایت‌های فایل، نام فایل).
        """
        if isinstance(file_obj, (bytes, bytearray)):
            return bytes(file_obj), "file.bin"

        filename = getattr(file_obj, "name", "file.bin") or "file.bin"
        filename = filename.split("/")[-1].split("\\")[-1]

        if hasattr(file_obj, "open"):
            file_obj.open("rb")
            try:
                content = file_obj.read()
            finally:
                file_obj.close()
            return content, filename

        if hasattr(file_obj, "read"):
            content = file_obj.read()
            return content, filename

        raise MessengerAPIError("فرمت فایل ورودی برای آپلود در روبیکا معتبر نیست.")

    _FALLBACK_THUMB_B64 = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcv"
        "Jik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7"
        "Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAAgACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEA"
        "AAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEI"
        "I0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4"
        "eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo"
        "6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQA"
        "AQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNE"
        "RUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
        "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDy2iiitRBRRRQA"
        "UUUUAFFFFAH/2Q=="
    )

    @classmethod
    def _extract_image_meta(cls, file_bytes: bytes) -> Tuple[int, int, str]:
        """استخراج عرض، ارتفاع و تصویر بندانگشتی Base64 (thumb_inline) برای عکس در روبیکا."""
        try:
            from PIL import Image

            with Image.open(io.BytesIO(file_bytes)) as im:
                width, height = im.size
                rgb_im = im.convert("RGB")
                if height > width:
                    new_h = 40
                    new_w = max(1, round(new_h * width / max(1, height)))
                else:
                    new_w = 40
                    new_h = max(1, round(new_w * height / max(1, width)))
                resized = rgb_im.resize((new_w, new_h))
                out = io.BytesIO()
                resized.save(out, format="JPEG", quality=70)
                thumb_b64 = base64.b64encode(out.getvalue()).decode("ascii")
                return int(width), int(height), thumb_b64
        except Exception:
            return 200, 200, cls._FALLBACK_THUMB_B64

    @classmethod
    def _extract_video_meta(cls, file_bytes: bytes, ext: str = "mp4") -> Tuple[int, int, int, str]:
        """برگرداندن سریع متادیتا و تصویر بندانگشتی استاندارد برای ویدیو و گیف بدون سربار دیسک و ffmpeg."""
        return 480, 360, 1, cls._FALLBACK_THUMB_B64
        ffmpeg_bin = None
        if not ffmpeg_bin:
            return width, height, duration, thumb_b64

        tmp_video = None
        tmp_thumb = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as vf:
                vf.write(file_bytes)
                tmp_video = vf.name
            tmp_thumb = tmp_video + ".jpg"

            ffprobe_bin = shutil.which("ffprobe")
            if ffprobe_bin:
                probe = subprocess.run(
                    [
                        ffprobe_bin, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,duration",
                        "-of", "json", tmp_video,
                    ],
                    capture_output=True, text=True, timeout=10, check=False,
                )
                if probe.returncode == 0 and probe.stdout:
                    streams = json.loads(probe.stdout).get("streams") or []
                    if streams:
                        width = int(streams[0].get("width") or width)
                        height = int(streams[0].get("height") or height)
                        dur_val = streams[0].get("duration")
                        if dur_val:
                            duration = max(1, int(float(dur_val)))

            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-i", tmp_video,
                    "-ss", "00:00:00.5", "-vframes", "1",
                    "-vf", "scale=40:-1", tmp_thumb,
                ],
                capture_output=True, timeout=10, check=False,
            )
            if os.path.exists(tmp_thumb) and os.path.getsize(tmp_thumb) > 0:
                with open(tmp_thumb, "rb") as tf:
                    thumb_b64 = base64.b64encode(tf.read()).decode("ascii")
        except Exception:
            pass
        finally:
            for p in (tmp_video, tmp_thumb):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        return width, height, duration, thumb_b64

    def _upload_file(self, file_obj: Any, default_filename: str) -> Dict[str, Any]:
        """آپلود تکه‌ای فایل به سرورهای روبیکا با استفاده از متد requestSendFile.

        :param file_obj: شیء فایل قابل خواندن یا بایت‌های خام.
        :param default_filename: نام پیش‌فرض فایل در صورت نبود نام یا پسوند.
        :return: دیکشنری اطلاعات فایل آپلودشده شامل file_id، dc_id، access_hash_rec و بایت‌های فایل.
        """
        file_bytes, filename = self._read_file_bytes(file_obj)
        if "." not in filename:
            filename = default_filename

        file_size = len(file_bytes)
        mime = filename.rsplit(".", 1)[-1].lower()

        req_data = self._request(
            "requestSendFile",
            {
                "file_name": filename,
                "size": int(file_size),
                "mime": mime,
            },
        )

        file_id = str(req_data["id"])
        dc_id = str(req_data["dc_id"])
        upload_url = req_data["upload_url"]
        access_hash_send = req_data["access_hash_send"]

        total_parts = max(1, (file_size + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE)
        upload_headers_base = {
            "auth": self._auth,
            "file-id": file_id,
            "total-part": str(total_parts),
            "access-hash-send": access_hash_send,
        }

        upload_result: Dict[str, Any] = {}
        for index in range(total_parts):
            start = index * self.CHUNK_SIZE
            chunk = file_bytes[start : start + self.CHUNK_SIZE]
            headers = {
                **upload_headers_base,
                "part-number": str(index + 1),
                "chunk-size": str(len(chunk)),
                "Content-Type": "application/octet-stream",
            }
            try:
                resp = self._session.post(
                    upload_url,
                    data=chunk,
                    headers=headers,
                    timeout=self.TIMEOUT * 4,
                )
                resp.raise_for_status()
                upload_result = resp.json()
            except requests.RequestException as exc:
                raise MessengerAPIError(f"خطا در آپلود قطعه {index + 1} به روبیکا: {exc}") from exc
            except ValueError as exc:
                raise MessengerAPIError(f"پاسخ نامعتبر از سرور آپلود روبیکا: {exc}") from exc

            if upload_result.get("status") == "ERROR_TRY_AGAIN":
                raise MessengerAPIError("سرور آپلود روبیکا درخواست تلاش مجدد داد (ERROR_TRY_AGAIN).")

        if upload_result.get("status") != "OK":
            raise MessengerAPIError(
                f"آپلود فایل در روبیکا ناموفق بود: {upload_result.get('status_det', upload_result)}"
            )

        access_hash_rec = upload_result.get("data", {}).get("access_hash_rec")
        if not access_hash_rec:
            raise MessengerAPIError("مقدار access_hash_rec از سرور آپلود روبیکا دریافت نشد.")

        return {
            "file_id": file_id,
            "mime": mime,
            "dc_id": dc_id,
            "access_hash_rec": access_hash_rec,
            "file_name": filename,
            "size": file_size,
            "_file_bytes": file_bytes,
        }

    def _send_file_inline(
        self,
        chat_id: str,
        file_obj: Any,
        default_filename: str,
        rubika_type: str,
        caption: str = "",
        extra_inline: Optional[Dict[str, Any]] = None,
        cached_file_inline: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """ساخت ساختار دقیق file_inline بر اساس نوع رسانه و فراخوانی sendMessage در روبیکا.

        در صورتی که cached_file_inline از آپلود کانال قبلی در همان جاب موجود باشد، بدون آپلود مجدد
        مستقیماً از همان متادیتا استفاده می‌شود تا ارسال به کانال‌های بعدی روبیکا آنی انجام شود.
        """
        if isinstance(cached_file_inline, dict) and cached_file_inline.get("file_id") and cached_file_inline.get("access_hash_rec"):
            file_inline = dict(cached_file_inline)
            file_inline["type"] = rubika_type
            logger.info("[rubika] Reusing cached file_id=%s (skipping upload) -> %s", file_inline["file_id"], chat_id)
        else:
            logger.info("[rubika] Uploading new media (%s) -> %s", rubika_type, chat_id)
            uploaded = self._upload_file(file_obj, default_filename=default_filename)
            file_bytes = uploaded.pop("_file_bytes", b"")

            file_inline = {
                **uploaded,
                "type": rubika_type,
            }

            if rubika_type == "Image":
                w, h, thumb = self._extract_image_meta(file_bytes)
                file_inline.update({
                    "width": w,
                    "height": h,
                    "thumb_inline": thumb,
                    "is_spoil": False,
                })
            elif rubika_type in ("Video", "Gif"):
                w, h, dur, thumb = self._extract_video_meta(file_bytes, ext=uploaded.get("mime", "mp4"))
                file_inline.update({
                    "width": w,
                    "height": h,
                    "time": dur,
                    "thumb_inline": thumb,
                    "auto_play": False if rubika_type == "Video" else True,
                    "is_spoil": False,
                })
            elif rubika_type == "Music":
                file_inline.update({
                    "time": 1,
                    "music_performer": "",
                })
            elif rubika_type == "Voice":
                file_inline.update({
                    "time": 1000,
                })

        if extra_inline:
            file_inline.update(extra_inline)

        input_data: Dict[str, Any] = {
            "object_guid": chat_id,
            "rnd": random.randint(100000, 999999999),
            "file_inline": file_inline,
        }
        if caption:
            input_data["text"] = caption

        result = self._request("sendMessage", input_data)
        msg_id = (
            result.get("message_update", {}).get("message_id")
            or result.get("message_id")
            or ""
        )
        return {
            "message_id": str(msg_id),
            "file_id": file_inline["file_id"],
            "rubika_file_inline": file_inline,
        }

    def send_text(self, chat_id: str, text: str, reply_markup: dict = None) -> dict:
        """ارسال پیام متنی ساده به کانال یا گفت‌وگوی روبیکا.

        :param chat_id: شناسه GUID مقصد (مانند c0...).
        :param text: متن پیام ارسالی.
        :param reply_markup: پارامتر سازگاری با اینترفیس پایه (در کلاینت شخصی استفاده نمی‌شود).
        :return: دیکشنری حاوی message_id.
        """
        result = self._request(
            "sendMessage",
            {
                "object_guid": chat_id,
                "text": text,
                "rnd": random.randint(100000, 999999999),
            },
        )
        msg_id = (
            result.get("message_update", {}).get("message_id")
            or result.get("message_id")
            or ""
        )
        return {"message_id": str(msg_id)}

    def send_photo(self, chat_id: str, photo, caption: str = "", file_id: str = None) -> dict:
        """ارسال عکس به کانال روبیکا همراه با کپشن اختیاری.

        :param chat_id: شناسه GUID کانال یا چت مقصد.
        :param photo: فایل تصویر.
        :param caption: متن کپشن اختیاری.
        :param file_id: شناسه فایل از پیش آپلودشده (در روبیکا آپلود مستقیم انجام می‌شود).
        :return: دیکشنری حاوی message_id و file_id.
        """
        return self._send_file_inline(chat_id, photo, "photo.jpg", "Image", caption=caption, cached_file_inline=file_id if isinstance(file_id, dict) else None)

    def send_video(self, chat_id: str, video, caption: str = "", file_id: str = None) -> dict:
        """ارسال ویدیو به کانال روبیکا همراه با کپشن اختیاری.

        :param chat_id: شناسه GUID کانال یا چت مقصد.
        :param video: فایل ویدیو.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id و file_id.
        """
        return self._send_file_inline(chat_id, video, "video.mp4", "Video", caption=caption, cached_file_inline=file_id if isinstance(file_id, dict) else None)

    def send_audio(self, chat_id: str, audio, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل صوتی (موزیک/پادکست) به کانال روبیکا همراه با کپشن اختیاری.

        :param chat_id: شناسه GUID کانال یا چت مقصد.
        :param audio: فایل صوتی (مانند mp3).
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id و file_id.
        """
        return self._send_file_inline(chat_id, audio, "audio.mp3", "Music", caption=caption, cached_file_inline=file_id if isinstance(file_id, dict) else None)

    def send_voice(self, chat_id: str, voice, caption: str = "", file_id: str = None) -> dict:
        """ارسال پیام صوتی (ویس) به کانال روبیکا همراه با کپشن اختیاری.

        :param chat_id: شناسه GUID کانال یا چت مقصد.
        :param voice: فایل ویس (مانند ogg).
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id و file_id.
        """
        return self._send_file_inline(
            chat_id,
            voice,
            "voice.ogg",
            "Voice",
            caption=caption,
            extra_inline={"time": 1000},
            cached_file_inline=file_id if isinstance(file_id, dict) else None,
        )

    def send_document(self, chat_id: str, document, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل یا سند به کانال روبیکا همراه با کپشن اختیاری.

        :param chat_id: شناسه GUID کانال یا چت مقصد.
        :param document: فایل ارسالی.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id و file_id.
        """
        return self._send_file_inline(chat_id, document, "document.bin", "File", caption=caption, cached_file_inline=file_id if isinstance(file_id, dict) else None)

    def send_animation(self, chat_id: str, animation, caption: str = "", file_id: str = None) -> dict:
        """ارسال گیف (انیمیشن) به کانال روبیکا همراه با کپشن اختیاری.

        :param chat_id: شناسه GUID کانال یا چت مقصد.
        :param animation: فایل گیف یا ویدیوی کوتاه.
        :param caption: متن کپشن اختیاری.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :return: دیکشنری حاوی message_id و file_id.
        """
        return self._send_file_inline(chat_id, animation, "animation.gif", "Gif", caption=caption, cached_file_inline=file_id if isinstance(file_id, dict) else None)

    def send_sticker(self, chat_id: str, sticker, file_id: str = None) -> dict:
        """جلوگیری از ارسال استیکر به روبیکا به دلیل عدم پشتیبانی از استیکرهای بیرونی.

        :param chat_id: شناسه GUID کانال یا چت مقصد.
        :param sticker: فایل استیکر.
        :param file_id: پارامتر سازگاری با اینترفیس پایه.
        :raises MessengerAPIError: همیشه خطای عدم پشتیبانی از استیکر برمی‌گرداند.
        """
        raise MessengerAPIError("روبیکا از ارسال استیکر بیرونی پشتیبانی نمی‌کند.")

    # ============================================================
    # متدهای مدیریت و بررسی کانال‌ها
    # ============================================================

    def get_object_by_username(self, username: str) -> Dict[str, Any]:
        """دریافت اطلاعات کانال یا کاربر از طریق نام کاربری (بدون @).

        :param username: نام کاربری کانال در روبیکا.
        :return: دیکشنری اطلاعات کانال شامل channel_guid و عنوان.
        """
        clean_username = username.strip().lstrip("@")
        return self._request("getObjectByUsername", {"username": clean_username})

    def get_chats(self, start_id: Optional[str] = None) -> Dict[str, Any]:
        """دریافت لیست گفت‌وگوها و کانال‌های اکانت متصل‌شده کاربر.

        :param start_id: شناسه صفحه‌بندی برای دریافت ادامه لیست (اختیاری).
        :return: دیکشنری شامل لیست chats و وضعیت ادامه.
        """
        return self._request("getChats", {"start_id": start_id})

    def get_user_channels(self) -> List[Dict[str, str]]:
        """استخراج لیست کانال‌هایی که کاربر در آن‌ها عضو یا ادمین است.

        :return: لیست دیکشنری‌ها شامل chat_id، title و username هر کانال.
        """
        data = self.get_chats()
        chats = data.get("chats", [])
        channels: List[Dict[str, str]] = []
        for chat in chats:
            obj_guid = chat.get("object_guid", "")
            if not obj_guid.startswith("c0"):
                continue
            abs_obj = chat.get("abs_object", {}) or {}
            access = chat.get("access", []) or []
            # فقط کانال‌هایی که کاربر دسترسی ارسال پیام دارد یا سازنده/ادمین است
            if access and "SendMessages" not in access and "SetAdmin" not in access:
                continue
            channels.append(
                {
                    "chat_id": obj_guid,
                    "title": abs_obj.get("title") or obj_guid,
                    "username": abs_obj.get("username") or "",
                    "avatar_meta": abs_obj.get("avatar_thumbnail") or {},
                }
            )
        return channels

    def get_chat_info(self, chat_id: str) -> dict:
        """دریافت اطلاعات کانال روبیکا (عنوان، نام کاربری، نوع).

        :param chat_id: شناسه GUID کانال یا نام کاربری آن.
        :return: دیکشنری شامل title، username و type.
        """
        target_guid = chat_id.strip()
        if not target_guid.startswith("c0"):
            obj = self.get_object_by_username(target_guid)
            channel_obj = obj.get("channel") or {}
            if not channel_obj:
                raise MessengerNotFoundError("کانال با این نام کاربری در روبیکا یافت نشد.")
            return {
                "chat_id": channel_obj.get("channel_guid", ""),
                "title": channel_obj.get("channel_title", "") or target_guid,
                "username": channel_obj.get("username", "") or "",
                "type": "channel",
            }

        data = self._request("getChannelInfo", {"channel_guid": target_guid})
        channel_obj = data.get("channel") or {}
        return {
            "chat_id": channel_obj.get("channel_guid", target_guid),
            "title": channel_obj.get("channel_title", "") or target_guid,
            "username": channel_obj.get("username", "") or "",
            "type": "channel",
        }

    def check_bot_is_admin(self, chat_id: str) -> bool:
        """بررسی دسترسی ارسال پیام توسط اکانت کاربر در کانال مشخص.

        :param chat_id: شناسه GUID کانال روبیکا.
        :return: True در صورت داشتن دسترسی ارسال یا ادمین بودن، در غیر این صورت False.
        """
        try:
            data = self._request("getChannelInfo", {"channel_guid": chat_id})
            chat = data.get("chat", {}) or {}
            access = chat.get("access", []) or []
            if access:
                return "SendMessages" in access or "SetAdmin" in access
            return bool(data.get("channel"))
        except MessengerError:
            return False

    def get_bot_username(self) -> str:
        """دریافت نام کاربری ربات (برای سازگاری با اینترفیس پایه؛ در کلاینت شخصی خالی است).

        :return: رشته خالی.
        """
        return ""

    def _get_storage_url(self, dc_id: str) -> str:
        """دریافت آدرس دقیق سرور دانلود فایل از سرویس کشف دیتاسنتر روبیکا (کلید storage)."""
        base_url = f"https://messenger{dc_id}.iranlms.ir"
        try:
            resp = self._session.get(self.DC_DISCOVERY_URL, timeout=8)
            if resp.status_code == 200:
                data = resp.json().get("data") or {}
                storage_map = data.get("storage") or data.get("storages") or {}
                if str(dc_id) in storage_map and storage_map[str(dc_id)]:
                    base_url = str(storage_map[str(dc_id)]).rstrip("/")
        except Exception:
            pass
        if base_url.endswith("/GetFile.ashx"):
            return base_url
        return f"{base_url}/GetFile.ashx"

    def download_chat_avatar(self, chat_id: str, avatar_meta: Optional[Dict[str, Any]] = None) -> Optional[bytes]:
        """دانلود بایت‌های عکس پروفایل کانال روبیکا مطابق متد download کتابخانه rubpy (POST به GetFile.ashx)."""
        try:
            meta = avatar_meta or {}
            if not meta.get("file_id") and str(chat_id).startswith("c0"):
                data = self._request("getChannelInfo", {"channel_guid": chat_id})
                channel_obj = data.get("channel") or {}
                chat_abs = (data.get("chat") or {}).get("abs_object") or {}
                meta = channel_obj.get("avatar_thumbnail") or chat_abs.get("avatar_thumbnail") or {}

            file_id = meta.get("file_id")
            dc_id = meta.get("dc_id")
            access_hash_rec = meta.get("access_hash_rec") or meta.get("access_hash")
            if not (file_id and dc_id and access_hash_rec and self._auth):
                logger.warning(
                    "[rubika] Missing avatar metadata for %s: keys=%s",
                    chat_id,
                    list(meta.keys()) if isinstance(meta, dict) else type(meta),
                )
                return None

            url = self._get_storage_url(str(dc_id))
            chunk_size = 131072  # 128 KB مطابق پیش‌فرض rubpy
            size = int(meta.get("size") or 0)

            base_headers = {
                "auth": self._auth,
                "access-hash-rec": str(access_hash_rec),
                "file-id": str(file_id),
                "user-agent": self._session.headers.get("User-Agent", ""),
            }

            result = bytearray()
            if size > 0:
                for start in range(0, size, chunk_size):
                    end = min(start + chunk_size, size) - 1
                    headers = {
                        **base_headers,
                        "start-index": str(start),
                        "last-index": str(end),
                    }
                    resp = requests.post(url, headers=headers, timeout=15)
                    if resp.status_code != 200 or not resp.content:
                        logger.warning(
                            "[rubika] GetFile failed for %s: status=%s url=%s len=%s",
                            chat_id,
                            resp.status_code,
                            url,
                            len(resp.content or b""),
                        )
                        return None
                    result.extend(resp.content)
            else:
                start = 0
                for _ in range(16):  # حداکثر ۲ مگابایت برای آواتار
                    end = start + chunk_size - 1
                    headers = {
                        **base_headers,
                        "start-index": str(start),
                        "last-index": str(end),
                    }
                    resp = requests.post(url, headers=headers, timeout=15)
                    if resp.status_code != 200:
                        logger.warning(
                            "[rubika] GetFile failed for %s: status=%s url=%s len=%s",
                            chat_id,
                            resp.status_code,
                            url,
                            len(resp.content or b""),
                        )
                        return None
                    if not resp.content:
                        break
                    result.extend(resp.content)
                    if len(resp.content) < chunk_size:
                        break
                    start += len(resp.content)

            if len(result) > 100:
                return bytes(result)
            logger.warning(
                "[rubika] GetFile returned empty/too-small body for %s: url=%s len=%s",
                chat_id,
                url,
                len(result),
            )
        except Exception as exc:
            logger.warning("[rubika] download_chat_avatar failed for %s: %s", chat_id, exc)
        return None
