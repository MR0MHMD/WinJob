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
    پشتیبانی از:
    - ContentOrderFile (فایل‌های پیوست سفارش)
    - ContentDeliveryFile (فایل‌های تحویل سفارش)
    - سفارش‌های مستقل (بدون کمپین)
    - سفارش‌های متصل به کمپین
    """

    # ====== حالت اول: فایل پیوست سفارش (ContentOrderFile) ======
    if hasattr(instance, 'order') and instance.order:
        order = instance.order

        # بررسی اینکه سفارش مستقل هست یا به کمپین متصل
        if order.is_standalone:
            # سفارش مستقل تولید محتوا
            return f'content_orders/standalone/{order.id}/{filename}'
        elif order.campaign_id:
            # سفارش متصل به کمپین
            return f'content_orders/campaign/{order.campaign_id}/{order.id}/{filename}'
        else:
            # fallback (اگه هیچکدوم)
            return f'content_orders/unknown/{order.id}/{filename}'

    # ====== حالت دوم: فایل تحویل سفارش (ContentDeliveryFile) ======
    elif hasattr(instance, 'delivery') and instance.delivery:
        delivery = instance.delivery
        order = delivery.order

        if order.is_standalone:
            return f'content_orders/standalone/{order.id}/delivery/{filename}'
        elif order.campaign_id:
            return f'content_orders/campaign/{order.campaign_id}/{order.id}/delivery/{filename}'
        else:
            return f'content_orders/unknown/{order.id}/delivery/{filename}'

    # ====== fallback نهایی ======
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
