from django.core.exceptions import ValidationError
from django.db import transaction
from .models import DirectRule, DirectMessageEvent
from windirect.connections.models import InstagramConnection
from windirect.forms.models import FormSubmission
from windirect.forms.services import continue_form, start_form
from windirect.showcases.services import build_response
from windirect.common.matching import _matches


@transaction.atomic
def simulate_direct(*, connection, sender_id, message_id, text):
    """یک پیام نمونه را یک‌بار پردازش می‌کند و پیشرفت فرم را نگه می‌دارد."""
    connection = InstagramConnection.objects.select_for_update().get(pk=connection.pk)
    if connection.status != InstagramConnection.Status.SIMULATED:
        raise ValidationError("آزمایش فقط برای حساب آزمایشی مجاز است.")
    if not sender_id.strip() or not message_id.strip() or not text.strip():
        raise ValidationError("حساب، شناسهٔ مخاطب، شناسهٔ پیام و متن لازم هستند.")
    if len(sender_id) > 100 or len(message_id) > 100 or len(text) > 2000:
        raise ValidationError("طول ورودی بیشتر از حد مجاز است.")
    from windirect.subscriptions.access import require_connection

    period = require_connection(connection, "smart_direct")
    existing = DirectMessageEvent.objects.filter(
        connection=connection, external_message_id=message_id
    ).first()
    if existing:
        if existing.sender_id != sender_id or existing.text != text:
            raise ValidationError("شناسهٔ پیام قبلاً برای ورودی دیگری استفاده شده است.")
        return existing, False
    event = DirectMessageEvent(
        connection=connection,
        external_message_id=message_id,
        sender_id=sender_id,
        text=text,
    )
    active = (
        FormSubmission.objects.select_for_update()
        .filter(connection=connection, sender_id=sender_id, status="active")
        .first()
    )
    if active and not period.capabilities.get("forms"):
        raise ValidationError("برای ادامهٔ فرم، اشتراک دارای قابلیت فرم‌ساز لازم است.")
    if active:
        response = continue_form(active, text)
    else:
        response = {
            "kind": "unmatched",
            "text": "هیچ قانون فعالی با این پیام مطابقت نداشت.",
        }
        for rule in DirectRule.objects.filter(
            connection=connection, is_active=True
        ).select_related("showcase", "form"):
            if not _matches(rule, text):
                continue
            if rule.response_type == "showcase":
                if not period.capabilities.get("showcases"):
                    continue
                candidate = build_response(rule.showcase, connection)
                if candidate is None:
                    continue
                response = candidate
            elif rule.response_type == "form":
                if not period.capabilities.get("forms"):
                    continue
                candidate = start_form(rule.form, connection, sender_id)
                if candidate is None:
                    continue
                response = candidate
            else:
                response = {"kind": "text", "text": rule.reply_text}
            event.rule = rule
            break
    event.response = response
    event.save()
    return event, True
