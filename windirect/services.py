import unicodedata

from django.db import transaction

from .models import Automation, AutomationExecution, CommentEvent, InstagramConnection


def _normalize(value):
    """حروف و شکل‌های رایج نوشتار فارسی را برای تطبیق یکسان می‌کند."""
    return unicodedata.normalize("NFKC", value).replace("ي", "ی").replace("ك", "ک").strip().casefold()


def _matches(automation, text):
    """بررسی می‌کند متن کامنت با شرط قانون سازگار است یا نه."""
    keyword = _normalize(automation.keyword)
    comment = _normalize(text)
    if not keyword:
        return False
    if automation.match_type == Automation.MatchType.EXACT:
        return keyword == comment
    return keyword in comment


@transaction.atomic
def simulate_comment(*, connection, comment_id, media_id, text):
    """کامنت و اجرای آزمایشی قوانین را بدون ارسال پیام ثبت می‌کند."""
    if connection.status != InstagramConnection.Status.SIMULATED:
        raise ValueError("شبیه‌سازی فقط برای حساب آزمایشی مجاز است.")
    if not comment_id or not media_id or not text:
        raise ValueError("شناسهٔ کامنت، شناسهٔ پست و متن کامنت لازم هستند.")

    event, created = CommentEvent.objects.get_or_create(
        connection=connection, external_comment_id=comment_id,
        defaults={"media_id": media_id, "text": text},
    )
    if not created:
        return event, []

    executions = []
    rules = Automation.objects.filter(connection=connection, is_active=True)
    for rule in rules:
        if (not rule.media_id or rule.media_id == media_id) and _matches(rule, text):
            executions.append(AutomationExecution.objects.create(
                automation=rule, event=event, response_text=rule.reply_text,
            ))
    return event, executions
