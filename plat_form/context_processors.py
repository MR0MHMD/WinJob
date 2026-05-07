from .models import Platform


def platform_info(request):
    """
    Context processor برای ارسال اطلاعات پلتفرم‌های فعال به تمام تمپلیت‌ها
    فقط نام و لوگوی پلتفرم‌های فعال رو برمی‌گردونه
    """
    platforms = Platform.objects.filter(is_active=True).only('name', 'logo')

    return {
        'platforms': platforms,
    }