"""API Endpointهای اختصاصی برای ارتباط n8n با جنگو."""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from product.forward.broadcast.models import BroadcastChannel, BroadcastJob, BroadcastMessage, BroadcastTarget
from product.forward.messengers.models import BotUser, ConnectToken
from core.models import Platform

logger = logging.getLogger(__name__)


@csrf_exempt
def api_connect_user(request):
    """Endpoint برای اتصال کاربر (وقتی n8n دستور /start connect_<token> رو می‌گیره)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        token = data.get("token")
        chat_id = str(data.get("chat_id"))
        username = data.get("username", "")

        # پیدا کردن پلتفرم بر اساس نامی که n8n می‌فرسته (فعلاً bale)
        platform_slug = data.get("platform", "bale")
        platform = Platform.objects.filter(slug=platform_slug).first()

        if not platform:
            return JsonResponse({"ok": False, "error": "Platform not found"}, status=404)

        token_obj = ConnectToken.objects.filter(token=token, used_at__isnull=True).select_related("user").first()

        if not token_obj or not token_obj.is_valid():
            return JsonResponse({"ok": False, "error": "invalid_token", "message": "لینک نامعتبر یا منقضی شده."})

        # ساخت یا آپدیت BotUser
        bot_user, created = BotUser.objects.get_or_create(
            user=token_obj.user,
            platform=platform,
            defaults={"chat_id": chat_id, "is_verified": True, "username": username}
        )
        if not created:
            bot_user.chat_id = chat_id
            bot_user.is_verified = True
            bot_user.username = username
            bot_user.save(update_fields=["chat_id", "is_verified", "username"])

        # باطل کردن توکن
        token_obj.used_at = timezone.now()
        token_obj.save(update_fields=["used_at"])

        return JsonResponse({
            "ok": True,
            "user_id": token_obj.user.id,
            "message": "✅ حساب شما با موفقیت به وین‌فوروارد متصل شد."
        })

    except Exception as e:
        logger.error(f"Error in api_connect_user: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
def api_get_channels(request):
    """Endpoint برای دریافت لیست کانال‌های یک کاربر."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")

        channels = BroadcastChannel.objects.filter(user_id=user_id, is_active=True, bot_is_admin=True)

        channels_data = []
        for ch in channels:
            channels_data.append({
                "id": ch.id,
                "title": ch.title,
                "chat_id": ch.chat_id
            })

        return JsonResponse({"ok": True, "channels": channels_data})

    except Exception as e:
        logger.error(f"Error in api_get_channels: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
def api_create_draft(request):
    """ساخت پیش‌نویس پیام (مشابه _handle_private_message)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        chat_id = str(data.get("chat_id"))
        content_type = data.get("content_type", "text")
        text = data.get("text", "")
        file_id = data.get("file_id")

        bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=chat_id).select_related("user").first()
        if not bot_user:
            return JsonResponse({"ok": False, "error": "not_connected"})

        # ساخت پیام و جاب
        msg = BroadcastMessage.objects.create(
            user=bot_user.user,
            content_type=content_type,
            text=text,
            platform_file_ids={"bale": file_id} if file_id else {}
        )
        job = BroadcastJob.objects.create(message=msg, status=BroadcastJob.Status.DRAFT)

        # ساخت کیبورد
        channels = BroadcastChannel.objects.filter(user=bot_user.user, is_active=True, bot_is_admin=True)
        if not channels.exists():
            return JsonResponse({"ok": False, "error": "no_channels"})

        inline_keyboard = []
        for ch in channels:
            inline_keyboard.append([{"text": f"⬜ {ch.title}", "callback_data": f"sel_{job.pk}_{ch.pk}"}])
        inline_keyboard.append([{"text": "🚀 تایید و ارسال", "callback_data": f"send_{job.pk}"}])

        return JsonResponse({
            "ok": True,
            "job_id": job.pk,
            "keyboard": {"inline_keyboard": inline_keyboard}
        })
    except Exception as e:
        logger.error(f"Error in api_create_draft: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
def api_toggle_target(request):
    """انتخاب/لغو انتخاب کانال (مشابه callback_query sel_)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        job_id = data.get("job_id")
        channel_id = data.get("channel_id")

        job = BroadcastJob.objects.filter(pk=job_id).first()
        if not job:
            return JsonResponse({"ok": False, "error": "job_not_found"})

        target = BroadcastTarget.objects.filter(job=job, channel_id=channel_id).first()
        if target:
            target.delete()
        else:
            BroadcastTarget.objects.create(job=job, channel_id=channel_id)

        # ساخت مجدد کیبورد با وضعیت جدید
        channels = BroadcastChannel.objects.filter(user=job.message.user, is_active=True, bot_is_admin=True)
        selected_channel_ids = set(job.targets.values_list("channel_id", flat=True))
        inline_keyboard = []
        for ch in channels:
            icon = "✅" if ch.pk in selected_channel_ids else "⬜"
            inline_keyboard.append([{"text": f"{icon} {ch.title}", "callback_data": f"sel_{job.pk}_{ch.pk}"}])
        inline_keyboard.append([{"text": "🚀 تایید و ارسال", "callback_data": f"send_{job.pk}"}])

        return JsonResponse({"ok": True, "keyboard": {"inline_keyboard": inline_keyboard}})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
def api_dispatch_job(request):
    """ارسال نهایی پیام (مشابه callback_query send_)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        job_id = data.get("job_id")

        job = BroadcastJob.objects.filter(pk=job_id, status=BroadcastJob.Status.DRAFT).first()
        if not job:
            return JsonResponse({"ok": False, "error": "job_not_found"})

        if not job.targets.exists():
            return JsonResponse({"ok": False, "error": "no_targets"})

        job.status = BroadcastJob.Status.PENDING
        job.total_targets = job.targets.count()
        job.save(update_fields=["status", "total_targets"])

        from product.forward.broadcast.services.dispatcher import enqueue_dispatch_job
        enqueue_dispatch_job(job.pk)

        return JsonResponse({
            "ok": True,
            "status": "queued",
            "job_id": job.pk,
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ... (کدهای قبلی: api_connect_user, api_get_channels, api_create_draft, api_toggle_target, api_dispatch_job)

@csrf_exempt
def api_bot_status(request):
    """برگرداندن وضعیت اتصال کاربر (مشابه /status)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        chat_id = str(data.get("chat_id"))

        bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=chat_id).select_related("user").first()
        if not bot_user:
            return JsonResponse({"ok": True, "text": "❌ حساب بله شما به سایت متصل نیست."})

        text = (
            f"👤 **وضعیت حساب شما:**\n\n"
            f"📱 شماره تماس: {bot_user.user.phone_number}\n"
            f"🔗 وضعیت اتصال: ✅ متصل و تایید شده\n"
            f"📅 تاریخ اتصال: {bot_user.linked_at.strftime('%Y/%m/%d') if bot_user.linked_at else 'نامشخص'}\n\n"
            f"برای دیدن لیست کانال‌ها دستور /channels را بزنید."
        )
        return JsonResponse({"ok": True, "text": text})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
def api_bot_channels_list(request):
    """برگرداندن لیست کانال‌ها به همراه کیبورد (مشابه /channels)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        chat_id = str(data.get("chat_id"))

        bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=chat_id).select_related("user").first()
        if not bot_user:
            return JsonResponse({"ok": True, "text": "❌ ابتدا حساب خود را با دستور /start به سایت متصل کنید."})

        channels = BroadcastChannel.objects.filter(user=bot_user.user, is_active=True)
        if not channels.exists():
            return JsonResponse({"ok": True, "text": "📋 شما هنوز هیچ کانال فعالی ندارید."})

        inline_keyboard = []
        for ch in channels:
            icon = "✅" if ch.bot_is_admin else "⚠️"
            inline_keyboard.append([{"text": f"{icon} {ch.title}", "callback_data": f"ch_{ch.pk}"}])

        return JsonResponse({
            "ok": True,
            "text": "📋 لطفاً یک کانال را برای مدیریت انتخاب کنید:",
            "keyboard": {"inline_keyboard": inline_keyboard}
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
def api_bot_channel_event(request):
    """پردازش رویدادهای کانال (new_chat_members / left_chat_member)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        event_type = data.get("event_type")  # "added" یا "removed"
        chat_id = str(data.get("chat_id"))
        from_chat_id = str(data.get("from_chat_id"))
        title = data.get("title", "")
        username = data.get("username", "")

        platform = Platform.objects.get(slug="bale")

        if event_type == "removed":
            BroadcastChannel.objects.filter(platform=platform, chat_id=chat_id).update(
                is_active=False, bot_is_admin=False, bot_admin_checked_at=timezone.now()
            )
            return JsonResponse({"ok": True, "text": ""})  # نیازی به پیام نیست

        # event_type == "added"
        bot_user = BotUser.objects.filter(platform=platform, chat_id=from_chat_id).select_related("user").first()

        if not bot_user:
            return JsonResponse({
                "ok": False,
                "text": f"سلام! کانال «{title}» شناسایی شد.\nابتدا از لینک زیر حساب بله خود را به سایت متصل کنید، سپس ربات را حذف و مجدداً اضافه کنید:\nhttps://winjob.ir/forward/bale/connect/"
            })

        channel, created = BroadcastChannel.objects.update_or_create(
            user=bot_user.user, platform=platform, chat_id=chat_id,
            defaults={"title": title or username or "کانال بدون عنوان", "username": username, "bot_is_admin": True,
                      "bot_admin_checked_at": timezone.now(), "is_active": True}
        )
        return JsonResponse({"ok": True, "text": f"✅ کانال «{channel.title}» با موفقیت به وین‌فوروارد متصل شد."})

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
