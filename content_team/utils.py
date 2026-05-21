from django.utils import timezone
from datetime import datetime
import jdatetime


def get_team_province(team):
    """دریافت استان تیم از طریق مدیر تیم"""
    try:
        manager = team.members.filter(role='manager', is_active=True).first()
        if manager and manager.user and manager.user.province:
            return manager.user.province
    except:
        pass
    return None


def content_order_file_path(instance, filename):
    """
    مسیر ذخیره فایل‌های سفارش
    پشتیبانی از ContentOrderFile و ContentDeliveryFile
    """
    if hasattr(instance, 'order') and instance.order:
        return f'content_orders/{instance.order.campaign.id}/{instance.order.id}/{filename}'

    elif hasattr(instance, 'delivery') and instance.delivery:
        return f'content_orders/{instance.delivery.order.campaign.id}/{instance.delivery.order.id}/delivery/{filename}'

    # fallback
    return f'content_orders/unknown/{filename}'


def get_jalali_month_name(dt):
    """دریافت نام ماه شمسی از تاریخ میلادی (dt: datetime)"""
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    month_names = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                   'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
    return month_names[jd.month - 1]


def get_last_n_months(n=6):
    """بازگرداندن لیست datetime از اولین روز هر ماه برای n ماه گذشته (شامل ماه جاری)"""
    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    months = []
    for i in range(n - 1, -1, -1):
        year = current_month_start.year
        month = current_month_start.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append(datetime(year, month, 1, tzinfo=timezone.get_current_timezone()))
    return months
