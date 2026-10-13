import re
from django.utils import timezone
from .models import FormSubmission
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from windirect.common.matching import _normalize


def _question(schema, index):
    """متن سؤال را همراه گزینه‌های احتمالی آماده می‌کند."""
    question = schema["questions"][index]
    options = question["options"]
    return question["prompt"] + ("\n" + "\n".join(options) if options else "")


def _answer(question, text):
    """پاسخ را بر اساس نوع سؤال اعتبارسنجی و ارقام را یکسان می‌کند."""
    value = text.strip()
    digits = value.translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    kind = question["kind"]
    if kind == "number":
        if not re.fullmatch(r"-?[0-9]{1,18}", digits):
            raise ValidationError("لطفاً یک عدد صحیح (حداکثر ۱۸ رقم) وارد کنید.")
        return digits
    if kind == "phone":
        if not re.fullmatch(r"09[0-9]{9}", digits):
            raise ValidationError("شمارهٔ همراه را با ۰۹ و در ۱۱ رقم وارد کنید.")
        return digits
    if kind == "email":
        try:
            validate_email(value)
        except ValidationError:
            raise ValidationError("لطفاً یک نشانی ایمیل معتبر وارد کنید.")
    if kind == "choice":
        for option in question["options"]:
            if _normalize(option) == _normalize(value):
                return option
        raise ValidationError("لطفاً یکی از گزینه‌های نمایش‌داده‌شده را بنویسید.")
    return value


def continue_form(active, text):
    """پاسخ بعدی یا لغو را روی نسخهٔ ثابت فرم اعمال می‌کند."""
    if _normalize(text) == _normalize(active.schema["cancel_keyword"]):
        active.status = "cancelled"
        response = {
            "kind": "text",
            "text": "تکمیل فرم لغو شد. برای شروع دوباره کلمهٔ فعال‌کننده را بنویسید.",
        }
    else:
        index = len(active.answers)
        try:
            value = _answer(active.schema["questions"][index], text)
        except ValidationError as error:
            response = {
                "kind": "text",
                "text": error.messages[0] + "\n" + _question(active.schema, index),
            }
        else:
            active.answers.append(value)
            if len(active.answers) == len(active.schema["questions"]):
                active.status = "completed"
                active.completed_at = timezone.now()
                response = {
                    "kind": "text",
                    "text": active.schema["completion_text"],
                }
            else:
                response = {
                    "kind": "text",
                    "text": _question(active.schema, len(active.answers)),
                }
    active.save()
    response["submission_id"] = active.pk
    return response


def start_form(form, connection, sender_id):
    """سؤال‌ها را هنگام شروع ثابت می‌کند و اولین پاسخ مکالمه را می‌سازد."""
    if not form or form.connection_id != connection.pk or not form.is_active:
        return None
    questions = [
        {
            "id": q.pk,
            "prompt": q.prompt,
            "kind": q.kind,
            "options": q.options.splitlines() if q.kind == "choice" else [],
        }
        for q in form.questions.all()
    ]
    if not 1 <= len(questions) <= 20:
        return None
    schema = {
        "questions": questions,
        "completion_text": form.completion_text,
        "cancel_keyword": form.cancel_keyword,
    }
    submission = FormSubmission.objects.create(
        form=form,
        connection=connection,
        sender_id=sender_id,
        schema=schema,
    )
    response = {
        "kind": "text",
        "text": _question(schema, 0) + "\nبرای انصراف: " + schema["cancel_keyword"],
        "submission_id": submission.pk,
    }
    return response
