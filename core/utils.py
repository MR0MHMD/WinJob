import random
import string
from jdatetime import datetime as jdatetime
import jdatetime




def generate_random_slug():
    """تولید اسلاگ تصادفی ۱۴ کاراکتری"""
    from content_team.models import ContentTeam
    characters = string.ascii_letters + string.digits
    while True:
        slug_candidate = ''.join(random.choices(characters, k=14))
        if not ContentTeam.objects.filter(slug=slug_candidate).exists():
            return slug_candidate


def convert_to_jalali(date_obj):
    """تبدیل تاریخ میلادی به شمسی"""
    if not date_obj:
        return None
    try:
        if hasattr(date_obj, 'date'):
            date_obj = date_obj.date()
        return jdatetime.date.fromgregorian(date=date_obj)
    except Exception as e:
        print(f"Error converting date: {e}")
        return None


def format_jalali_date(date, format_str='%Y/%m/%d'):
    """
    فرمت کردن تاریخ شمسی
    """
    jalali_date = convert_to_jalali(date)
    if jalali_date:
        return jalali_date.strftime(format_str)
    return '-'
