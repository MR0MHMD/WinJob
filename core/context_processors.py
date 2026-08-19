from django.conf import settings
from core.models import Platform


def platform_info(request):
    """
    Context processor برای ارسال اطلاعات پلتفرم‌های فعال به تمام تمپلیت‌ها
    فقط نام و لوگوی پلتفرم‌های فعال رو برمی‌گردونه
    """
    platforms = Platform.objects.filter(is_active=True).only('name', 'logo')

    return {
        'platforms': platforms,
    }

def domain(request):
    """
    نام دامنه رو برمیگردونه
    """
    return {
        'domain': settings.SITE_URL,
    }
