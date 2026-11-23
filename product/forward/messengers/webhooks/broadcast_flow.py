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

from .commands import (
    _handle_channels_command, _handle_help_command, _handle_presets_command,
    _handle_start_send_command, _handle_status_command, _send_guest_welcome,
)
from .common import (
    _CANCEL_SEND_KEYBOARD, _USER_KEYBOARD, _WINJOB_FORWARD_URL, _WINJOB_PLANS_URL,
    _bot_send, _is_soroush_locked_for_message, _set_awaiting_broadcast,
)


def _build_draft_keyboard(job, manual_mode: bool = False):
    """ساخت کیبورد شیشه‌ای هوشمند برای انتخاب پکیج‌ها، انتخاب دستی کانال‌ها، انتخاب همه و لغو پیش‌نویس."""
    from product.forward.subscriptions.access import get_active_platform_slugs

    active_slugs = get_active_platform_slugs(job.message.user)
    soroush_locked, _ = _is_soroush_locked_for_message(job.message)
    channels = list(
        BroadcastChannel.objects.filter(
            user=job.message.user, is_active=True, bot_is_admin=True
        ).select_related("platform")
    )
    eligible_channel_ids = {
        ch.pk
        for ch in channels
        if ch.platform.slug in active_slugs and not (soroush_locked and ch.platform.slug == "soroush")
    }
    selected_channel_ids = set(job.targets.values_list("channel_id", flat=True))

    presets = list(
        ChannelPreset.objects.filter(user=job.message.user, is_active=True)
        .prefetch_related("channels__platform")
        .order_by("-created_at")
    )

    inline_keyboard = []

    if presets and not manual_mode:
        for preset in presets:
            preset_eligible_ids = {
                ch.pk
                for ch in preset.channels.all()
                if ch.is_active and ch.bot_is_admin and ch.platform.slug in active_slugs
            }
            if not preset_eligible_ids:
                inline_keyboard.append([
                    {"text": f"🔒 📦 {preset.name} (نیاز به توکن یا کانال فعال)", "callback_data": f"preset_{job.pk}_{preset.pk}"}
                ])
            else:
                is_selected = preset_eligible_ids.issubset(selected_channel_ids)
                icon = "✅" if is_selected else "⬜"
                inline_keyboard.append([
                    {"text": f"{icon} 📦 {preset.name} ({len(preset_eligible_ids)} کانال)", "callback_data": f"preset_{job.pk}_{preset.pk}"}
                ])

        if eligible_channel_ids:
            all_selected = eligible_channel_ids.issubset(selected_channel_ids)
            all_icon = "✅" if all_selected else "⬜"
            inline_keyboard.append([
                {"text": f"{all_icon} 🌟 انتخاب همه ({len(eligible_channel_ids)} کانال)", "callback_data": f"selall_{job.pk}"}
            ])

        inline_keyboard.append([
            {"text": "📋 انتخاب دستی کانال‌ها", "callback_data": f"manual_{job.pk}"}
        ])
    else:
        if presets:
            inline_keyboard.append([
                {"text": "🔙 بازگشت به پکیج‌های ارسال", "callback_data": f"presetsview_{job.pk}"}
            ])

        if eligible_channel_ids:
            all_selected = eligible_channel_ids.issubset(selected_channel_ids)
            all_icon = "✅" if all_selected else "⬜"
            selall_cb = f"selallm_{job.pk}" if presets else f"selall_{job.pk}"
            inline_keyboard.append([
                {"text": f"{all_icon} 🌟 انتخاب همه ({len(eligible_channel_ids)} کانال)", "callback_data": selall_cb}
            ])

        for ch in channels:
            if ch.platform.slug not in active_slugs:
                inline_keyboard.append([
                    {"text": f"🔒 {ch.title} ({ch.platform.name} - نیاز به توکن)", "callback_data": f"locked_{ch.platform.slug}"}
                ])
            elif soroush_locked and ch.platform.slug == "soroush":
                inline_keyboard.append([
                    {"text": f"🔒 {ch.title} (سروش‌پلاس - فقط متن/کپشن)", "callback_data": "soroush_locked"}
                ])
            else:
                is_selected = ch.pk in selected_channel_ids
                icon = "✅" if is_selected else "⬜"
                inline_keyboard.append([{"text": f"{icon} {ch.title} ({ch.platform.name})", "callback_data": f"sel_{job.pk}_{ch.pk}"}])

    inline_keyboard.append([
        {"text": "🚀 تایید و ارسال", "callback_data": f"send_{job.pk}"},
        {"text": "❌ لغو پیش‌نویس", "callback_data": f"cancel_{job.pk}"},
    ])
    return {"inline_keyboard": inline_keyboard}



def _handle_callback_query(callback, platform_slug: str = "bale"):
    """پردازش کلیک کاربر روی دکمه‌های شیشه‌ای."""
    adapter = get_adapter(platform_slug)
    data = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    message_id = callback.get("message", {}).get("message_id")

    if not chat_id:
        return JsonResponse({"ok": True, "status": "no chat"})

    bot_user = BotUser.objects.filter(
        platform__slug=platform_slug, chat_id=str(chat_id)
    ).select_related("user").first()
    if not bot_user:
        _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "unauthorized"})

    # ۰. کلیک روی کانال نیازمند شارژ توکن
    if data.startswith("locked_"):
        _bot_send(
            adapter,
            chat_id,
            "🪙 موجودی توکن شما برای ارسال پیام کافی نیست (حداقل ۲ توکن لازم است).\n"
            f"می‌توانید از [بخش کیف توکن وین‌فوروارد]({_WINJOB_PLANS_URL}) هدیه ۳۵۰ توکنی رایگان بگیرید یا بسته توکن تهیه کنید.",
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "insufficient tokens"})

    # ۰-ب. کلیک روی کانال قفل‌شده سروش‌پلاس (فایل بدون کپشن / استیکر / گیف)
    if data == "soroush_locked":
        _bot_send(
            adapter,
            chat_id,
            "🔒 در سروش‌پلاس فقط پیام متنی یا کپشن فایل‌ها ارسال می‌شود (۲ توکن).\n"
            "چون این پیام فایل بدون کپشن (یا استیکر/گیف) است، کانال‌های سروش‌پلاس قفل شده‌اند.",
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "soroush locked"})

    # ۱-الف. انتخاب/لغو انتخاب یک پکیج ارسال
    if data.startswith("preset_"):
        try:
            from product.forward.subscriptions.access import get_active_platform_slugs

            _, job_id, preset_id = data.split("_")
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            preset = ChannelPreset.objects.filter(pk=preset_id, user=bot_user.user, is_active=True).first()
            if not job or not preset:
                return JsonResponse({"ok": True, "status": "job or preset not found"})

            active_slugs = get_active_platform_slugs(bot_user.user)
            eligible_ids = [
                ch.pk
                for ch in preset.channels.filter(is_active=True, bot_is_admin=True).select_related("platform")
                if ch.platform.slug in active_slugs
            ]
            if not eligible_ids:
                _bot_send(
                    adapter,
                    chat_id,
                    f"⚠️ پکیج «{preset.name}» هیچ کانال فعالی ندارد یا موجودی توکن شما کافی نیست.",
                    platform_slug=platform_slug,
                )
                return JsonResponse({"ok": True, "status": "preset has no eligible channels"})

            selected_ids = set(job.targets.values_list("channel_id", flat=True))
            if set(eligible_ids).issubset(selected_ids):
                BroadcastTarget.objects.filter(job=job, channel_id__in=eligible_ids).delete()
            else:
                for cid in eligible_ids:
                    if cid not in selected_ids:
                        BroadcastTarget.objects.get_or_create(job=job, channel_id=cid)

            if message_id:
                reply_markup = _build_draft_keyboard(job)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error in preset_ callback: {e}")

        return JsonResponse({"ok": True, "status": "preset toggled"})

    # ۱-ب. جابجایی به حالت انتخاب دستی کانال‌ها یا بازگشت به پکیج‌ها
    if data.startswith("manual_") or data.startswith("presetsview_"):
        try:
            is_manual = data.startswith("manual_")
            job_id = data.split("_", 1)[1]
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            if job and message_id:
                reply_markup = _build_draft_keyboard(job, manual_mode=is_manual)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error switching manual/preset view: {e}")
        return JsonResponse({"ok": True, "status": "view switched"})

    # ۱-ج. انتخاب یا لغو انتخاب همه کانال‌های مجاز
    if data.startswith("selall_") or data.startswith("selallm_"):
        try:
            from product.forward.subscriptions.access import get_active_platform_slugs

            is_manual = data.startswith("selallm_")
            job_id = data.split("_", 1)[1]
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            if not job:
                return JsonResponse({"ok": True, "status": "job not found"})

            active_slugs = get_active_platform_slugs(bot_user.user)
            soroush_locked, _ = _is_soroush_locked_for_message(job.message)
            eligible_ids = [
                ch.pk
                for ch in BroadcastChannel.objects.filter(
                    user=bot_user.user, is_active=True, bot_is_admin=True
                ).select_related("platform")
                if ch.platform.slug in active_slugs and not (soroush_locked and ch.platform.slug == "soroush")
            ]
            selected_ids = set(job.targets.values_list("channel_id", flat=True))
            if eligible_ids and set(eligible_ids).issubset(selected_ids):
                job.targets.all().delete()
            else:
                for cid in eligible_ids:
                    if cid not in selected_ids:
                        BroadcastTarget.objects.get_or_create(job=job, channel_id=cid)

            if message_id:
                reply_markup = _build_draft_keyboard(job, manual_mode=is_manual)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error in selall_ callback: {e}")

        return JsonResponse({"ok": True, "status": "select all toggled"})

    # ۱-د. انتخاب/لغو انتخاب کانال تکی (حفظ حالت دستی)
    if data.startswith("sel_"):
        try:
            _, job_id, channel_id = data.split("_")
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            if not job:
                return JsonResponse({"ok": True, "status": "job not found"})

            target = BroadcastTarget.objects.filter(job=job, channel_id=channel_id).first()
            if target:
                target.delete()
            else:
                ch_obj = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).select_related("platform").first()
                soroush_locked, lock_reason = _is_soroush_locked_for_message(job.message)
                if ch_obj and ch_obj.platform.slug == "soroush" and soroush_locked:
                    _bot_send(adapter, chat_id, f"🔒 {lock_reason}", platform_slug=platform_slug)
                    return JsonResponse({"ok": True, "status": "soroush locked"})
                BroadcastTarget.objects.create(job=job, channel_id=channel_id)

            if message_id:
                reply_markup = _build_draft_keyboard(job, manual_mode=True)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error in sel_ callback: {e}")

        return JsonResponse({"ok": True, "status": "selection toggled"})

    # ۱-ه. لغو پیش‌نویس و پاک کردن پیام انتخاب
    if data.startswith("cancel_"):
        try:
            job_id = data.replace("cancel_", "")
            job = BroadcastJob.objects.filter(
                pk=job_id, message__user=bot_user.user, status=BroadcastJob.Status.DRAFT
            ).first()
            if job:
                msg_obj = job.message
                job.delete()
                if msg_obj and not msg_obj.jobs.exists():
                    msg_obj.delete()
            if message_id:
                adapter.delete_message(chat_id, message_id)
            still_awaiting = bool((bot_user.session_data or {}).get("awaiting_broadcast"))
            _bot_send(
                adapter,
                chat_id,
                "❌ پیش‌نویس ارسال لغو و پاک شد.",
                reply_markup=_CANCEL_SEND_KEYBOARD if still_awaiting else _USER_KEYBOARD,
                platform_slug=platform_slug,
            )
        except Exception as e:
            logger.error(f"Error in cancel_ callback: {e}")
        return JsonResponse({"ok": True, "status": "draft cancelled"})

    # ۲. تایید و ارسال نهایی (حذف فوری پیام پیش‌نویس و اجرای پس‌زمینه)
    if data.startswith("send_"):
        try:
            job_id = data.replace("send_", "")
            job = BroadcastJob.objects.filter(
                pk=job_id, message__user=bot_user.user, status=BroadcastJob.Status.DRAFT
            ).first()
            if not job:
                _bot_send(
                    adapter,
                    chat_id,
                    "❌ پیش‌نویس یافت نشد یا قبلاً ارسال شده است.",
                    reply_markup=_USER_KEYBOARD,
                    platform_slug=platform_slug,
                )
                return JsonResponse({"ok": True, "status": "job not found"})

            if not job.targets.exists():
                _bot_send(
                    adapter,
                    chat_id,
                    "⚠️ لطفاً حداقل یک پکیج یا کانال را انتخاب کنید.",
                    platform_slug=platform_slug,
                )
                return JsonResponse({"ok": True, "status": "no targets"})

            job.status = BroadcastJob.Status.PENDING
            job.total_targets = job.targets.count()
            job.save(update_fields=["status", "total_targets"])

            # حذف فوری پیام پیش‌نویس/انتخاب کانال تا صفحه تمیز بماند و کلیک تکراری ممکن نباشد
            if message_id:
                adapter.delete_message(chat_id, message_id)

            enqueue_dispatch_job(job.pk, progress_chat_id=str(chat_id))
        except Exception as e:
            logger.exception(f"Error in send_ callback: {e}")
            _bot_send(
                adapter,
                chat_id,
                "❌ خطایی در شروع ارسال رخ داد.",
                reply_markup=_USER_KEYBOARD,
                platform_slug=platform_slug,
            )

        return JsonResponse({"ok": True, "status": "send processed"})

    # ۳. مدیریت کانال‌ها و پکیج‌ها
    if (
        data.startswith("ch_")
        or data == "back_list"
        or data.startswith("refresh_")
        or data.startswith("viewpreset_")
        or data == "back_presets"
    ):
        return _handle_dashboard_callback(callback, adapter, chat_id, bot_user, platform_slug=platform_slug)

    return JsonResponse({"ok": True, "status": "ignored"})



def _handle_dashboard_callback(callback, adapter, chat_id, bot_user, platform_slug: str = "bale"):
    """مدیریت مشاهده جزئیات کانال‌ها و پکیج‌ها در ربات (حذف و ویرایش از طریق پنل وب)."""
    from product.forward.subscriptions.access import user_has_platform_access

    data = callback.get("data", "")

    if data.startswith("ch_"):
        channel_id = data.replace("ch_", "")
        channel = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).select_related("platform").first()
        if not channel:
            _bot_send(adapter, chat_id, "❌ کانال یافت نشد.", platform_slug=platform_slug)
            return JsonResponse({"ok": True})

        admin_status = "✅ ربات/اکانت متصل است" if channel.bot_is_admin else "⚠️ دسترسی ارسال تایید نشده"
        has_sub = user_has_platform_access(bot_user.user, channel.platform.slug)
        tok_status = "✅ آماده ارسال با توکن" if has_sub else "🪙 نیاز به شارژ توکن"
        username_line = f"🔗 آیدی: @{channel.username}\n" if channel.username else ""

        text = (
            f"📢 **{channel.title}**\n\n"
            f"📱 پلتفرم: **{channel.platform.name}**\n"
            f"{username_line}"
            f"🆔 شناسه: `{channel.chat_id}`\n"
            f"🛡️ وضعیت اتصال: {admin_status}\n"
            f"🪙 وضعیت توکن: {tok_status}\n\n"
            "برای حذف یا ویرایش این کانال از پنل وب استفاده کنید:"
        )
        web_channel_url = f"https://winjob.ir/forward/{channel.platform.slug}/channels/"
        inline_keyboard = []
        if channel.platform.slug in ("bale", "telegram"):
            inline_keyboard.append([{"text": "🔄 بروزرسانی وضعیت ادمین", "callback_data": f"refresh_{channel.pk}"}])
        inline_keyboard.append([{"text": "⚙️ حذف یا مدیریت در پنل وب", "url": web_channel_url}])
        inline_keyboard.append([{"text": "🔙 بازگشت به لیست کانال‌ها", "callback_data": "back_list"}])

        _bot_send(adapter, chat_id, text, reply_markup={"inline_keyboard": inline_keyboard}, platform_slug=platform_slug)
        return JsonResponse({"ok": True})

    if data.startswith("refresh_"):
        channel_id = data.replace("refresh_", "")
        channel = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).select_related("platform").first()
        if channel and channel.platform.slug in ("bale", "telegram"):
            ch_adapter = get_adapter(channel.platform.slug)
            if ch_adapter:
                try:
                    is_admin = ch_adapter.check_bot_is_admin(channel.chat_id)
                    channel.bot_is_admin = is_admin
                    channel.save(update_fields=["bot_is_admin"])
                    sync_channel_avatar(channel, adapter=ch_adapter)
                    _bot_send(
                        adapter,
                        chat_id,
                        f"✅ وضعیت «{channel.title}» بروزرسانی شد:\n{'✅ ربات ادمین است' if is_admin else '⚠️ ربات ادمین نیست'}",
                        platform_slug=platform_slug,
                    )
                except Exception as e:
                    _bot_send(adapter, chat_id, f"❌ خطا در بروزرسانی: {e}", platform_slug=platform_slug)
        return JsonResponse({"ok": True})

    if data == "back_list":
        return _handle_channels_command(chat_id, platform_slug=platform_slug)

    if data.startswith("viewpreset_"):
        preset_id = data.replace("viewpreset_", "")
        preset = (
            ChannelPreset.objects.filter(pk=preset_id, user=bot_user.user, is_active=True)
            .prefetch_related("channels__platform")
            .first()
        )
        if not preset:
            _bot_send(adapter, chat_id, "❌ پکیج یافت نشد.", platform_slug=platform_slug)
            return JsonResponse({"ok": True})

        ch_lines = [
            f"  • {ch.title} ({ch.platform.name})"
            for ch in preset.channels.filter(is_active=True)
        ]
        channels_block = "\n".join(ch_lines) if ch_lines else "  (بدون کانال)"
        text = (
            f"📦 **جزئیات پکیج «{preset.name}»**\n\n"
            f"📢 **کانال‌های عضو ({len(ch_lines)}):**\n{channels_block}\n\n"
            "برای ویرایش یا حذف این پکیج از پنل وب اقدام کنید:"
        )
        edit_url = f"https://winjob.ir/forward/presets/{preset.pk}/edit/"
        _bot_send(
            adapter,
            chat_id,
            text,
            reply_markup={
                "inline_keyboard": [
                    [{"text": "✏️ ویرایش یا حذف در پنل وب", "url": edit_url}],
                    [{"text": "🔙 بازگشت به لیست پکیج‌ها", "callback_data": "back_presets"}],
                ]
            },
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True})

    if data == "back_presets":
        return _handle_presets_command(chat_id, platform_slug=platform_slug)

    return JsonResponse({"ok": True})



def _handle_private_message(message, platform_slug: str = "bale"):
    """پردازش دکمه‌های کیبورد ثابت و ساخت پیش‌نویس در حالت مرحله‌ای ارسال پیام."""
    from product.forward.broadcast.models import BroadcastMessage

    chat_id = message.get("chat", {}).get("id")
    chat_str = str(chat_id)
    text_content = (message.get("text") or "").strip()
    adapter = get_adapter(platform_slug)

    bot_user = BotUser.objects.filter(
        platform__slug=platform_slug, chat_id=chat_str
    ).select_related("user").first()
    if not bot_user:
        _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "not connected"})

    if text_content.startswith("/"):
        return JsonResponse({"ok": True, "status": "command ignored in private"})

    # ۱. پردازش دکمه‌های کیبورد ثابت پایین ربات
    if text_content == "📢 کانال‌های من":
        _set_awaiting_broadcast(bot_user, False)
        return _handle_channels_command(chat_id, platform_slug=platform_slug)

    if text_content == "📦 پکیج‌های ارسال":
        _set_awaiting_broadcast(bot_user, False)
        return _handle_presets_command(chat_id, platform_slug=platform_slug)

    if text_content in ("👤 حساب و اشتراک", "🪙 حساب و توکن"):
        _set_awaiting_broadcast(bot_user, False)
        return _handle_status_command(chat_id, platform_slug=platform_slug)

    if text_content == "📤 ارسال پیام":
        return _handle_start_send_command(chat_id, platform_slug=platform_slug)

    if text_content == "🔙 بازگشت به منوی اصلی":
        _set_awaiting_broadcast(bot_user, False)
        _bot_send(adapter, chat_id, "به منوی اصلی برگشتید 👇", reply_markup=_USER_KEYBOARD, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "send cancelled"})

    if text_content == "❓ راهنما و پشتیبانی":
        _set_awaiting_broadcast(bot_user, False)
        return _handle_help_command(chat_id, platform_slug=platform_slug)

    if text_content == "🌐 پنل وب":
        _set_awaiting_broadcast(bot_user, False)
        _bot_send(
            adapter,
            chat_id,
            f"🌐 برای مدیریت کامل کانال‌ها، پکیج‌ها و گزارش ارسال‌ها روی [ورود به پنل وین فوروارد]({_WINJOB_FORWARD_URL}) بزنید.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🌐 باز کردن پنل وین فوروارد", "url": _WINJOB_FORWARD_URL}]
                ]
            },
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "web panel sent"})

    # ۲. بررسی حالت مرحله‌ای (کاربر باید اول دکمه «📤 ارسال پیام» را زده باشد)
    is_awaiting = bool((bot_user.session_data or {}).get("awaiting_broadcast"))
    if not is_awaiting:
        _bot_send(
            adapter,
            chat_id,
            "برای ارسال پیام یا فایل به کانال‌ها، لطفاً اول دکمه **«📤 ارسال پیام»** را از منوی پایین بزنید 👇",
            reply_markup=_USER_KEYBOARD,
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "not awaiting broadcast"})

    # ۳. استخراج نوع محتوا و file_id
    content_type = "text"
    platform_file_id = None
    original_file_name = ""

    if "sticker" in message:
        content_type = "sticker"
        platform_file_id = message["sticker"]["file_id"]
        text_content = ""
    elif "animation" in message:
        content_type = "animation"
        platform_file_id = message["animation"]["file_id"]
        original_file_name = message["animation"].get("file_name") or ""
        text_content = message.get("caption", "")
    elif "photo" in message:
        content_type = "photo"
        platform_file_id = message["photo"][-1]["file_id"]
        text_content = message.get("caption", "")
    elif "video" in message:
        content_type = "video"
        platform_file_id = message["video"]["file_id"]
        original_file_name = message["video"].get("file_name") or ""
        text_content = message.get("caption", "")
    elif "voice" in message:
        content_type = "voice"
        platform_file_id = message["voice"]["file_id"]
        original_file_name = message["voice"].get("file_name") or ""
        text_content = message.get("caption", "")
    elif "audio" in message:
        content_type = "audio"
        audio_obj = message["audio"]
        platform_file_id = audio_obj["file_id"]
        original_file_name = audio_obj.get("file_name") or ""
        if not original_file_name and audio_obj.get("title"):
            original_file_name = f"{audio_obj['title']}.mp3"
        text_content = message.get("caption", "")
    elif "document" in message:
        doc_obj = message["document"]
        platform_file_id = doc_obj["file_id"]
        original_file_name = doc_obj.get("file_name") or ""
        doc_mime = (doc_obj.get("mime_type") or "").lower()
        if doc_mime.startswith("audio/") or original_file_name.lower().endswith((".mp3", ".m4a", ".wav", ".flac", ".aac")):
            content_type = "audio"
        else:
            content_type = "document"
        text_content = message.get("caption", "")

    if not text_content and not platform_file_id:
        _bot_send(adapter, chat_id, "⚠️ محتوای پیام قابل پردازش نبود.", reply_markup=_CANCEL_SEND_KEYBOARD, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "empty message"})

    incoming_size = 0
    for media_key in ("video", "document", "audio", "voice", "animation", "sticker"):
        if media_key in message and isinstance(message[media_key], dict):
            incoming_size = int(message[media_key].get("file_size") or 0)
            break
    if not incoming_size and "photo" in message and isinstance(message["photo"], list) and message["photo"]:
        incoming_size = int(message["photo"][-1].get("file_size") or 0)

    from product.forward.subscriptions.services import calculate_delivery_token_cost, get_max_file_size_bytes
    max_bytes = get_max_file_size_bytes()
    if incoming_size > max_bytes:
        _bot_send(
            adapter,
            chat_id,
            f"⚠️ حجم این فایل بیشتر از سقف مجاز (**{max_bytes // (1024 * 1024)} مگابایت**) است و امکان انتقال آن وجود ندارد.",
            reply_markup=_CANCEL_SEND_KEYBOARD,
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "file too large"})

    file_ids_payload = {"source_platform": platform_slug, "file_size": incoming_size}
    if platform_file_id:
        file_ids_payload[platform_slug] = platform_file_id
        if original_file_name:
            file_ids_payload[f"{platform_slug}_file_name"] = original_file_name

    try:
        msg = BroadcastMessage.objects.create(
            user=bot_user.user,
            content_type=content_type,
            text=text_content,
            platform_file_ids=file_ids_payload,
        )
        job = BroadcastJob.objects.create(message=msg, status=BroadcastJob.Status.DRAFT)
    except Exception as exc:
        logger.exception(f"Failed to create draft message/job: {exc}")
        _bot_send(adapter, chat_id, f"❌ خطا در ساخت پیش‌نویس: {exc}", reply_markup=_USER_KEYBOARD, platform_slug=platform_slug)
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)

    from product.forward.subscriptions.access import get_user_token_balance
    unit_cost = calculate_delivery_token_cost(
        content_type=content_type,
        has_caption=bool((text_content or "").strip()),
        file_size_bytes=incoming_size,
        is_hub=False,
    )
    user_tokens = get_user_token_balance(bot_user.user)
    if user_tokens < unit_cost:
        _bot_send(
            adapter,
            chat_id,
            f"🪙 موجودی توکن شما کافی نیست! (موجودی: **{user_tokens:,}** | نیاز برای هر کانال: **{unit_cost} توکن**)\n"
            "برای دریافت ۳۵۰ توکن رایگان یا خرید بسته توکن وارد سایت شوید:",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🪙 شارژ توکن / دریافت هدیه رایگان", "url": _WINJOB_PLANS_URL}],
                ]
            },
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "insufficient tokens"})

    has_channels = BroadcastChannel.objects.filter(
        user=bot_user.user, is_active=True, bot_is_admin=True
    ).exists()
    if not has_channels:
        _bot_send(
            adapter,
            chat_id,
            "⚠️ هنوز هیچ کانالی ثبت نکرده‌اید که ربات در آن ادمین باشد.\n"
            "ابتدا ربات را در کانال خود ادمین کنید یا از پنل وب کانال‌های ایتا و روبیکا را اضافه نمایید.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🌐 مدیریت کانال‌ها در سایت", "url": _WINJOB_FORWARD_URL}],
                ]
            },
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "no channels"})

    reply_markup = _build_draft_keyboard(job)
    _bot_send(
        adapter,
        chat_id,
        f"📝 **پیش‌نویس آماده ارسال است!**\n🪙 هزینه هر کانال: **{unit_cost} توکن** | موجودی شما: **{user_tokens:,} توکن**\nپکیج یا کانال‌های مقصد را انتخاب کنید و سپس «🚀 تایید و ارسال» را بزنید:",
        reply_markup=reply_markup,
        platform_slug=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "draft created", "job_id": job.pk})

