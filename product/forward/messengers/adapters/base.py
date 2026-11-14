"""اینترفیس انتزاعی آداپتور پیام‌رسان‌ها و سلسله‌مراتب خطاها."""

from abc import ABC, abstractmethod


class MessengerError(Exception):
    """خطای پایه برای همه خطاهای پیام‌رسان."""


class MessengerAPIError(MessengerError):
    """خطای عمومی از سمت API پیام‌رسان."""


class MessengerRateLimitError(MessengerError):
    """محدودیت نرخ ارسال (HTTP 429)."""

    def __init__(self, retry_after: int = 0, message: str = "Rate limit exceeded"):
        """ذخیره ثانیه انتظار پیشنهادی توسط API."""
        super().__init__(message)
        self.retry_after = retry_after


class MessengerNotFoundError(MessengerError):
    """چت، کانال یا کاربر در پلتفرم یافت نشد."""


class MessengerPermissionError(MessengerError):
    """ربات یا اکانت دسترسی لازم (مثلاً ادمین بودن) را ندارد."""


class MessengerAdapter(ABC):
    """اینترفیس مشترک همه آداپتورهای پیام‌رسان (بله، ایتا، روبیکا، ...)."""

    platform_slug: str = ""

    @abstractmethod
    def send_text(self, chat_id: str, text: str, reply_markup: dict = None) -> dict:
        """ارسال پیام متنی و بازگرداندن دیکشنری حاوی message_id."""

    @abstractmethod
    def send_photo(self, chat_id: str, photo, caption: str = "", file_id: str = None) -> dict:
        """ارسال عکس با کپشن اختیاری."""

    @abstractmethod
    def send_video(self, chat_id: str, video, caption: str = "", file_id: str = None) -> dict:
        """ارسال ویدیو با کپشن اختیاری."""

    @abstractmethod
    def send_document(self, chat_id: str, document, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل با کپشن اختیاری."""

    def send_audio(self, chat_id: str, audio, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل صوتی (موزیک) با کپشن اختیاری؛ در صورت عدم پیاده‌سازی به send_document ارجاع می‌شود."""
        return self.send_document(chat_id, audio, caption=caption, file_id=file_id)

    def send_voice(self, chat_id: str, voice, caption: str = "", file_id: str = None) -> dict:
        """ارسال پیام صوتی (ویس) با کپشن اختیاری؛ در صورت عدم پیاده‌سازی به send_document ارجاع می‌شود."""
        return self.send_document(chat_id, voice, caption=caption, file_id=file_id)

    def send_animation(self, chat_id: str, animation, caption: str = "", file_id: str = None) -> dict:
        """ارسال گیف (با file_id یا آپلود جدید)."""

    def send_sticker(self, chat_id: str, sticker, file_id: str = None) -> dict:
        """ارسال استیکر (با file_id یا آپلود جدید)."""

    def send_media(self, chat_id: str, content_type: str, file, caption: str = "", file_id: str = None) -> dict:
        """ارسال فایل بر اساس نوع محتوا (dispatch به متد مناسب).

        :param chat_id: شناسه چت یا کانال مقصد.
        :param content_type: نوع محتوا (photo، video، audio، voice، document، animation، sticker).
        :param file: فایل یا شیء رسانه.
        :param caption: متن کپشن اختیاری.
        :param file_id: شناسه فایل کش‌شده در صورت پشتیبانی پلتفرم.
        :return: دیکشنری نتیجه ارسال شامل message_id و file_id.
        """
        if content_type == "photo":
            return self.send_photo(chat_id, file, caption, file_id=file_id)
        if content_type == "video":
            return self.send_video(chat_id, file, caption, file_id=file_id)
        if content_type == "audio":
            return self.send_audio(chat_id, file, caption, file_id=file_id)
        if content_type == "voice":
            return self.send_voice(chat_id, file, caption, file_id=file_id)
        if content_type == "document":
            return self.send_document(chat_id, file, caption, file_id=file_id)
        if content_type == "animation":
            return self.send_animation(chat_id, file, caption, file_id=file_id)
        if content_type == "sticker":
            return self.send_sticker(chat_id, file, file_id=file_id)
        raise ValueError(f"نوع محتوای پشتیبانی‌نشده: {content_type}")

    @abstractmethod
    def check_bot_is_admin(self, chat_id: str) -> bool:
        """بررسی ادمین بودن ربات یا دسترسی ارسال اکانت در کانال مشخص."""

    @abstractmethod
    def get_chat_info(self, chat_id: str) -> dict:
        """دریافت اطلاعات کانال (عنوان، نام کاربری، نوع)."""

    @abstractmethod
    def get_bot_username(self) -> str:
        """نام کاربری ربات برای ساخت Deep Link (بدون @)."""
