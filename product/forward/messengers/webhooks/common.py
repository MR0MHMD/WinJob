"""ماژول وب‌هوک ربات‌های بله و تلگرام (وین‌فوروارد)."""

import html
import json
import logging
import re

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import Platform
from product.forward.broadcast.models import (
    BroadcastChannel,
    BroadcastHub,
    BroadcastJob,
    BroadcastMessage,
    BroadcastTarget,
    ChannelPreset,
)
from product.forward.broadcast.services.channel_sync import finalize_verification, sync_channel_avatar
from product.forward.broadcast.services.dispatcher import enqueue_dispatch_job
from product.forward.messengers.adapters.registry import get_adapter
from product.forward.messengers.models import BotUser, ConnectToken

logger = logging.getLogger(__name__)

_WINJOB_FORWARD_URL = "https://winjob.ir/forward/"
_WINJOB_PLANS_URL = "https://winjob.ir/forward/subscriptions/"
_WINJOB_PRESETS_URL = "https://winjob.ir/forward/presets/"

_PLATFORM_NAMES_FA = {
    "bale": "بله",
    "telegram": "تلگرام",
    "soroush": "سروش‌پلاس",
}

_USER_KEYBOARD = {
    "keyboard": [
        [{"text": "📢 کانال‌های من"}, {"text": "📦 پکیج‌های ارسال"}],
        [{"text": "🪙 حساب و توکن"}, {"text": "📤 ارسال پیام"}],
        [{"text": "❓ راهنما و پشتیبانی"}, {"text": "🌐 پنل وب"}],
    ],
    "resize_keyboard": True,
}

_GUEST_KEYBOARD = {
    "keyboard": [
        [{"text": "🌐 ورود به پنل وینجاب"}],
    ],
    "resize_keyboard": True,
}

_CANCEL_SEND_KEYBOARD = {
    "keyboard": [
        [{"text": "🔙 بازگشت به منوی اصلی"}],
    ],
    "resize_keyboard": True,
}


def _md_to_tg_html(text: str) -> str:
    """تبدیل ایمن Markdown ساده پیام‌های سیستمی ربات به HTML استاندارد تلگرام."""
    escaped = html.escape(text or "")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped, flags=re.DOTALL)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped



def _bot_send(adapter, chat_id, text: str, reply_markup: dict = None, platform_slug: str = "bale"):
    """ارسال پیام سیستمی ربات با فرمت مناسب هر پیام‌رسان."""
    if platform_slug == "telegram":
        return adapter.send_text(chat_id, _md_to_tg_html(text), reply_markup=reply_markup, parse_mode="HTML")
    return adapter.send_text(chat_id, text, reply_markup=reply_markup)



def _set_awaiting_broadcast(bot_user: BotUser, state: bool) -> None:
    """ثبت یا پاکسازی وضعیت انتظار دریافت پیام برای ارسال روی session_data کاربر."""
    data = dict(bot_user.session_data or {})
    if state:
        data["awaiting_broadcast"] = True
    else:
        data.pop("awaiting_broadcast", None)
    bot_user.session_data = data
    bot_user.save(update_fields=["session_data"])



def _is_our_bot_user(member: dict, platform_slug: str) -> bool:
    """بررسی اینکه آیا عضو اضافه یا حذف‌شده در گروه دقیقاً خود ربات وین‌فوروارد است یا خیر."""
    if not isinstance(member, dict):
        return False
    adapter = get_adapter(platform_slug)
    token = getattr(adapter, "_token", "") if adapter else ""
    bot_id = token.split(":", 1)[0] if ":" in token else ""
    if bot_id and str(member.get("id", "")) == bot_id:
        return True
    if adapter:
        try:
            bot_uname = (adapter.get_bot_username() or "").lower()
            if bot_uname and (member.get("username") or "").lower() == bot_uname:
                return True
        except Exception:
            pass
    return bool(member.get("is_bot"))



def _is_soroush_locked_for_message(msg) -> tuple[bool, str]:
    """بررسی قفل بودن کانال‌های سروش‌پلاس برای پیام فعلی (فقط متن و رسانه دارای کپشن مجاز است)."""
    ctype = getattr(msg, "content_type", "text")
    if ctype in ("sticker", "animation"):
        return True, "ارسال استیکر و گیف در سروش‌پلاس پشتیبانی نمی‌شود."
    if ctype != "text" and not (getattr(msg, "text", "") or "").strip():
        return True, "برای ارسال به سروش‌پلاس، فایل باید دارای کپشن باشد (فقط متن کپشن ارسال می‌شود)."
    return False, ""



def _extract_message_media(message: dict) -> tuple[str, str | None, str, str]:
    """استخراج یکپارچه نوع محتوا، شناسه فایل، نام فایل و متن/کپشن از آبجکت پیام."""
    content_type = "text"
    platform_file_id = None
    original_file_name = ""
    text_content = (message.get("text") or "").strip()

    if "sticker" in message:
        content_type = "sticker"
        platform_file_id = message["sticker"]["file_id"]
        text_content = ""
    elif "animation" in message:
        content_type = "animation"
        platform_file_id = message["animation"]["file_id"]
        original_file_name = message["animation"].get("file_name") or ""
        text_content = message.get("caption", "") or ""
    elif "photo" in message:
        content_type = "photo"
        platform_file_id = message["photo"][-1]["file_id"]
        text_content = message.get("caption", "") or ""
    elif "video" in message:
        content_type = "video"
        platform_file_id = message["video"]["file_id"]
        original_file_name = message["video"].get("file_name") or ""
        text_content = message.get("caption", "") or ""
    elif "voice" in message:
        content_type = "voice"
        platform_file_id = message["voice"]["file_id"]
        original_file_name = message["voice"].get("file_name") or ""
        text_content = message.get("caption", "") or ""
    elif "audio" in message:
        content_type = "audio"
        audio_obj = message["audio"]
        platform_file_id = audio_obj["file_id"]
        original_file_name = audio_obj.get("file_name") or ""
        if not original_file_name and audio_obj.get("title"):
            original_file_name = f"{audio_obj['title']}.mp3"
        text_content = message.get("caption", "") or ""
    elif "document" in message:
        doc_obj = message["document"]
        platform_file_id = doc_obj["file_id"]
        original_file_name = doc_obj.get("file_name") or ""
        doc_mime = (doc_obj.get("mime_type") or "").lower()
        if doc_mime.startswith("audio/") or original_file_name.lower().endswith(
            (".mp3", ".m4a", ".wav", ".flac", ".aac")
        ):
            content_type = "audio"
        else:
            content_type = "document"
        text_content = message.get("caption", "") or ""

    return content_type, platform_file_id, original_file_name, text_content

