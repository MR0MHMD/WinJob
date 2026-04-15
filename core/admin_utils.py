# core/admin_utils.py
from django.utils import timezone


def format_datetime(dt):
    """
    فرمت مرکزی برای تاریخ و زمان
    """
    try:
        if dt:
            # تبدیل به زمان محلی
            local_dt = timezone.localtime(dt)
            return local_dt.strftime('%Y/%m/%d | %H:%M:%S')
        return "-"
    except:
        return "نامشخص"


def format_date_only(dt):
    """
    تابع کمکی برای نمایش فقط تاریخ
    """
    try:
        if dt:
            # تبدیل به زمان محلی
            local_dt = timezone.localtime(dt)
            return local_dt.strftime('%Y/%m/%d')
        return "-"
    except:
        return "نامشخص"


def format_time_only(dt):
    """
    تابع کمکی برای نمایش فقط زمان
    """
    if not dt:
        return "-"

    try:
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        return dt.strftime('%H:%M:%S')
    except (AttributeError, ValueError, TypeError):
        return "-"
