"""دریافت و پردازش آپدیت‌های Webhook ربات بله."""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from product.forward.broadcast.services.channel_sync import finalize_verification
from product.forward.messengers.adapters.registry import get_adapter

logger = logging.getLogger(__name__)


@csrf_exempt
def bale_webhook(request):
    """
    دریافت آپدیت‌های ربات بله.
    این ویو باید به عنوان URL وبهوک در API بله ثبت شود.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("Webhook payload is not valid JSON")
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    message = data.get("message")
    if not message:
        return JsonResponse({"ok": True, "status": "ignored, no message"})

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return JsonResponse({"ok": True, "status": "ignored, no chat_id"})

    # فقط دستورات /start رو پردازش می‌کنیم
    if text.startswith("/start"):
        parts = text.split(" ")
        adapter = get_adapter("bale")

        if adapter is None:
            logger.error("BaleAdapter is not registered")
            return JsonResponse({"ok": False, "error": "Adapter missing"}, status=500)

        # حالت اول: /start verify_<token>
        if len(parts) > 1 and parts[1].startswith("verify_"):
            token = parts[1].replace("verify_", "")

            # ۱. صدا زدن منطق تأیید
            result = finalize_verification(token, "bale", str(chat_id))

            # ۲. پاسخ به کاربر
            if result["ok"]:
                adapter.send_text(
                    chat_id,
                    f"✅ کانال «{result['channel'].title}» با موفقیت به وین فوروارد متصل شد."
                )
            else:
                error_map = {
                    "invalid_or_used_token": "❌ لینک نامعتبر است یا قبلاً استفاده شده.",
                    "expired_token": "❌ لینک منقضی شده است. لطفاً از سایت لینک جدید بگیرید.",
                    "bot_not_admin": "❌ ربات در کانال ادمین نیست. لطفاً ربات را ادمین کنید.",
                    "api_error": "❌ خطا در ارتباط با بله. لطفاً بعداً تلاش کنید.",
                }
                err = result.get("error", "api_error")
                adapter.send_text(chat_id, error_map.get(err, "❌ خطای نامشخص."))

        # حالت دوم: /start بدون توکن (خوش‌آمدگویی)
        else:
            adapter.send_text(
                chat_id,
                "سلام! به ربات وین فوروارد خوش آمدید.\nبرای اتصال کانال، از سایت اقدام کنید."
            )

    return JsonResponse({"ok": True})