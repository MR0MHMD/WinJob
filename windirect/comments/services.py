"""منطق اجرای کامنت هوشمند و ساخت خروجی آزمایشی."""

import random

from django.db import transaction

from windirect.common.matching import _matches_keyword
from windirect.connections.models import InstagramConnection
from windirect.subscriptions.access import require_connection

from .models import (
    Automation,
    AutomationExecution,
    CommentEvent,
    CommentReplyTemplate,
)


def _pick_comment_reply(automation):
    """از بین متن‌های پاسخ کامنت، یکی را به‌صورت تصادفی انتخاب می‌کند."""
    replies = list(automation.comment_replies.values_list("text", flat=True))
    if not replies:
        return ""
    return random.choice(replies)


def _build_comment_payload(automation):
    """خروجی کامنت را برای ثبت در AutomationExecution می‌سازد."""
    return {
        "channel": "comment",
        "kind": "text",
        "text": _pick_comment_reply(automation),
    }


def _build_direct_payload(automation, assume_followed=False):
    """خروجی دایرکت را برای ثبت در AutomationExecution می‌سازد.

    اگر فالو اجباری باشد و مخاطب فالو نکرده باشد، payload «فالو کن» برمی‌گردد.
    """
    # مرحلهٔ فالو اجباری
    if automation.require_follow and not assume_followed:
        return {
            "channel": "direct",
            "kind": "follow_prompt",
            "prompt_text": automation.follow_prompt_text,
            "button_text": automation.follow_prompt_button,
        }

    kind = automation.direct_message_kind or Automation.DirectKind.TEXT

    if kind == Automation.DirectKind.TEXT:
        return {
            "channel": "direct",
            "kind": "text",
            "text": automation.direct_message_text,
        }

    # صوت/تصویر/ویدیو
    # URL فایل رو از direct_message_file بگیر
    file_url = ""
    if automation.media_upload:
        file_url = automation.media_upload.boxapi_url

    return {
        "channel": "direct",
        "kind": kind,
        "url": file_url,
    }


def _matches_automation(automation, media_id, text):
    """بررسی می‌کند یک کامنت با شرط کامنت هوشمند سازگار است یا نه."""
    # ==================== نوع هدف ====================
    if automation.target_type == Automation.TargetType.POST:
        # فقط اگه post_media_id خالی باشه (همه پست‌ها) یا با media_id برابر باشه
        if automation.post_media_id and automation.post_media_id != media_id:
            return False
    # اگه target_type == live، به media_id کاری نداریم

    # ==================== تطبیق کلیدواژه ====================
    return _matches_keyword(automation, text)


@transaction.atomic
def simulate_comment(*, connection, comment_id, media_id, text, assume_followed=False):
    """کامنت نمونه را ثبت و قوانین منطبق را یک‌بار اجرا می‌کند.

    Args:
        connection: حساب اینستاگرام (آزمایشی یا متصل)
        comment_id: شناسهٔ یکتای کامنت (برای جلوگیری از اجرای تکراری)
        media_id: شناسهٔ پست
        text: متن کامنت
        assume_followed: در حالت آزمایش، فرض کن مخاطب فالو کرده است

    Returns:
        tuple: (event, executions)
    """
    # ==================== اعتبارسنجی دسترسی ====================
    require_connection(connection, "smart_comments")

    # ==================== قبول هر دو حالت (آزمایشی و متصل) ====================
    if connection.status not in (
        InstagramConnection.Status.SIMULATED,
        InstagramConnection.Status.CONNECTED,
    ):
        raise ValueError(
            "شبیه‌سازی فقط برای حساب‌های آزمایشی یا متصل مجاز است."
        )

    if not comment_id or not media_id or not text:
        raise ValueError("شناسهٔ کامنت، شناسهٔ پست و متن کامنت لازم هستند.")

    # ==================== ثبت رویداد (یکتایی) ====================
    event, created = CommentEvent.objects.get_or_create(
        connection=connection,
        external_comment_id=comment_id,
        defaults={"media_id": media_id, "text": text},
    )
    if not created:
        return event, []

    # ==================== اجرای قوانین منطبق ====================
    executions = []
    rules = (
        Automation.objects
        .filter(connection=connection, is_active=True)
        .prefetch_related("keywords", "comment_replies")
    )

    for rule in rules:
        if not _matches_automation(rule, media_id, text):
            continue

        # ==================== ساخت payload ====================
        if rule.reply_channel == Automation.ReplyChannel.COMMENT:
            payload = _build_comment_payload(rule)
            status = AutomationExecution.Status.SIMULATED
        else:  # direct
            payload = _build_direct_payload(rule, assume_followed=assume_followed)
            if payload["kind"] == "follow_prompt":
                status = AutomationExecution.Status.FOLLOW_REQUIRED
            else:
                status = AutomationExecution.Status.SIMULATED

        executions.append(
            AutomationExecution.objects.create(
                automation=rule,
                event=event,
                status=status,
                response_payload=payload,
            )
        )

    return event, executions


# ==================== پردازش کامنت واقعی (BoxAPI Webhook) ====================
def process_real_comment(*, connection, comment_id, media_id, text, username="", customer_id=""):
    """
    پردازش کامنت واقعی از Webhook BoxAPI.

    ⚠️ نکته مهم: اگه هیچ rule منطبقی نباشه، CommentEvent ساخته نمیشه.
    این برای جلوگیری از ذخیره‌ی کامنت‌های بی‌ربطه.
    """
    import logging
    from windirect.connections.boxapi import (
        reply_to_comment,
        send_private_reply,
        get_follow_status,
    )

    logger = logging.getLogger(__name__)

    logger.warning(
        "🚀 process_real_comment START | @%s | comment_id=%s | media_id=%s | "
        "text=%r | username=%s | customer_id=%s",
        connection.username, comment_id, media_id,
        text[:100] if text else "", username, customer_id,
    )

    # ==================== اعتبارسنجی ====================
    if not connection.instagram_user_id:
        logger.warning("⚠️ process_real_comment: no instagram_user_id | @%s", connection.username)
        return

    account_id = connection.instagram_user_id

    # ==================== چک: کامنت خود پیج نباشه ====================
    if customer_id and str(customer_id) == str(account_id):
        logger.warning(
            "⏭️ process_real_comment: comment from page itself → skipping | "
            "customer_id=%s == account_id=%s",
            customer_id, account_id,
        )
        return

    # ==================== پیدا کردن قوانین منطبق ====================
    # ⚠️ اول rules رو چک کن، بعد CommentEvent بساز
    rules = (
        Automation.objects
        .filter(connection=connection, is_active=True)
        .prefetch_related("keywords", "comment_replies")
    )

    rules_count = rules.count()
    logger.warning("📋 process_real_comment: checking %s active rules", rules_count)

    if rules_count == 0:
        logger.warning("⚠️ process_real_comment: no active rules for @%s", connection.username)
        return

    # ==================== پیدا کردن ruleهای منطبق ====================
    matched_rules = []
    for rule in rules:
        if _matches_automation(rule, media_id, text):
            matched_rules.append(rule)
            logger.warning(
                "🎯 Rule matched | rule=%s | channel=%s | kind=%s | require_follow=%s",
                rule.name, rule.reply_channel, rule.direct_message_kind, rule.require_follow,
            )
        else:
            logger.warning("⏭️ Rule not matched | rule=%s", rule.name)

    # ==================== اگه هیچ rule مطابقت نکرد → هیچی ذخیره نکن ====================
    if not matched_rules:
        logger.warning(
            "⏭️ No matching rules → skipping entirely (no CommentEvent) | "
            "comment_id=%s | text=%r",
            comment_id, text[:100] if text else "",
        )
        return

    # ==================== حالا CommentEvent رو بساز ====================
    event, created = CommentEvent.objects.get_or_create(
        connection=connection,
        external_comment_id=comment_id,
        defaults={
            "media_id": media_id,
            "text": text,
            "customer_id": customer_id,
            "customer_username": username,
        },
    )

    if not created:
        logger.warning(
            "⏭️ process_real_comment: comment already processed | comment_id=%s",
            comment_id,
        )
        return

    logger.warning("✅ CommentEvent created | id=%s | comment_id=%s", event.pk, comment_id)

    # ==================== اجرای قوانین منطبق ====================
    for rule in matched_rules:
        # ==================== حالت فالو اجباری ====================
        if rule.require_follow:
            logger.warning(
                "👤 Follow required | rule=%s | customer_id=%s",
                rule.name, customer_id,
            )

            if not customer_id:
                logger.error(
                    "❌ require_follow but no customer_id | rule=%s | comment_id=%s",
                    rule.name, comment_id,
                )
                AutomationExecution.objects.create(
                    automation=rule,
                    event=event,
                    status=AutomationExecution.Status.FAILED,
                    response_payload={
                        "channel": "direct",
                        "kind": "follow_check",
                        "error": "no_customer_id",
                    },
                )
                continue

            # ==================== صدا زدن get_follow_status ====================
            follow_request_ok = get_follow_status(
                account_id=account_id,
                customer_id=customer_id,
            )

            if not follow_request_ok:
                logger.error(
                    "❌ get_follow_status request failed | rule=%s | customer_id=%s",
                    rule.name, customer_id,
                )
                AutomationExecution.objects.create(
                    automation=rule,
                    event=event,
                    status=AutomationExecution.Status.FAILED,
                    response_payload={
                        "channel": "direct",
                        "kind": "follow_check",
                        "error": "follow_status_request_failed",
                        "customer_id": customer_id,
                    },
                )
                continue

            # ==================== ثبت execution در حالت انتظار ====================
            execution = AutomationExecution.objects.create(
                automation=rule,
                event=event,
                status=AutomationExecution.Status.FOLLOW_REQUIRED,
                response_payload={
                    "channel": "direct",
                    "kind": "follow_check",
                    "stage": "pending_initial",
                    "account_id": account_id,
                    "customer_id": customer_id,
                    "customer_username": username,
                    "comment_id": comment_id,
                    "media_id": media_id,
                },
            )

            logger.warning(
                "⏳ Waiting for follow_status webhook | execution_id=%s | rule=%s | customer_id=%s",
                execution.pk, rule.name, customer_id,
            )
            continue

        # ==================== حالت عادی (بدون فالو اجباری) ====================
        payload = None
        status = AutomationExecution.Status.FAILED

        try:
            if rule.reply_channel == Automation.ReplyChannel.COMMENT:
                payload = _build_comment_payload(rule)
                message_text = payload.get("text", "")

                if not message_text:
                    logger.warning("⚠️ Comment reply has no text | rule=%s", rule.name)
                    continue

                logger.warning(
                    "💬 Sending comment reply | rule=%s | text=%r",
                    rule.name, message_text[:80],
                )
                success = reply_to_comment(
                    account_id=account_id,
                    comment_id=comment_id,
                    message=message_text,
                )
                status = (
                    AutomationExecution.Status.SENT
                    if success
                    else AutomationExecution.Status.FAILED
                )

            else:  # direct (بدون فالو اجباری)
                payload = _build_direct_payload(rule)
                kind = payload.get("kind", "")

                if kind == "follow_prompt":
                    logger.warning(
                        "⚠️ Unexpected follow_prompt while require_follow=False | rule=%s",
                        rule.name,
                    )
                    continue

                message_text = payload.get("text", "")
                if not message_text:
                    logger.warning("⚠️ Direct reply has no text | rule=%s", rule.name)
                    continue

                logger.warning(
                    "📩 Sending private reply | rule=%s | text=%r",
                    rule.name, message_text[:80],
                )
                success = send_private_reply(
                    account_id=account_id,
                    comment_id=comment_id,
                    message=message_text,
                )
                status = (
                    AutomationExecution.Status.SENT
                    if success
                    else AutomationExecution.Status.FAILED
                )

        except Exception:
            logger.exception("❌ Error sending reply | rule=%s", rule.name)
            status = AutomationExecution.Status.FAILED

        # ==================== ثبت اجرا ====================
        if payload is not None:
            AutomationExecution.objects.create(
                automation=rule,
                event=event,
                status=status,
                response_payload=payload,
            )
            logger.warning(
                "📝 Execution recorded | rule=%s | status=%s",
                rule.name, status,
            )

    logger.warning(
        "🏁 process_real_comment DONE | @%s | comment_id=%s | matched=%s | total=%s",
        connection.username, comment_id, len(matched_rules), rules_count,
    )
