from django.utils import timezone
from django.core.exceptions import ValidationError
import jdatetime
from datetime import timedelta
from content_team.models import ContentOrderFile


def validate_start_date(start_date):
    """
    تاریخ شروع نباید قبل از تاریخ فعلی باشد.
    start_date: jdatetime.date یا jdatetime.datetime
    """
    # تبدیل timezone.now() به jdatetime.date
    now_jalali = jdatetime.datetime.fromgregorian(datetime=timezone.now()).date()

    # اگر start_date از نوع jdatetime.datetime بود به date تبدیل کن
    if isinstance(start_date, jdatetime.datetime):
        start_date = start_date.date()

    if start_date < now_jalali:
        raise ValidationError("تاریخ شروع نمی‌تواند قبل از تاریخ امروز باشد.")


def validate_end_date(start_date, end_date):
    """
    تاریخ پایان باید بین 2 تا 14 روز بعد از تاریخ شروع باشد.
    start_date, end_date: jdatetime.date یا jdatetime.datetime
    """
    if isinstance(start_date, jdatetime.datetime):
        start_date = start_date.date()
    if isinstance(end_date, jdatetime.datetime):
        end_date = end_date.date()

    delta = (end_date - start_date).days

    if delta < 2:
        raise ValidationError('تاریخ پایان باید حداقل ۲ روز بعد از تاریخ شروع باشد.')
    if delta > 14:
        raise ValidationError('تاریخ پایان نباید بیشتر از ۱۴ روز بعد از تاریخ شروع باشد.')


def jalali_str_to_datetime(jalali_str):
    """
    رشته شمسی به jdatetime.date تبدیل می‌کند (نه datetime میلادی)
    فرمت ورودی: 'YYYY/MM/DD' یا 'YYYY/MM/DD HH:MM'
    خروجی: jdatetime.date (بدون ساعت)
    """
    # تبدیل اعداد فارسی و عربی به انگلیسی
    persian_nums = '۰۱۲۳۴۵۶۷۸۹'
    arabic_nums = '٠١٢٣٤٥٦٧٨٩'
    for i, (p, a) in enumerate(zip(persian_nums, arabic_nums)):
        jalali_str = jalali_str.replace(p, str(i)).replace(a, str(i))

    jalali_str = jalali_str.strip()

    # فقط قسمت تاریخ رو میگیریم (ساعت رو نادیده میگیریم)
    if ' ' in jalali_str:
        date_part = jalali_str.split(' ')[0]
    else:
        date_part = jalali_str

    # تبدیل به jdatetime.date
    try:
        parts = date_part.split('/')
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        return jdatetime.date(year, month, day)
    except (ValueError, IndexError):
        raise ValueError("فرمت تاریخ صحیح نیست. فرمت مورد انتظار: YYYY/MM/DD")


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