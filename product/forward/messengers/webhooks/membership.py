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

from .common import _GUEST_KEYBOARD, _PLATFORM_NAMES_FA, _USER_KEYBOARD, _WINJOB_FORWARD_URL, _bot_send, _set_awaiting_broadcast
from .hubs import _handle_hub_membership_event


def _handle_telegram_my_chat_member(update_obj: dict):
    """مدیریت خودکار اضافه شدن، ادمین شدن یا حذف شدن ربات تلگرام در کانال‌ها (my_chat_member)."""
    chat = update_obj.get("chat") or {}
    from_user = update_obj.get("from") or {}
    new_member = update_obj.get("new_chat_member") or {}

    chat_type = chat.get("type")
    if chat_type in ("group", "supergroup"):
        return _handle_hub_membership_event(
            chat=chat,
            from_user=from_user,
            is_removed=(new_member.get("status", "") in ("left", "kicked")),
            platform_slug="telegram",
        )
    if chat_type != "channel":
        return JsonResponse({"ok": True, "status": "not a channel"})

    platform = Platform.objects.filter(slug="telegram").first()
    if not platform:
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    chat_id_str = str(chat.get("id"))
    new_status = new_member.get("status", "")
    adapter = get_adapter("telegram")

    if new_status in ("left", "kicked"):
        updated = BroadcastChannel.objects.filter(
            platform=platform, chat_id=chat_id_str
        ).update(is_active=False, bot_is_admin=False, bot_admin_checked_at=timezone.now())
        return JsonResponse({"ok": True, "status": "channel deactivated" if updated else "channel not found"})

    from_chat_id = from_user.get("id")
    bot_user = BotUser.objects.filter(platform=platform, chat_id=str(from_chat_id)).select_related("user").first()

    if not bot_user:
        if adapter and from_chat_id:
            try:
                _bot_send(
                    adapter,
                    from_chat_id,
                    f"سلام! کانال «{chat.get('title', '')}» در تلگرام شناسایی شد.\n"
                    "برای مدیریت و ارسال پیام، ابتدا وارد پنل وینجاب شوید و حساب تلگرام خود را متصل کنید، "
                    "سپس از پنل وب کانال را اضافه کنید یا ربات را یک‌بار دوباره در کانال ادمین نمایید:",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "🌐 ورود به پنل وینجاب", "url": _WINJOB_FORWARD_URL}]
                        ]
                    },
                    platform_slug="telegram",
                )
            except Exception as exc:
                logger.warning(f"Failed to send telegram onboarding DM: {exc}")
        return JsonResponse({"ok": True, "status": "user not linked, dm sent"})

    is_admin = new_status in ("administrator", "creator")
    channel, created = BroadcastChannel.objects.update_or_create(
        user=bot_user.user,
        platform=platform,
        chat_id=chat_id_str,
        defaults={
            "title": chat.get("title", "") or chat.get("username", "") or "کانال بدون عنوان",
            "username": chat.get("username", "") or "",
            "bot_is_admin": is_admin,
            "bot_admin_checked_at": timezone.now(),
            "is_active": True,
        },
    )

    if adapter:
        try:
            sync_channel_avatar(channel, adapter=adapter)
            if is_admin:
                _bot_send(
                    adapter,
                    from_chat_id,
                    f"✅ کانال تلگرام «{channel.title}» با دسترسی ادمین ثبت شد و آماده دریافت پیام است!",
                    reply_markup=_USER_KEYBOARD,
                    platform_slug="telegram",
                )
            else:
                _bot_send(
                    adapter,
                    from_chat_id,
                    f"⚠️ ربات در کانال تلگرام «{channel.title}» اضافه شد، اما دسترسی ارسال پیام (ادمین) ندارد.\n"
                    "لطفاً ربات را با دسترسی ارسال پیام ادمین کنید تا در لیست ارسال ظاهر شود.",
                    reply_markup=_USER_KEYBOARD,
                    platform_slug="telegram",
                )
        except Exception as exc:
            logger.warning(f"Failed to handle telegram my_chat_member notify: {exc}")

    return JsonResponse({
        "ok": True,
        "status": "channel created" if created else "channel updated",
        "channel_id": channel.pk,
    })



def _handle_bot_added_to_chat(message, platform_slug: str = "bale"):
    """پردازش رویداد اضافه شدن ربات به کانال یا گروه هاب (new_chat_members)."""
    chat = message.get("chat", {})
    from_user = message.get("from", {})

    chat_id = chat.get("id")
    chat_type = chat.get("type")
    from_chat_id = from_user.get("id")

    if chat_type in ("group", "supergroup"):
        return _handle_hub_membership_event(
            chat=chat,
            from_user=from_user,
            is_removed=False,
            platform_slug=platform_slug,
        )

    if chat_type != "channel":
        return JsonResponse({"ok": True, "status": "not a channel"})

    platform = Platform.objects.filter(slug=platform_slug).first()
    if not platform:
        logger.error(f"Platform '{platform_slug}' not found")
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    chat_id_str = str(chat_id)
    adapter = get_adapter(platform_slug)
    p_name = _PLATFORM_NAMES_FA.get(platform_slug, platform_slug)

    bot_user = BotUser.objects.filter(platform=platform, chat_id=str(from_chat_id)).select_related("user").first()

    if not bot_user:
        if adapter and from_chat_id:
            try:
                _bot_send(
                    adapter,
                    from_chat_id,
                    f"سلام! کانال «{chat.get('title', '')}» شناسایی شد.\n"
                    f"برای مدیریت و ارسال پیام، ابتدا وارد پنل وینجاب شوید و حساب {p_name} خود را متصل کنید، "
                    "سپس ربات را یک‌بار از کانال حذف و دوباره اضافه کنید:",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "🌐 ورود به پنل وینجاب", "url": _WINJOB_FORWARD_URL}]
                        ]
                    },
                    platform_slug=platform_slug,
                )
            except Exception as exc:
                logger.warning(f"Failed to send onboarding DM: {exc}")
        return JsonResponse({"ok": True, "status": "user not linked, dm sent"})

    channel, created = BroadcastChannel.objects.update_or_create(
        user=bot_user.user,
        platform=platform,
        chat_id=chat_id_str,
        defaults={
            "title": chat.get("title", "") or chat.get("username", "") or "کانال بدون عنوان",
            "username": chat.get("username", "") or "",
            "bot_is_admin": False,
            "bot_admin_checked_at": timezone.now(),
            "is_active": True,
        },
    )

    if adapter:
        try:
            is_admin = adapter.check_bot_is_admin(chat_id_str)
            channel.bot_is_admin = is_admin
            channel.bot_admin_checked_at = timezone.now()
            channel.save(update_fields=["bot_is_admin", "bot_admin_checked_at"])
            sync_channel_avatar(channel, adapter=adapter)

            if is_admin:
                _bot_send(
                    adapter,
                    from_chat_id,
                    f"✅ کانال «{channel.title}» با دسترسی ادمین ثبت شد و آماده دریافت پیام است!",
                    reply_markup=_USER_KEYBOARD,
                    platform_slug=platform_slug,
                )
            else:
                _bot_send(
                    adapter,
                    from_chat_id,
                    f"⚠️ ربات به کانال «{channel.title}» اضافه شد، اما هنوز ادمین نیست.\n"
                    "لطفاً ربات را با دسترسی ارسال پیام ادمین کنید تا در لیست ارسال ظاهر شود.",
                    reply_markup=_USER_KEYBOARD,
                    platform_slug=platform_slug,
                )
        except Exception as exc:
            logger.warning(f"Failed to verify admin status: {exc}")

    return JsonResponse({
        "ok": True,
        "status": "channel created" if created else "channel updated",
        "channel_id": channel.pk,
    })



def _handle_bot_removed_from_chat(message, platform_slug: str = "bale"):
    """پردازش حذف شدن ربات از کانال (left_chat_member)."""
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if chat.get("type") in ("group", "supergroup"):
        return _handle_hub_membership_event(
            chat=chat,
            from_user=message.get("from", {}),
            is_removed=True,
            platform_slug=platform_slug,
        )
    if chat.get("type") != "channel":
        return JsonResponse({"ok": True, "status": "not a channel"})

    platform = Platform.objects.filter(slug=platform_slug).first()
    if not platform:
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    chat_id_str = str(chat_id)
    updated = BroadcastChannel.objects.filter(
        platform=platform, chat_id=chat_id_str
    ).update(
        is_active=False, bot_is_admin=False, bot_admin_checked_at=timezone.now()
    )

    return JsonResponse({"ok": True, "status": "channel deactivated" if updated else "channel not found"})



def _handle_connect_user(token, chat_id, from_user, platform_slug: str = "bale"):
    """اتصال کاربر سایت به ربات با استفاده از توکن تولیدشده در سایت."""
    token_obj = ConnectToken.objects.filter(token=token, used_at__isnull=True).select_related("user", "platform").first()

    adapter = get_adapter(platform_slug)
    if not adapter:
        return JsonResponse({"ok": False, "error": "Adapter missing"}, status=500)

    if not token_obj or not token_obj.is_valid():
        _bot_send(
            adapter,
            chat_id,
            "❌ لینک اتصال نامعتبر است یا منقضی شده.\nلطفاً دوباره وارد پنل وینجاب شوید و لینک اتصال جدید بگیرید.",
            reply_markup=_GUEST_KEYBOARD,
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "invalid token"})

    bot_user, created = BotUser.objects.get_or_create(
        user=token_obj.user,
        platform=token_obj.platform,
        defaults={"chat_id": str(chat_id), "is_verified": True, "username": from_user.get("username", "") or ""},
    )
    if not created:
        bot_user.chat_id = str(chat_id)
        bot_user.is_verified = True
        bot_user.save(update_fields=["chat_id", "is_verified"])

    token_obj.used_at = timezone.now()
    token_obj.save(update_fields=["used_at"])

    _set_awaiting_broadcast(bot_user, False)
    p_name = _PLATFORM_NAMES_FA.get(platform_slug, platform_slug)
    _bot_send(
        adapter,
        chat_id,
        f"🎉 حساب {p_name} شما با موفقیت به **وین فوروارد** متصل شد!\n\n"
        f"الان می‌توانید ربات را در کانال‌های {p_name} خود ادمین کنید تا خودکار ثبت شوند، "
        "و یا از پنل وب سایر پیام‌رسان‌ها را متصل کنید.\n\n"
        "همه گزینه‌ها از منوی پایین در دسترس است 👇",
        reply_markup=_USER_KEYBOARD,
        platform_slug=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "connected"})

