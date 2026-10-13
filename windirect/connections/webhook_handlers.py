"""پردازش‌کننده‌های Webhook BoxAPI (کامنت، دایرکت، profile)."""

import logging

from django.db import models
from django.utils import timezone

from .models import InstagramConnection

logger = logging.getLogger(__name__)


# ==================== هندلر get_profile ====================
def handle_get_profile(payload: dict) -> bool:
    """پاسخ get_profile: ذخیره‌ی عکس پروفایل."""
    from .views import _download_and_save_profile_picture

    data = payload.get("data", {})
    account_id = data.get("account_id") or data.get("ig_id")
    profile_pic = (
            data.get("profile_pic_url_hd")
            or data.get("profile_pic_url")
            or data.get("profile_pic")
    )

    logger.warning(
        "🖼️ handle_get_profile | account_id=%s | pic_found=%s",
        account_id, bool(profile_pic),
    )

    if not account_id or not profile_pic:
        logger.warning("⚠️ get_profile: missing account_id or profile_pic | data=%s", data)
        return False

    connection = InstagramConnection.objects.filter(
        instagram_user_id=account_id
    ).first()
    if not connection:
        logger.warning("⚠️ get_profile: connection not found for account_id=%s", account_id)
        return False

    _download_and_save_profile_picture(connection, profile_pic)
    logger.warning("✅ get_profile: profile pic saved for @%s", connection.username)
    return True


# ==================== هندلر کامنت ====================
def handle_comment_event(payload: dict) -> bool:
    """
    پردازش رویداد کامنت جدید (ساختار BoxAPI).
    """
    from windirect.comments.services import process_real_comment

    logger.warning("💬 handle_comment_event | top_keys=%s", list(payload.keys()))

    # ==================== استخراج فیلدها ====================
    account_id = payload.get("account_id")
    data = payload.get("data") or {}

    comment_id = data.get("id")
    media_id = (data.get("media") or {}).get("id")
    text = data.get("text", "")
    username = (data.get("from") or {}).get("username", "")
    customer_id = (data.get("from") or {}).get("id", "")

    logger.warning(
        "📋 comment fields | account_id=%s | comment_id=%s | media_id=%s | "
        "text=%r | username=%s | customer_id=%s",
        account_id, comment_id, media_id, text[:100] if text else "",
        username, customer_id,
    )

    # ==================== اعتبارسنجی ====================
    if not account_id or not comment_id or not media_id or not text:
        logger.warning(
            "⚠️ comment event: missing required fields | account_id=%s | comment_id=%s | media_id=%s",
            account_id, comment_id, media_id,
        )
        return False

    # ==================== چک: کامنت خود پیج نباشه ====================
    if customer_id and str(customer_id) == str(account_id):
        logger.warning(
            "⏭️ comment event: comment is from page itself → skipping | "
            "customer_id=%s == account_id=%s",
            customer_id, account_id,
        )
        return False

    # ==================== پیدا کردن connection ====================
    connection = InstagramConnection.objects.filter(
        instagram_user_id=account_id
    ).first()

    if not connection:
        logger.warning(
            "⚠️ comment event: connection not found for account_id=%s",
            account_id,
        )
        return False

    if connection.status != InstagramConnection.Status.CONNECTED:
        logger.warning(
            "⚠️ comment event: connection not connected | @%s | status=%s",
            connection.username, connection.status,
        )
        return False

    logger.warning(
        "✅ comment event | @%s | comment_id=%s | media_id=%s",
        connection.username, comment_id, media_id,
    )

    # ==================== پردازش ====================
    try:
        process_real_comment(
            connection=connection,
            comment_id=comment_id,
            media_id=media_id,
            text=text,
            username=username,
            customer_id=customer_id,
        )
        return True

    except Exception:
        logger.exception("❌ process_real_comment failed | comment_id=%s", comment_id)
        return False


def handle_follow_status_event(payload: dict) -> bool:
    """پردازش نتیجه‌ی follow_status از BoxAPI."""
    from django.db import models as django_models
    from windirect.comments.models import AutomationExecution
    from windirect.comments.services import _build_direct_payload
    from windirect.connections.boxapi import send_private_reply, send_message

    logger.warning("👤 handle_follow_status_event | top_keys=%s", list(payload.keys()))

    data = payload.get("data") or {}
    request = data.get("request") or {}
    result = data.get("result") or {}

    account_id = request.get("account_id") or payload.get("account_id")
    customer_id = request.get("customer_id") or result.get("customer_id")

    is_following = result.get("is_user_follow_business")
    success = data.get("success")

    logger.warning(
        "📊 follow_status result | account_id=%s | customer_id=%s | "
        "is_following=%s | success=%s",
        account_id, customer_id, is_following, success,
    )

    if not account_id or not customer_id:
        logger.warning("⚠️ follow_status: missing account_id or customer_id")
        return False

    if not success:
        logger.warning(
            "⚠️ follow_status: BoxAPI reported failure | error=%s",
            data.get("error"),
        )
        return False

    # ==================== پیدا کردن execution در انتظار ====================
    execution = (
        AutomationExecution.objects
        .filter(
            status=AutomationExecution.Status.FOLLOW_REQUIRED,
            response_payload__customer_id=customer_id,
            response_payload__account_id=account_id,
        )
        .filter(
            django_models.Q(response_payload__stage="pending_initial")
            | django_models.Q(response_payload__stage="pending_recheck")
        )
        .select_related("automation", "event")
        .order_by("-created_at")
        .first()
    )

    if not execution:
        logger.warning(
            "⚠️ follow_status: no pending execution found | "
            "customer_id=%s | account_id=%s",
            customer_id, account_id,
        )
        return False

    rule = execution.automation
    event = execution.event
    current_stage = execution.response_payload.get("stage", "")

    logger.warning(
        "🎯 Found pending execution | execution_id=%s | rule=%s | comment_id=%s | stage=%s",
        execution.pk, rule.name, event.external_comment_id, current_stage,
    )

    # ==================== تصمیم‌گیری ====================
    if is_following is True:
        # ==================== فالو کرده → پیام اصلی ====================
        logger.warning(
            "✅ User is following → sending main message | rule=%s | customer_id=%s",
            rule.name, customer_id,
        )

        direct_payload = _build_direct_payload(rule, assume_followed=True)
        message_text = direct_payload.get("text", "")

        if not message_text:
            logger.warning("⚠️ Direct reply has no text | rule=%s", rule.name)
            return False

        # ==================== انتخاب متد ارسال ====================
        # ⚠️ مهم: اگه قبلاً یه private_reply برای این کامنت فرستادیم،
        # دیگه نمی‌تونیم private_reply بفرستیم. باید send_message بفرستیم.
        #
        # مرحله‌ها:
        # - pending_initial: هنوز هیچ پیامی نفرستادیم → private_reply مجازه
        # - pending_recheck: قبلاً یه private_reply فرستادیم → باید send_message
        if current_stage == "pending_initial":
            # اولین پیام → private_reply (با comment_id)
            logger.warning(
                "📩 Using private_reply (first message) | comment_id=%s",
                event.external_comment_id,
            )
            success_send = send_private_reply(
                account_id=account_id,
                comment_id=event.external_comment_id,
                message=message_text,
            )
        else:
            # pending_recheck → کاربر دایرکت داره → send_message
            logger.warning(
                "📨 Using send_message (user already has DM) | recipient_id=%s",
                customer_id,
            )
            success_send = send_message(
                account_id=account_id,
                recipient_id=customer_id,
                message=message_text,
            )

        # ==================== آپدیت execution ====================
        execution.status = (
            AutomationExecution.Status.SENT
            if success_send
            else AutomationExecution.Status.FAILED
        )
        execution.response_payload = {
            **execution.response_payload,
            "stage": "following_verified",
            "is_following": True,
            "text": message_text,
            "send_success": success_send,
            "send_method": "private_reply" if current_stage == "pending_initial" else "send_message",
        }
        execution.save(update_fields=["status", "response_payload"])

        logger.warning(
            "📝 execution updated | execution_id=%s | status=%s | sent=%s",
            execution.pk, execution.status, success_send,
        )
        return True

    elif is_following is False:
        # ==================== فالو نکرده ====================

        # ===== اگه مرحله‌ی pending_recheck هست: پیام یادآوری =====
        if current_stage == "pending_recheck":
            logger.warning(
                "⚠️ User still NOT following (after postback) → sending reminder | "
                "rule=%s | customer_id=%s",
                rule.name, customer_id,
            )

            reminder_text = (
                "هنوز پیج ما رو فالو نکردی رفیق! 🙃\n"
                "لطفاً اول فالو کن، بعد دکمه رو بزن."
            )

            reminder_buttons = [
                {
                    "type": "postback",
                    "title": rule.follow_prompt_button or "فالو کردم",
                    "payload": f"CHECK_FOLLOW_{rule.pk}_{event.pk}",
                }
            ]

            # ===== ارسال پیام یادآوری =====
            # چون کاربر الان دایرکت داره، از send_message استفاده می‌کنیم
            success_send = send_message(
                account_id=account_id,
                recipient_id=customer_id,
                message=reminder_text,
                buttons=reminder_buttons,
            )

            # ==================== آپدیت execution ====================
            execution.status = AutomationExecution.Status.FOLLOW_REQUIRED
            execution.response_payload = {
                **execution.response_payload,
                "stage": "pending_recheck",
                "is_following": False,
                "reminder_sent": success_send,
                "reminder_text": reminder_text,
            }
            execution.save(update_fields=["status", "response_payload"])

            logger.warning(
                "📝 execution updated (reminder) | execution_id=%s | status=%s | sent=%s",
                execution.pk, execution.status, success_send,
            )
            return True

        # ===== اگه مرحله‌ی pending_initial هست: پیام «فالو کن» اولیه =====
        logger.warning(
            "⚠️ User is NOT following → sending follow prompt | rule=%s | customer_id=%s",
            rule.name, customer_id,
        )

        follow_text = rule.follow_prompt_text or "لطفاً پیج ما رو فالو کنید."
        follow_button_text = rule.follow_prompt_button or "فالو کردم"

        buttons = [
            {
                "type": "postback",
                "title": follow_button_text,
                "payload": f"CHECK_FOLLOW_{rule.pk}_{event.pk}",
            }
        ]

        success_send = send_private_reply(
            account_id=account_id,
            comment_id=event.external_comment_id,
            message=follow_text,
            buttons=buttons,
        )

        # ==================== آپدیت execution ====================
        execution.status = (
            AutomationExecution.Status.FOLLOW_REQUIRED
            if success_send
            else AutomationExecution.Status.FAILED
        )
        execution.response_payload = {
            **execution.response_payload,
            "stage": "follow_prompt_sent",
            "is_following": False,
            "prompt_text": follow_text,
            "button_text": follow_button_text,
            "button_payload": f"CHECK_FOLLOW_{rule.pk}_{event.pk}",
            "send_success": success_send,
        }
        execution.save(update_fields=["status", "response_payload"])

        logger.warning(
            "📝 execution updated | execution_id=%s | status=%s | sent=%s",
            execution.pk, execution.status, success_send,
        )
        return True

    else:
        # ==================== نتیجه نامشخص ====================
        logger.warning(
            "❓ Follow status unknown | rule=%s | customer_id=%s | result=%s",
            rule.name, customer_id, result,
        )
        execution.status = AutomationExecution.Status.FAILED
        execution.response_payload = {
            **execution.response_payload,
            "stage": "unknown",
            "error": "unknown_follow_status",
            "raw_result": result,
        }
        execution.save(update_fields=["status", "response_payload"])
        return False


def handle_postback_event(payload: dict) -> bool:
    """
    پردازش کلیک کاربر روی دکمه‌ی postback.

    ساختار Webhook:
    {
      "event_id": "...",
      "event_type": "messaging_postbacks",
      "account_id": "...",
      "data": {
        "sender": {"id": "..."},
        "recipient": {"id": "..."},
        "timestamp": ...,
        "postback": {
          "title": "فالو کردم",
          "payload": "CHECK_FOLLOW_1_12"
        }
      }
    }
    """
    from windirect.comments.models import AutomationExecution
    from windirect.connections.boxapi import get_follow_status

    logger.warning("🔘 handle_postback_event | top_keys=%s", list(payload.keys()))

    data = payload.get("data") or {}
    account_id = payload.get("account_id")
    sender = data.get("sender") or {}
    customer_id = sender.get("id")
    postback = data.get("postback") or {}
    postback_payload = postback.get("payload", "")
    postback_title = postback.get("title", "")

    logger.warning(
        "🔘 postback | account_id=%s | customer_id=%s | title=%r | payload=%r",
        account_id, customer_id, postback_title, postback_payload,
    )

    if not account_id or not customer_id or not postback_payload:
        logger.warning("⚠️ postback: missing required fields")
        return False

    # ==================== پارس کردن payload ====================
    # فرمت: CHECK_FOLLOW_{rule_id}_{event_id}
    if not postback_payload.startswith("CHECK_FOLLOW_"):
        logger.warning("⚠️ postback: unknown payload format | payload=%s", postback_payload)
        return False

    try:
        parts = postback_payload.split("_")
        # parts = ["CHECK", "FOLLOW", "{rule_id}", "{event_id}"]
        rule_id = int(parts[2])
        event_id = int(parts[3])
    except (IndexError, ValueError):
        logger.exception("❌ postback: invalid payload format | payload=%s", postback_payload)
        return False

    logger.warning("🔘 Parsed payload | rule_id=%s | event_id=%s", rule_id, event_id)

    # ==================== پیدا کردن execution قبلی ====================
    execution = (
        AutomationExecution.objects
        .filter(
            automation_id=rule_id,
            event_id=event_id,
            response_payload__customer_id=customer_id,
        )
        .select_related("automation", "event")
        .order_by("-created_at")
        .first()
    )

    if not execution:
        logger.warning(
            "⚠️ postback: no execution found | rule_id=%s | event_id=%s | customer_id=%s",
            rule_id, event_id, customer_id,
        )
        return False

    rule = execution.automation
    event = execution.event

    logger.warning(
        "🎯 postback: found execution | execution_id=%s | rule=%s | comment_id=%s",
        execution.pk, rule.name, event.external_comment_id,
    )

    # ==================== آپدیت stage به pending_recheck ====================
    execution.response_payload = {
        **execution.response_payload,
        "stage": "pending_recheck",  # ← مرحله‌ی جدید
        "postback_received_at": timezone.now().isoformat(),
    }
    execution.save(update_fields=["response_payload"])

    # ==================== دوباره چک فالو ====================
    logger.warning(
        "🔄 Re-checking follow status | customer_id=%s | rule=%s",
        customer_id, rule.name,
    )

    follow_request_ok = get_follow_status(
        account_id=account_id,
        customer_id=customer_id,
    )

    if not follow_request_ok:
        logger.error(
            "❌ follow_status request failed (postback) | customer_id=%s",
            customer_id,
        )
        return False

    logger.warning(
        "⏳ Waiting for follow_status webhook (recheck) | execution_id=%s",
        execution.pk,
    )
    return True


def handle_messaging_event(payload: dict) -> bool:
    """
    پردازش رویدادهای messaging عمومی (پیام‌های دایرکت).
    فعلاً فقط لاگ می‌کنیم. بعداً می‌تونیم گسترش بدیم.
    """
    logger.warning("📨 handle_messaging_event | top_keys=%s", list(payload.keys()))
    # TODO: بعداً اگه نیاز بود، پیام‌های دایرکت کاربر رو پردازش کن
    return True


def _normalize(value: str) -> str:
    """نرمال‌سازی رشته برای تطبیق."""
    return str(value or "").lower().replace("_", "").replace("-", "").strip()


def route_webhook(payload: dict) -> bool:
    """تشخیص و هدایت رویدادهای دریافتی از BoxAPI (ساختار واقعی)."""

    event_type = payload.get("event_type", "")
    event_id = payload.get("event_id", "")
    account_id = payload.get("account_id", "")

    logger.warning(
        "🚦 route_webhook | event_type=%s | account_id=%s | event_id=%s",
        event_type, account_id, event_id,
    )

    if not event_type:
        logger.warning(
            "⚠️ route_webhook: no event_type | keys=%s",
            list(payload.keys()),
        )
        return False

    normalized = _normalize(event_type)

    # ==================== اول action های BoxAPI ====================
    # ⚠️ اینا باید قبل از comments چک بشن چون اسمشون شامل comment هست
    if "actionreplycomment" in normalized or "action.reply_comment" in event_type:
        return handle_action_callback(payload, "reply_comment")

    if "actionprivatreply" in normalized or "action.private_reply" in event_type:
        return handle_action_callback(payload, "private_reply")

    if "actionsendmessage" in normalized or "action.send_message" in event_type:
        return handle_action_callback(payload, "send_message")

    if "actionfollowstatus" in normalized or "action.follow_status" in event_type:
        return handle_follow_status_event(payload)

    # ==================== action.list_posts ====================
    if "actionlistposts" in normalized or "action.list_posts" in event_type:
        return handle_list_posts(payload)

    # ==================== messaging (کلیک روی دکمه) ====================
    if "messagingpostback" in normalized or "messaging_postback" in event_type:
        return handle_postback_event(payload)

    if "messaging" in normalized:
        return handle_messaging_event(payload)

    # ==================== کامنت ====================
    if normalized in ("comments", "comment", "livecomments", "livecomment"):
        return handle_comment_event(payload)

    # ==================== profile ====================
    if normalized in ("getprofile", "profile", "get_profile"):
        return handle_get_profile(payload)

    # ==================== list_posts (غیر action) ====================
    if normalized in ("listposts", "posts", "getposts", "media"):
        return handle_list_posts(payload)

    # ==================== fallback ====================
    if "comment" in normalized:
        return handle_comment_event(payload)
    if "profile" in normalized:
        return handle_get_profile(payload)
    if "listpost" in normalized or "getpost" in normalized:
        return handle_list_posts(payload)

    logger.warning("⚠️ route_webhook: no handler for event_type=%s", event_type)
    return False


def handle_action_callback(payload: dict, action: str) -> bool:
    """
    پردازش Webhook های اطلاع‌رسانی از BoxAPI.

    اینا فقط تأیید می‌کنن که یه action انجام شد:
    - action.reply_comment
    - action.private_reply
    - action.send_message
    """
    logger.warning(
        "📬 BoxAPI action callback | action=%s | event_id=%s",
        action, payload.get("event_id"),
    )

    data = payload.get("data") or {}
    result = data.get("result") or {}

    logger.warning(
        "📬 action result | success=%s | result=%s",
        data.get("success"), result,
    )
    # کاری نمی‌کنیم، فقط لاگ
    return True


# ==================== هندلر list_posts ====================
def handle_list_posts(payload: dict) -> bool:
    """پاسخ list_posts: ذخیره‌ی لیست پست‌ها در Cache."""
    from django.core.cache import cache

    # ==================== استخراج فیلدها ====================
    # account_id توی root هست، نه توی data
    account_id = payload.get("account_id") or payload.get("data", {}).get("account_id")

    # پست‌ها توی data.result.data هستن
    data = payload.get("data", {})
    result = data.get("result", {})
    posts = result.get("data", [])  # لیست پست‌ها

    logger.warning(
        "📸 handle_list_posts | account_id=%s | posts_count=%s",
        account_id, len(posts) if isinstance(posts, list) else "N/A",
    )

    if not account_id:
        logger.warning("⚠️ list_posts: no account_id")
        return False

    # ذخیره توی Cache
    cache_key = f"instagram_posts:{account_id}"
    cache.set(cache_key, {
        "status": "ready",
        "posts": posts,
        "fetched_at": timezone.now().isoformat(),
    }, timeout=600)

    logger.warning(
        "✅ list_posts cached | account_id=%s | count=%s",
        account_id, len(posts),
    )
    return True


# ==================== روتر Webhook ====================
HANDLERS = {
    "get_profile": handle_get_profile,
    "getprofile": handle_get_profile,
    "profile": handle_get_profile,
    "comments": handle_comment_event,
    "comment": handle_comment_event,
    "list_posts": handle_list_posts,
    "listposts": handle_list_posts,
    "posts": handle_list_posts,
    "action.follow_status": handle_follow_status_event,
    "messaging_postbacks": handle_postback_event,
    "messaging": handle_messaging_event,
    # ==================== جدید: action callbacks ====================
    "action.reply_comment": lambda p: handle_action_callback(p, "reply_comment"),
    "action.private_reply": lambda p: handle_action_callback(p, "private_reply"),
    "action.send_message": lambda p: handle_action_callback(p, "send_message"),
}
