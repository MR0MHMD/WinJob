"""اجرای محلی مکالمه؛ بدون فراخوانی متا یا سرویس هوش مصنوعی."""
import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from .models import (InstagramConnection, DirectRule, DirectMessageEvent, FormSubmission)
from .services import _normalize, _matches


def _question(schema, index):
    """متن سؤال را همراه گزینه‌های احتمالی آماده می‌کند."""
    question = schema['questions'][index]
    options = question['options']
    return question['prompt'] + ('\n' + '\n'.join(options) if options else '')


def _answer(question, text):
    """پاسخ را بر اساس نوع سؤال اعتبارسنجی و ارقام را یکسان می‌کند."""
    value = text.strip()
    digits = value.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
    kind = question['kind']
    if kind == 'number':
        if not re.fullmatch(r'-?[0-9]{1,18}', digits):
            raise ValidationError('لطفاً یک عدد صحیح (حداکثر ۱۸ رقم) وارد کنید.')
        return digits
    if kind == 'phone':
        if not re.fullmatch(r'09[0-9]{9}', digits):
            raise ValidationError('شمارهٔ همراه را با ۰۹ و در ۱۱ رقم وارد کنید.')
        return digits
    if kind == 'email':
        try:
            validate_email(value)
        except ValidationError:
            raise ValidationError('لطفاً یک نشانی ایمیل معتبر وارد کنید.')
    if kind == 'choice':
        for option in question['options']:
            if _normalize(option) == _normalize(value):
                return option
        raise ValidationError('لطفاً یکی از گزینه‌های نمایش‌داده‌شده را بنویسید.')
    return value


@transaction.atomic
def simulate_direct(*, connection, sender_id, message_id, text):
    """یک پیام نمونه را یک‌بار پردازش می‌کند و پیشرفت فرم را نگه می‌دارد."""
    connection = InstagramConnection.objects.select_for_update().get(pk=connection.pk)
    if connection.status != InstagramConnection.Status.SIMULATED:
        raise ValidationError('آزمایش فقط برای حساب آزمایشی مجاز است.')
    if not sender_id.strip() or not message_id.strip() or not text.strip():
        raise ValidationError('حساب، شناسهٔ مخاطب، شناسهٔ پیام و متن لازم هستند.')
    if len(sender_id) > 100 or len(message_id) > 100 or len(text) > 2000:
        raise ValidationError('طول ورودی بیشتر از حد مجاز است.')
    from .subscriptions.access import require_connection
    period = require_connection(connection, 'smart_direct')
    existing = DirectMessageEvent.objects.filter(connection=connection, external_message_id=message_id).first()
    if existing:
        if existing.sender_id != sender_id or existing.text != text:
            raise ValidationError('شناسهٔ پیام قبلاً برای ورودی دیگری استفاده شده است.')
        return existing, False
    event = DirectMessageEvent(connection=connection, external_message_id=message_id, sender_id=sender_id, text=text)
    active = FormSubmission.objects.select_for_update().filter(connection=connection, sender_id=sender_id, status='active').first()
    if active and not period.capabilities.get('forms'):
        raise ValidationError('برای ادامهٔ فرم، اشتراک دارای قابلیت فرم‌ساز لازم است.')
    if active:
        if _normalize(text) == _normalize(active.schema['cancel_keyword']):
            active.status = 'cancelled'
            response = {'kind': 'text', 'text': 'تکمیل فرم لغو شد. برای شروع دوباره کلمهٔ فعال‌کننده را بنویسید.'}
        else:
            index = len(active.answers)
            try:
                value = _answer(active.schema['questions'][index], text)
            except ValidationError as error:
                response = {'kind': 'text', 'text': error.messages[0] + '\n' + _question(active.schema, index)}
            else:
                active.answers.append(value)
                if len(active.answers) == len(active.schema['questions']):
                    active.status = 'completed'
                    active.completed_at = timezone.now()
                    response = {'kind': 'text', 'text': active.schema['completion_text']}
                else:
                    response = {'kind': 'text', 'text': _question(active.schema, len(active.answers))}
        active.save()
        response['submission_id'] = active.pk
    else:
        response = {'kind': 'unmatched', 'text': 'هیچ قانون فعالی با این پیام مطابقت نداشت.'}
        for rule in DirectRule.objects.filter(connection=connection, is_active=True).select_related('showcase', 'form'):
            if not _matches(rule, text):
                continue
            if rule.response_type == 'showcase':
                if not period.capabilities.get('showcases'):
                    continue
                if not rule.showcase or rule.showcase.connection_id != connection.pk or not rule.showcase.is_active:
                    continue
                cards = list(rule.showcase.cards.values('title', 'subtitle', 'image_url', 'button_title', 'button_url'))
                if not 1 <= len(cards) <= 10:
                    continue
                response = {'kind': 'showcase', 'text': rule.showcase.name, 'cards': cards}
            elif rule.response_type == 'form':
                if not period.capabilities.get('forms'):
                    continue
                if not rule.form or rule.form.connection_id != connection.pk or not rule.form.is_active:
                    continue
                questions = [{'id': q.pk, 'prompt': q.prompt, 'kind': q.kind,
                              'options': q.options.splitlines() if q.kind == 'choice' else []}
                             for q in rule.form.questions.all()]
                if not 1 <= len(questions) <= 20:
                    continue
                schema = {'questions': questions, 'completion_text': rule.form.completion_text,
                          'cancel_keyword': rule.form.cancel_keyword}
                submission = FormSubmission.objects.create(form=rule.form, connection=connection,
                    sender_id=sender_id, schema=schema)
                response = {'kind': 'text', 'text': _question(schema, 0) + '\nبرای انصراف: ' + schema['cancel_keyword'],
                            'submission_id': submission.pk}
            else:
                response = {'kind': 'text', 'text': rule.reply_text}
            event.rule = rule
            break
    event.response = response
    event.save()
    return event, True
