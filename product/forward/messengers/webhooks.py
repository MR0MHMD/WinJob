"""دریافت و پردازش آپدیت‌های Webhook ربات بله."""

import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from core.models import Platform
from product.forward.broadcast.models import BroadcastChannel, BroadcastJob, BroadcastTarget
from product.forward.broadcast.services.channel_sync import finalize_verification
from product.forward.broadcast.services.dispatcher import dispatch_job, enqueue_dispatch_job
from product.forward.messengers.adapters.base import MessengerError
from product.forward.messengers.adapters.registry import get_adapter
from product.forward.messengers.models import BotUser, ConnectToken

logger = logging.getLogger(__name__)


@csrf_exempt
def bale_webhook(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    # لاگ کامل payload دریافتی
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Bale webhook received: {json.dumps(data, ensure_ascii=False)}")

    if "message" in data:
        return _handle_message(data["message"])

    if "callback_query" in data:
        return _handle_callback_query(data["callback_query"])

    return JsonResponse({"ok": True, "status": "ignored"})


def _handle_message(message):
    """پردازش پیام‌های دریافتی — شامل دستورات /start, /status, /channels و رویدادهای کانال."""

    # ۱. بررسی اضافه شدن ربات به کانال
    if "new_chat_members" in message:
        return _handle_bot_added_to_chat(message)

    # ۲. بررسی حذف شدن ربات از کانال
    if "left_chat_member" in message:
        return _handle_bot_removed_from_chat(message)

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return JsonResponse({"ok": True, "status": "no chat_id"})

    # ۳. بررسی دستورات (قبل از پیام‌های خصوصی — رفع باگ)
    if text.startswith("/"):
        parts = text.split(" ")
        command = parts[0]

        adapter = get_adapter("bale")
        if adapter is None:
            logger.error("BaleAdapter is not registered")
            return JsonResponse({"ok": False, "error": "Adapter missing"}, status=500)

        # --- /start ---
        if command == "/start":
            if len(parts) > 1 and parts[1].startswith("verify_"):
                token = parts[1].replace("verify_", "")
                result = finalize_verification(token, "bale", str(chat_id))
                if result["ok"]:
                    adapter.send_text(chat_id, f"✅ کانال «{result['channel'].title}» با موفقیت به وین فوروارد متصل شد.")
                else:
                    error_map = {
                        "invalid_or_used_token": "❌ لینک نامعتبر است یا قبلاً استفاده شده.",
                        "expired_token": "❌ لینک منقضی شده است. لطفاً از سایت لینک جدید بگیرید.",
                        "bot_not_admin": "❌ ربات در کانال ادمین نیست. لطفاً ربات را ادمین کنید.",
                        "api_error": "❌ خطا در ارتباط با بله. لطفاً بعداً تلاش کنید.",
                    }
                    adapter.send_text(chat_id, error_map.get(result.get("error"), "❌ خطای نامشخص."))
                return JsonResponse({"ok": True, "status": "verify processed"})

            elif len(parts) > 1 and parts[1].startswith("connect_"):
                token = parts[1].replace("connect_", "")
                from_user = message.get("from", {})
                return _handle_connect_user(token, chat_id, from_user)

            else:
                adapter.send_text(chat_id, "سلام! به ربات وین فوروارد خوش آمدید.\nبرای اتصال کانال، از سایت اقدام کنید.")
                return JsonResponse({"ok": True, "status": "welcome sent"})

        # --- /status ---
        elif command == "/status":
            return _handle_status_command(chat_id)

        # --- /channels ---
        elif command == "/channels":
            return _handle_channels_command(chat_id)

        return JsonResponse({"ok": True, "status": "unknown command"})

    # ۴. پیام غیردستوری در چت خصوصی → ساخت پیش‌نویس
    chat_type = message.get("chat", {}).get("type")
    if chat_type == "private":
        return _handle_private_message(message)

    return JsonResponse({"ok": True, "status": "ignored"})


def _handle_bot_added_to_chat(message):
    """پردازش رویداد اضافه شدن ربات به کانال (new_chat_members)."""
    chat = message.get("chat", {})
    from_user = message.get("from", {})

    chat_id = chat.get("id")
    chat_type = chat.get("type")
    from_chat_id = from_user.get("id")

    if chat_type != "channel":
        return JsonResponse({"ok": True, "status": "not a channel"})

    platform = Platform.objects.filter(slug="bale").first()
    if not platform:
        logger.error("Platform 'bale' not found")
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    chat_id_str = str(chat_id)
    adapter = get_adapter("bale")

    # پیدا کردن کاربر سایت از روی from.id
    bot_user = BotUser.objects.filter(platform=platform, chat_id=str(from_chat_id)).select_related("user").first()

    # ۲-الف: کاربر ناشناخته — ربات رو Start نکرده
    if not bot_user:
        if adapter and from_chat_id:
            try:
                adapter.send_text(
                    from_chat_id,
                    f"سلام! کانال «{chat.get('title', '')}» شناسایی شد.\n"
                    "برای مدیریت و ارسال پیام از طریق سایت وین‌فوروارد، ابتدا از لینک زیر حساب بله خود را به سایت متصل کنید، "
                    "سپس ربات را از کانال حذف و مجدداً اضافه کنید:\n"
                    "https://winjob.ir/forward/bale/connect/",
                )
            except Exception as exc:
                logger.warning(f"Failed to send onboarding DM: {exc}")
        return JsonResponse({"ok": True, "status": "user not linked, dm sent"})

    # ۲-ب: کاربر شناخته شده — ساخت/بروزرسانی کانال
    channel, created = BroadcastChannel.objects.update_or_create(
        user=bot_user.user,
        platform=platform,
        chat_id=chat_id_str,
        defaults={
            "title": chat.get("title", "") or chat.get("username", "") or "کانال بدون عنوان",
            "username": chat.get("username", "") or "",
            "bot_is_admin": False,  # در ابتدا ادمین نیست، بعدا چک میشه
            "bot_admin_checked_at": timezone.now(),
            "is_active": True,
        },
    )

    # بررسی نهایی با API
    if adapter:
        try:
            is_admin = adapter.check_bot_is_admin(chat_id_str)
            channel.bot_is_admin = is_admin
            channel.bot_admin_checked_at = timezone.now()
            channel.save(update_fields=["bot_is_admin", "bot_admin_checked_at"])

            if not is_admin:
                adapter.send_text(
                    from_chat_id,
                    f"ربات به کانال «{channel.title}» اضافه شد، اما ادمین نیست. لطفاً ربات را ادمین کنید تا بتواند پیام ارسال کند."
                )
        except Exception as exc:
            logger.warning(f"Failed to verify admin status: {exc}")

    return JsonResponse({
        "ok": True,
        "status": "channel created" if created else "channel updated",
        "channel_id": channel.pk,
    })


def _handle_bot_removed_from_chat(message):
    """پردازش حذف شدن ربات از کانال (left_chat_member)."""
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if chat.get("type") != "channel":
        return JsonResponse({"ok": True, "status": "not a channel"})

    platform = Platform.objects.filter(slug="bale").first()
    if not platform:
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    chat_id_str = str(chat_id)

    # غیرفعال کردن کانال در دیتابیس
    updated = BroadcastChannel.objects.filter(
        platform=platform, chat_id=chat_id_str
    ).update(
        is_active=False, bot_is_admin=False, bot_admin_checked_at=timezone.now()
    )

    return JsonResponse({"ok": True, "status": "channel deactivated" if updated else "channel not found"})


def _handle_connect_user(token, chat_id, from_user):
    """اتصال کاربر سایت به ربات با استفاده از توکن تولیدشده در سایت."""
    from product.forward.messengers.models import ConnectToken, BotUser
    token_obj = ConnectToken.objects.filter(token=token, used_at__isnull=True).select_related("user",
                                                                                              "platform").first()

    adapter = get_adapter("bale")
    if not adapter:
        return JsonResponse({"ok": False, "error": "Adapter missing"}, status=500)

    if not token_obj or not token_obj.is_valid():
        adapter.send_text(chat_id, "❌ لینک اتصال نامعتبر است یا منقضی شده. لطفاً از سایت لینک جدید بگیرید.")
        return JsonResponse({"ok": True, "status": "invalid token"})

    # ثبت یا آپدیت BotUser
    bot_user, created = BotUser.objects.get_or_create(
        user=token_obj.user,
        platform=token_obj.platform,
        defaults={"chat_id": str(chat_id), "is_verified": True, "username": from_user.get("username", "")}
    )
    if not created:
        bot_user.chat_id = str(chat_id)
        bot_user.is_verified = True
        bot_user.save(update_fields=["chat_id", "is_verified"])

    # باطل کردن توکن
    token_obj.used_at = timezone.now()
    token_obj.save(update_fields=["used_at"])

    adapter.send_text(
        chat_id,
        "✅ حساب شما با موفقیت به وین‌فوروارد متصل شد.\nحالا می‌تونید ربات رو به کانالتون اضافه کنید تا کانالتون شناسایی بشه."
    )
    return JsonResponse({"ok": True, "status": "connected"})


def _handle_status_command(chat_id):
    """پردازش دستور /status برای نمایش وضعیت اتصال کاربر."""
    adapter = get_adapter("bale")
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()

    if not bot_user:
        adapter.send_text(
            chat_id,
            "❌ حساب بله شما به سایت متصل نیست.\n"
            "برای اتصال، وارد سایت وین‌فوروارد شوید و از بخش اتصال کانال، لینک دریافت کنید."
        )
        return JsonResponse({"ok": True, "status": "not connected"})

    msg = (
        f"👤 **وضعیت حساب شما:**\n\n"
        f"📱 شماره تماس: {bot_user.user.phone_number}\n"
        f"🔗 وضعیت اتصال: ✅ متصل و تایید شده\n"
        f"📅 تاریخ اتصال: {bot_user.linked_at.strftime('%Y/%m/%d') if bot_user.linked_at else 'نامشخص'}\n\n"
        f"برای دیدن لیست کانال‌ها دستور /channels را بزنید."
    )
    adapter.send_text(chat_id, msg)
    return JsonResponse({"ok": True, "status": "status sent"})


def _handle_channels_command(chat_id):
    """پردازش دستور /channels برای نمایش لیست کانال‌ها با دکمه‌های شیشه‌ای."""
    adapter = get_adapter("bale")
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()

    if not bot_user:
        adapter.send_text(chat_id, "❌ ابتدا حساب خود را با دستور /start به سایت متصل کنید.")
        return JsonResponse({"ok": True, "status": "not connected"})

    # گرفتن کانال‌های فعال کاربر
    channels = BroadcastChannel.objects.filter(user=bot_user.user, is_active=True)

    if not channels.exists():
        adapter.send_text(chat_id,
                          "📋 شما هنوز هیچ کانال فعالی ندارید.\nبرای افزودن کانال، ربات را به عنوان ادمین به کانال بله خود اضافه کنید.")
        return JsonResponse({"ok": True, "status": "no channels"})

    # ساخت کیبورد شیشه‌ای
    inline_keyboard = []
    for ch in channels:
        status_icon = "✅" if ch.bot_is_admin else "⚠️"
        inline_keyboard.append([
            {"text": f"{status_icon} {ch.title}", "callback_data": f"ch_{ch.pk}"}
        ])

    reply_markup = {"inline_keyboard": inline_keyboard}
    adapter.send_text(chat_id, "📋 لطفاً یک کانال را برای مدیریت انتخاب کنید:", reply_markup=reply_markup)
    return JsonResponse({"ok": True, "status": "channels sent"})


def _build_draft_keyboard(job):
    """ساخت کیبورد شیشه‌ای برای انتخاب کانال‌ها همراه با نمایش قفل اشتراک برای پلتفرم‌های غیرفعال."""
    from product.forward.subscriptions.access import get_active_platform_slugs

    active_slugs = get_active_platform_slugs(job.message.user)
    channels = BroadcastChannel.objects.filter(
        user=job.message.user, is_active=True, bot_is_admin=True
    ).select_related("platform")
    selected_channel_ids = set(job.targets.values_list("channel_id", flat=True))
    inline_keyboard = []
    for ch in channels:
        if ch.platform.slug not in active_slugs:
            inline_keyboard.append([
                {"text": f"🔒 {ch.title} ({ch.platform.name} - نیاز به اشتراک)", "callback_data": f"locked_{ch.platform.slug}"}
            ])
        else:
            is_selected = ch.pk in selected_channel_ids
            icon = "✅" if is_selected else "⬜"
            inline_keyboard.append([{"text": f"{icon} {ch.title}", "callback_data": f"sel_{job.pk}_{ch.pk}"}])
    inline_keyboard.append([{"text": "🚀 تایید و ارسال", "callback_data": f"send_{job.pk}"}])
    return {"inline_keyboard": inline_keyboard}


def _handle_callback_query(callback):
    """پردازش کلیک کاربر روی دکمه‌های شیشه‌ای."""
    adapter = get_adapter("bale")
    data = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    message_id = callback.get("message", {}).get("message_id")

    if not chat_id:
        return JsonResponse({"ok": True, "status": "no chat"})

    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()
    if not bot_user:
        adapter.send_text(chat_id, "❌ دسترسی غیرمجاز.")
        return JsonResponse({"ok": True, "status": "unauthorized"})

    # ۰. کلیک روی کانال نیازمند اشتراک
    if data.startswith("locked_"):
        from product.forward.subscriptions.access import platform_label
        slug = data.replace("locked_", "")
        adapter.send_text(
            chat_id,
            f"🔒 اشتراک فعال برای پلتفرم «{platform_label(slug)}» ندارید.\n"
            "برای فعال‌سازی، به بخش اشتراک وین‌فوروارد در سایت مراجعه کنید.",
        )
        return JsonResponse({"ok": True, "status": "locked platform"})

    # ۱. انتخاب/لغو انتخاب کانال
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
                BroadcastTarget.objects.create(job=job, channel_id=channel_id)

            if message_id:
                reply_markup = _build_draft_keyboard(job)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error in sel_ callback: {e}")

        return JsonResponse({"ok": True, "status": "selection toggled"})

    # ۲. تایید و ارسال
    elif data.startswith("send_"):
        try:
            job_id = data.replace("send_", "")
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user,
                                              status=BroadcastJob.Status.DRAFT).first()
            if not job:
                adapter.send_text(chat_id, "❌ پیش‌نویس یافت نشد یا قبلاً ارسال شده است.")
                return JsonResponse({"ok": True, "status": "job not found"})

            if not job.targets.exists():
                adapter.send_text(chat_id, "❌ لطفاً حداقل یک کانال را انتخاب کنید.")
                return JsonResponse({"ok": True, "status": "no targets"})

            job.status = BroadcastJob.Status.PENDING
            job.total_targets = job.targets.count()
            job.save(update_fields=["status", "total_targets"])

            # 🔑 اجرای غیرمسدودکننده در پس‌زمینه تا وب‌هوک بله تایم‌اوت نخورد
            enqueue_dispatch_job(job.pk, progress_chat_id=str(chat_id))

        except Exception as e:
            logger.exception(f"Error in send_ callback: {e}")
            adapter.send_text(chat_id, "❌ خطایی در ارسال رخ داد.")

        return JsonResponse({"ok": True, "status": "send processed"})

    # ۳. داشبورد کانال‌ها
    elif data.startswith("ch_") or data == "back_list" or data.startswith("refresh_") or data.startswith("delete_"):
        return _handle_dashboard_callback(callback, adapter, chat_id, bot_user)

    return JsonResponse({"ok": True, "status": "ignored"})


def _handle_dashboard_callback(callback, adapter, chat_id, bot_user):
    """مدیریت دکمه‌های داشبورد کانال‌ها (تفکیک شده برای خوانایی)."""
    # (همون کدهایی که توی مرحله ۷-۳ برای ch_, refresh_, delete_, back_list نوشتیم رو اینجا بذار)
    data = callback.get("data", "")

    if data.startswith("ch_"):
        channel_id = data.replace("ch_", "")
        channel = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).first()
        if not channel:
            adapter.send_text(chat_id, "❌ کانال یافت نشد.")
            return JsonResponse({"ok": True})
        admin_status = "✅ ربات ادمین است" if channel.bot_is_admin else "⚠️ ربات ادمین نیست"
        text = f"📢 **{channel.title}**\n\nوضعیت: {admin_status}"
        inline_keyboard = [
            [{"text": "🔄 بروزرسانی وضعیت", "callback_data": f"refresh_{channel.pk}"}],
            [{"text": "🗑 حذف کانال", "callback_data": f"delete_{channel.pk}"}],
            [{"text": "🔙 بازگشت به لیست", "callback_data": "back_list"}]
        ]
        adapter.send_text(chat_id, text, reply_markup={"inline_keyboard": inline_keyboard})
    elif data.startswith("refresh_"):
        channel_id = data.replace("refresh_", "")
        channel = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).first()
        if channel and adapter:
            try:
                is_admin = adapter.check_bot_is_admin(channel.chat_id)
                channel.bot_is_admin = is_admin
                channel.save(update_fields=["bot_is_admin"])
                adapter.send_text(chat_id,
                                  f"✅ وضعیت بروزرسانی شد.\n{'✅ ربات ادمین است' if is_admin else '⚠️ ربات ادمین نیست'}")
            except Exception as e:
                adapter.send_text(chat_id, f"❌ خطا: {e}")
    elif data.startswith("delete_"):
        channel_id = data.replace("delete_", "")
        channel = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).first()
        if channel:
            channel.is_active = False
            channel.save(update_fields=["is_active"])
            adapter.send_text(chat_id, "✅ کانال غیرفعال شد.")
    elif data == "back_list":
        return _handle_channels_command(chat_id)

    return JsonResponse({"ok": True})


def _handle_private_message(message):
    """دریافت فایل یا متن از کاربر در چت خصوصی و ساخت پیش‌نویس برای ارسال."""
    from product.forward.broadcast.models import BroadcastMessage, BroadcastJob
    chat_id = message.get("chat", {}).get("id")
    chat_str = str(chat_id)
    from_user = message.get("from", {})
    text_content = message.get("text", "").strip()

    # --- ۳. منطق موجود بله ---
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=chat_str).select_related("user").first()
    if not bot_user:
        adapter = get_adapter("bale")
        adapter.send_text(chat_id, "❌ ابتدا حساب خود را با لینک اتصال سایت، به ربات متصل کنید.")
        return JsonResponse({"ok": True, "status": "not connected"})

    if text_content.startswith("/"):
        return JsonResponse({"ok": True, "status": "command ignored in private"})

    # استخراج نوع محتوا و file_id (ترتیب مهم است!)
    content_type = "text"
    platform_file_id = None
    original_file_name = ""

    # ۱. اول استیکر (چون ممکن است document هم داشته باشد)
    if "sticker" in message:
        content_type = "sticker"
        platform_file_id = message["sticker"]["file_id"]
        text_content = ""

    # ۲. بعد انیمیشن/گیف (چون ممکن است document هم داشته باشد)
    elif "animation" in message:
        content_type = "animation"
        platform_file_id = message["animation"]["file_id"]
        original_file_name = message["animation"].get("file_name") or ""
        text_content = message.get("caption", "")

    # ۳. سپس بقیه انواع
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
        return JsonResponse({"ok": True, "status": "empty message"})

    file_ids_payload = {}
    if platform_file_id:
        file_ids_payload["bale"] = platform_file_id
        if original_file_name:
            file_ids_payload["bale_file_name"] = original_file_name

    try:
        # ساخت پیام و جاب در حالت پیش‌نویس
        msg = BroadcastMessage.objects.create(
            user=bot_user.user,
            content_type=content_type,
            text=text_content,
            platform_file_ids=file_ids_payload,
        )
        job = BroadcastJob.objects.create(message=msg, status=BroadcastJob.Status.DRAFT)
    except Exception as exc:
        logger.exception(f"Failed to create draft message/job: {exc}")
        adapter = get_adapter("bale")
        adapter.send_text(chat_id, f"❌ خطا در ساخت پیش‌نویس: {exc}")
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)

    from product.forward.subscriptions.access import user_has_platform_access
    if not user_has_platform_access(bot_user.user, "bale"):
        adapter = get_adapter("bale")
        adapter.send_text(
            chat_id,
            "🔒 اشتراک وین‌فوروارد شما فعال نیست یا منقضی شده است.\n"
            "لطفاً ابتدا از سایت اشتراک خود را فعال یا تمدید کنید.",
        )
        return JsonResponse({"ok": True, "status": "subscription required"})

    # دریافت لیست کانال‌های کاربر
    channels = BroadcastChannel.objects.filter(user=bot_user.user, is_active=True, bot_is_admin=True)
    if not channels.exists():
        adapter = get_adapter("bale")
        adapter.send_text(chat_id, "⚠️ شما هیچ کانال فعالی با دسترسی ادمین ندارید.")
        return JsonResponse({"ok": True, "status": "no channels"})

    # ساخت کیبورد شیشه‌ای با نمایش وضعیت اشتراک هر پلتفرم
    reply_markup = _build_draft_keyboard(job)
    inline_keyboard = reply_markup["inline_keyboard"]

    adapter = get_adapter("bale")
    try:
        adapter.send_text(
            chat_id,
            "📝 پیش‌نویس پیام شما آماده شد.\nلطفاً کانال‌های مقصد را انتخاب کنید و سپس روی «تایید و ارسال» بزنید:",
            reply_markup={"inline_keyboard": inline_keyboard}
        )
    except Exception as exc:
        logger.exception(f"Failed to send draft keyboard: {exc}")

    return JsonResponse({"ok": True, "status": "draft created"})
