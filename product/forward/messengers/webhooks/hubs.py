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

from .common import _WINJOB_FORWARD_URL, _WINJOB_PLANS_URL, _bot_send, _extract_message_media


def _handle_hub_membership_event(chat: dict, from_user: dict, is_removed: bool, platform_slug: str):
    """ثبت خودکار یا غیرفعال‌سازی گروه هاب هنگام اضافه یا حذف شدن ربات در گروه."""
    logger.warning(
        "[HUB] membership event: platform=%s chat_id=%s from_id=%s is_removed=%s",
        platform_slug,
        chat.get("id"),
        from_user.get("id"),
        is_removed,
    )
    platform = Platform.objects.filter(slug=platform_slug).first()
    if not platform:
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    group_chat_id = str(chat.get("id") or "")
    if not group_chat_id:
        return JsonResponse({"ok": True, "status": "missing group chat_id"})

    if is_removed:
        updated = BroadcastHub.objects.filter(platform=platform, group_chat_id=group_chat_id).update(is_active=False)
        return JsonResponse({"ok": True, "status": "hub deactivated" if updated else "hub not found"})

    adapter = get_adapter(platform_slug)
    from_chat_id = from_user.get("id")
    bot_user = BotUser.objects.filter(platform=platform, chat_id=str(from_chat_id)).select_related("user").first()

    if not bot_user:
        if adapter and group_chat_id:
            try:
                _bot_send(
                    adapter,
                    group_chat_id,
                    "سلام! 👋 برای ثبت این گروه به عنوان **هاب ارسال تیمی**، ابتدا باید حسابتان در پنل وین‌فوروارد متصل باشد.\n"
                    "پس از اتصال حساب، کافی است دستور `/bindhub` را در همین گروه ارسال کنید.",
                    reply_markup={
                        "inline_keyboard": [[{"text": "🌐 ورود به پنل وین فوروارد", "url": _WINJOB_FORWARD_URL}]]
                    },
                    platform_slug=platform_slug,
                )
            except Exception as exc:
                logger.warning(f"Failed to send hub onboarding message: {exc}")
        return JsonResponse({"ok": True, "status": "hub user not linked"})

    group_title = chat.get("title") or f"گروه {group_chat_id}"
    hub, created = BroadcastHub.objects.update_or_create(
        platform=platform,
        group_chat_id=group_chat_id,
        defaults={
            "user": bot_user.user,
            "title": group_title,
            "is_active": True,
        },
    )

    hub_edit_url = f"https://winjob.ir/forward/hubs/{hub.pk}/edit/"
    if adapter and from_chat_id:
        try:
            _bot_send(
                adapter,
                from_chat_id,
                f"🚀 گروه **«{hub.title}»** با موفقیت به عنوان **هاب تیمی** ثبت شد!\n\n"
                "الان از لینک زیر وارد تنظیمات این هاب شوید و پکیج ارسال (یا کانال‌های مقصد) آن را انتخاب کنید:",
                reply_markup={
                    "inline_keyboard": [[{"text": "⚙️ تنظیم پروفایل و کانال‌های هاب", "url": hub_edit_url}]]
                },
                platform_slug=platform_slug,
            )
        except Exception as exc:
            logger.warning(f"Failed to send hub DM to owner: {exc}")

    return JsonResponse({
        "ok": True,
        "status": "hub created" if created else "hub updated",
        "hub_id": hub.pk,
    })



def _handle_hub_group_message(message: dict, platform_slug: str):
    """پردازش خودکار پیام‌های اعضای گروه هاب، انتشار به کانال‌ها، ری‌اکشن ✅ و گزارش در پی‌وی فرستنده."""
    from product.forward.broadcast.models import BroadcastMessage
    from product.forward.subscriptions.access import user_has_platform_access

    chat_id = str(message.get("chat", {}).get("id") or "")
    from_user = message.get("from") or {}
    if from_user.get("is_bot"):
        return JsonResponse({"ok": True, "status": "bot message ignored"})

    hub = (
        BroadcastHub.objects.filter(platform__slug=platform_slug, group_chat_id=chat_id, is_active=True)
        .select_related("user", "preset")
        .first()
    )
    if not hub:
        return JsonResponse({"ok": True, "status": "not an active hub"})

    content_type, platform_file_id, original_file_name, text_content = _extract_message_media(message)
    if not text_content and not platform_file_id:
        return JsonResponse({"ok": True, "status": "empty group message ignored"})

    # بررسی شرط هشتگ #ارسال در صورت تنظیم شدن روی هاب
    if hub.publish_mode == BroadcastHub.PublishMode.HASHTAG:
        if "#ارسال" not in text_content:
            return JsonResponse({"ok": True, "status": "skipped without #ارسال"})
        text_content = re.sub(r"\s*#ارسال\s*", " ", text_content).strip()
        if not text_content and not platform_file_id:
            return JsonResponse({"ok": True, "status": "empty after hashtag removal"})

    adapter = get_adapter(platform_slug)
    sender_chat_id = str(from_user.get("id") or "")

    # بررسی موجودی توکن مالک هاب و وجود کانال‌های مقصد تنظیم‌شده
    if not user_has_platform_access(hub.user, platform_slug):
        owner_bu = BotUser.objects.filter(user=hub.user, platform__slug=platform_slug).first()
        if adapter and owner_bu:
            try:
                _bot_send(
                    adapter,
                    owner_bu.chat_id,
                    f"🪙 پیامی در هاب «{hub.title}» ارسال شد اما موجودی توکن شما کافی نیست.",
                    reply_markup={"inline_keyboard": [[{"text": "🪙 شارژ توکن", "url": _WINJOB_PLANS_URL}]]},
                    platform_slug=platform_slug,
                )
            except Exception:
                pass
        return JsonResponse({"ok": True, "status": "hub owner no subscription"})

    target_channels = hub.get_target_channels()
    if not target_channels:
        owner_bu = BotUser.objects.filter(user=hub.user, platform__slug=platform_slug).first()
        if adapter and owner_bu:
            try:
                _bot_send(
                    adapter,
                    owner_bu.chat_id,
                    f"⚠️ پیامی در هاب «{hub.title}» فرستاده شد اما هنوز پکیج یا کانال مقصدی برای این هاب انتخاب نکرده‌اید:",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "⚙️ تنظیم کانال‌های هاب", "url": f"https://winjob.ir/forward/hubs/{hub.pk}/edit/"}]
                        ]
                    },
                    platform_slug=platform_slug,
                )
            except Exception:
                pass
        return JsonResponse({"ok": True, "status": "hub has no target channels"})

    hub_file_size = 0
    for media_key in ("video", "document", "audio", "voice", "animation", "sticker"):
        if media_key in message and isinstance(message[media_key], dict):
            hub_file_size = int(message[media_key].get("file_size") or 0)
            break
    if not hub_file_size and "photo" in message and isinstance(message["photo"], list) and message["photo"]:
        hub_file_size = int(message["photo"][-1].get("file_size") or 0)

    from product.forward.subscriptions.services import get_max_file_size_bytes
    if hub_file_size > get_max_file_size_bytes():
        return JsonResponse({"ok": True, "status": "hub file exceeds 20mb"})

    sender_parts = [
        (from_user.get("first_name") or "").strip(),
        (from_user.get("last_name") or "").strip(),
    ]
    sender_full_name = " ".join(p for p in sender_parts if p).strip()
    sender_username = (from_user.get("username") or "").strip().lstrip("@")
    if sender_full_name and sender_username:
        sender_display = f"{sender_full_name} (@{sender_username})"
    elif sender_full_name:
        sender_display = sender_full_name
    elif sender_username:
        sender_display = f"@{sender_username}"
    else:
        sender_display = f"کاربر {sender_chat_id}" if sender_chat_id else "عضو گروه"

    owner_bu = BotUser.objects.filter(user=hub.user, platform__slug=platform_slug).first()
    owner_chat_id = str(owner_bu.chat_id) if (owner_bu and owner_bu.chat_id) else None
    fallback_chat_id = owner_chat_id if (owner_chat_id and owner_chat_id != sender_chat_id) else None

    file_ids_payload = {
        "source_platform": platform_slug,
        "hub_id": hub.pk,
        "hub_title": hub.title,
        "hub_sender_name": sender_display,
        "file_size": hub_file_size,
    }
    if platform_file_id:
        file_ids_payload[platform_slug] = platform_file_id
        if original_file_name:
            file_ids_payload[f"{platform_slug}_file_name"] = original_file_name

    msg = BroadcastMessage.objects.create(
        user=hub.user,
        content_type=content_type,
        text=text_content,
        platform_file_ids=file_ids_payload,
    )
    job = BroadcastJob.objects.create(
        message=msg,
        status=BroadcastJob.Status.PENDING,
        total_targets=len(target_channels),
    )
    BroadcastTarget.objects.bulk_create([
        BroadcastTarget(job=job, channel=ch) for ch in target_channels
    ])

    enqueue_dispatch_job(
        job.pk,
        progress_chat_id=sender_chat_id or owner_chat_id,
        fallback_progress_chat_id=fallback_chat_id,
        reaction_chat_id=chat_id,
        reaction_message_id=message.get("message_id"),
        reaction_platform=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "hub job queued", "job_id": job.pk})

