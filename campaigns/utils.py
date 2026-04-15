from django.utils import timezone
from django.core.exceptions import ValidationError
import jdatetime

from content_team.models import ContentOrderFile


def validate_start_date(start_date):
    """
    اعتبارسنجی تاریخ شروع. تاریخ شروع نباید قبل از تاریخ و زمان فعلی باشد.
    """
    # تبدیل تاریخ جلالی به میلادی
    if isinstance(start_date, jdatetime.datetime):  # چک کردن اینکه تاریخ جلالی است
        start_date = start_date.togregorian()  # تبدیل به تاریخ میلادی

    # مقایسه تاریخ‌ها
    if start_date < timezone.now():
        raise ValueError("تاریخ شروع نمی‌تواند قبل از تاریخ و زمان فعلی باشد.")


def validate_end_date(start_date, end_date):
    """
    اعتبارسنجی تاریخ پایان که باید بعد از تاریخ شروع باشد
    """
    # تبدیل تاریخ جلالی به میلادی اگر تاریخ جلالی باشه
    if isinstance(start_date, jdatetime.datetime):  # چک کردن تاریخ جلالی بودن
        start_date = start_date.togregorian()

    if isinstance(end_date, jdatetime.datetime):  # چک کردن تاریخ جلالی بودن
        end_date = end_date.togregorian()

    # مقایسه تاریخ‌ها
    if end_date <= start_date:
        raise ValidationError('تاریخ پایان باید بعد از تاریخ شروع باشد.')


def jalali_str_to_datetime(jalali_str):
    """
    رشته شمسی (ممکنه اعداد فارسی باشه) رو به datetime میلادی تبدیل میکنه
    فرمت ورودی: 'YYYY/MM/DD HH:MM' یا 'YYYY/MM/DD'
    """
    persian_nums = '۰۱۲۳۴۵۶۷۸۹'
    arabic_nums = '٠١٢٣٤٥٦٧٨٩'
    for i, (p, a) in enumerate(zip(persian_nums, arabic_nums)):
        jalali_str = jalali_str.replace(p, str(i)).replace(a, str(i))

    jalali_str = jalali_str.strip()

    if ' ' in jalali_str:
        jdt = jdatetime.datetime.strptime(jalali_str, '%Y/%m/%d %H:%M')
    else:
        jdt = jdatetime.datetime.strptime(jalali_str, '%Y/%m/%d')

    gregorian_dt = jdt.togregorian()
    return timezone.make_aware(gregorian_dt)


def _detect_file_type(file):
    """تشخیص نوع فایل"""
    content_type = getattr(file, 'content_type', '')

    if content_type.startswith('image/'):
        return ContentOrderFile.FileType.IMAGE
    elif content_type.startswith('video/'):
        return ContentOrderFile.FileType.VIDEO
    elif content_type.startswith('audio/'):
        return ContentOrderFile.FileType.AUDIO
    elif content_type in ['application/pdf', 'application/msword',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        return ContentOrderFile.FileType.DOCUMENT

    return ContentOrderFile.FileType.OTHER