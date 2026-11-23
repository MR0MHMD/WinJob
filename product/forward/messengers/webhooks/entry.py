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

from .broadcast_flow import _handle_callback_query, _handle_private_message
from .commands import (
    _handle_channels_command, _handle_help_command, _handle_presets_command,
    _handle_start_send_command, _handle_status_command, _send_guest_welcome, _send_user_home,
)
from .common import _GUEST_KEYBOARD, _PLATFORM_NAMES_FA, _USER_KEYBOARD, _bot_send, _is_our_bot_user
from .hubs import _handle_hub_group_message, _handle_hub_membership_event
from .membership import (
    _handle_bot_added_to_chat, _handle_bot_removed_from_chat,
    _handle_connect_user, _handle_telegram_my_chat_member,
)


@csrf_exempt
def bale_webhook(request):
    """نقطه ورود Webhook بله برای دریافت پیام‌ها و کلیک دکمه‌های شیشه‌ای."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    logger.info(f"Bale webhook received: {json.dumps(data, ensure_ascii=False)}")

    if "message" in data:
        return _handle_message(data["message"], platform_slug="bale")

    if "callback_query" in data:
        return _handle_callback_query(data["callback_query"], platform_slug="bale")

    return JsonResponse({"ok": True, "status": "ignored"})



@csrf_exempt
def telegram_webhook(request):
    """نقطه ورود Webhook تلگرام برای دریافت پیام‌ها، دکمه‌های شیشه‌ای و وضعیت ادمینی کانال‌ها."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    logger.info(f"Telegram webhook received: {json.dumps(data, ensure_ascii=False)}")

    if "my_chat_member" in data:
        return _handle_telegram_my_chat_member(data["my_chat_member"])

    if "message" in data:
        return _handle_message(data["message"], platform_slug="telegram")

    if "callback_query" in data:
        cb = data["callback_query"]
        adapter = get_adapter("telegram")
        if adapter and cb.get("id"):
            adapter.answer_callback_query(cb["id"])
        return _handle_callback_query(cb, platform_slug="telegram")

    return JsonResponse({"ok": True, "status": "ignored"})



def _handle_message(message, platform_slug: str = "bale"):
    """پردازش پیام‌های دریافتی — شامل دستورات، دکمه‌های کیبورد، رویدادهای کانال و پیش‌نویس."""
    if message.get("group_chat_created") or message.get("supergroup_chat_created"):
        return _handle_hub_membership_event(
            chat=message.get("chat", {}),
            from_user=message.get("from", {}),
            is_removed=False,
            platform_slug=platform_slug,
        )

    if "new_chat_members" in message:
        members = message.get("new_chat_members") or []
        if any(_is_our_bot_user(m, platform_slug) for m in members):
            return _handle_bot_added_to_chat(message, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "non-bot member joined ignored"})

    if "left_chat_member" in message:
        left_member = message.get("left_chat_member") or {}
        if _is_our_bot_user(left_member, platform_slug):
            return _handle_bot_removed_from_chat(message, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "non-bot member left ignored"})

    text = (message.get("text") or "").strip()
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return JsonResponse({"ok": True, "status": "no chat_id"})

    if text.startswith("/"):
        parts = text.split(" ")
        command = parts[0].split("@")[0].lower()

        adapter = get_adapter(platform_slug)
        if adapter is None:
            logger.error(f"Adapter for '{platform_slug}' is not registered")
            return JsonResponse({"ok": False, "error": "Adapter missing"}, status=500)

        if command == "/start":
            if len(parts) > 1 and parts[1].startswith("verify_"):
                token = parts[1].replace("verify_", "")
                result = finalize_verification(token, platform_slug, str(chat_id))
                if result["ok"]:
                    if adapter:
                        sync_channel_avatar(result["channel"], adapter=adapter)
                    _bot_send(
                        adapter,
                        chat_id,
                        f"✅ کانال «{result['channel'].title}» با موفقیت به وین فوروارد متصل شد.",
                        platform_slug=platform_slug,
                    )
                else:
                    error_map = {
                        "invalid_or_used_token": "❌ لینک نامعتبر است یا قبلاً استفاده شده.",
                        "expired_token": "❌ لینک منقضی شده است. لطفاً از سایت لینک جدید بگیرید.",
                        "bot_not_admin": "❌ ربات در کانال ادمین نیست. لطفاً ربات را ادمین کنید.",
                        "api_error": f"❌ خطا در ارتباط با {_PLATFORM_NAMES_FA.get(platform_slug, platform_slug)}. لطفاً بعداً تلاش کنید.",
                    }
                    _bot_send(
                        adapter,
                        chat_id,
                        error_map.get(result.get("error"), "❌ خطای نامشخص."),
                        platform_slug=platform_slug,
                    )
                return JsonResponse({"ok": True, "status": "verify processed"})

            if len(parts) > 1 and parts[1].startswith("connect_"):
                token = parts[1].replace("connect_", "")
                from_user = message.get("from", {})
                return _handle_connect_user(token, chat_id, from_user, platform_slug=platform_slug)

            bot_user = BotUser.objects.filter(
                platform__slug=platform_slug, chat_id=str(chat_id)
            ).select_related("user").first()
            if bot_user:
                _send_user_home(adapter, chat_id, bot_user, platform_slug=platform_slug)
            else:
                _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
            return JsonResponse({"ok": True, "status": "welcome sent"})

        if command == "/status":
            return _handle_status_command(chat_id, platform_slug=platform_slug)

        if command == "/channels":
            return _handle_channels_command(chat_id, platform_slug=platform_slug)

        if command == "/presets":
            return _handle_presets_command(chat_id, platform_slug=platform_slug)

        if command == "/send":
            return _handle_start_send_command(chat_id, platform_slug=platform_slug)

        if command == "/help":
            return _handle_help_command(chat_id, platform_slug=platform_slug)

        if command == "/bindhub":
            chat_obj = message.get("chat", {})
            if chat_obj.get("type") in ("group", "supergroup"):
                return _handle_hub_membership_event(
                    chat=chat_obj,
                    from_user=message.get("from", {}),
                    is_removed=False,
                    platform_slug=platform_slug,
                )

        if message.get("chat", {}).get("type") in ("group", "supergroup"):
            return JsonResponse({"ok": True, "status": "group command ignored"})

        bot_user = BotUser.objects.filter(
            platform__slug=platform_slug, chat_id=str(chat_id)
        ).select_related("user").first()
        _bot_send(
            adapter,
            chat_id,
            "دستور واردشده معتبر نیست؛ از دکمه‌های منوی پایین استفاده کنید 👇",
            reply_markup=_USER_KEYBOARD if bot_user else _GUEST_KEYBOARD,
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "unknown command"})

    chat_type = message.get("chat", {}).get("type")
    if chat_type == "private":
        return _handle_private_message(message, platform_slug=platform_slug)

    if chat_type in ("group", "supergroup"):
        return _handle_hub_group_message(message, platform_slug=platform_slug)

    return JsonResponse({"ok": True, "status": "ignored"})

