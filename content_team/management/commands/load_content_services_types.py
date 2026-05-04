from django.core.management.base import BaseCommand
from content_team.models import ContentServiceType
from campaigns.models import AdType


class Command(BaseCommand):
    help = 'بارگذاری انواع خدمات تولید محتوا در سیستم'

    def handle(self, *args, **kwargs):
        ad_types = list(AdType.objects.all())

        if not ad_types:
            self.stdout.write(self.style.WARNING('⚠️ هیچ نوع تبلیغی در سیستم یافت نشد! اول AdTypeها رو بساز.'))
            return

        services_data = [
            {
                'name': 'طراحی استوری',
                'slug': 'instagram-story-design',
                'description': 'طراحی حرفه‌ای استوری‌های جذاب و تعاملی برای اینستاگرام با متحرک‌سازی ملایم',
                'icon': 'bi-camera-reels',
                'unit': 'project',
            },
            {
                'name': 'تولید ویدیو کوتاه',
                'slug': 'short-video-production',
                'description': 'تولید ویدیوهای کوتاه ۱۵ تا ۶۰ ثانیه‌ای مناسب ریلز، تیک‌تاک و یوتیوب شورت',
                'icon': 'bi-film',
                'unit': 'minute',
            },
            {
                'name': 'موشن گرافیک',
                'slug': 'motion-graphics',
                'description': 'ساخت انیمیشن‌های گرافیکی، تایپوگرافی متحرک و ویدیوهای تبلیغاتی پویا',
                'icon': 'bi-stars',
                'unit': 'minute',
            },
            {
                'name': 'عکاسی تبلیغاتی',
                'slug': 'commercial-photography',
                'description': 'عکاسی حرفه‌ای از محصولات، غذا، مد و فضاهای تجاری برای استفاده در کمپین‌ها',
                'icon': 'bi-camera',
                'unit': 'project',
            },
            {
                'name': 'طراحی پوستر و بنر',
                'slug': 'poster-banner-design',
                'description': 'طراحی بنرهای تبلیغاتی، پوسترهای شبکه‌های اجتماعی و اورچهای ویژه کمپین',
                'icon': 'bi-brush',
                'unit': 'project',
            },
            {
                'name': 'پادکست و محتوای صوتی',
                'slug': 'podcast-audio-content',
                'description': 'تولید پادکست، ضبط حرفه‌ای صدا، میکس و مسترینگ برای تبلیغات صوتی',
                'icon': 'bi-mic',
                'unit': 'minute',
            },
            {
                'name': 'اینفوگرافیک متحرک',
                'slug': 'animated-infographic',
                'description': 'تبدیل داده‌ها و آمار به انیمیشن‌های جذاب و قابل فهم برای محتوای آموزشی',
                'icon': 'bi-graph-up',
                'unit': 'project',
            },
            {
                'name': 'تدوین ویدیو',
                'slug': 'video-editing',
                'description': 'تدوین حرفه‌ای، رنگ‌اصلاحی، افکت‌گذاری و اصلاح صدای ویدیوهای خام',
                'icon': 'bi-scissors',
                'unit': 'minute',
            },
        ]

        created_count = 0
        updated_count = 0

        for service_data in services_data:
            obj, created = ContentServiceType.objects.update_or_create(
                slug=service_data['slug'],
                defaults={
                    'name': service_data['name'],
                    'description': service_data['description'],
                    'icon': service_data['icon'],
                    'unit': service_data['unit'],
                    'is_active': True,
                    'display_order': services_data.index(service_data),
                }
            )

            # اضافه کردن همه AdTypeها به این سرویس
            obj.ad_type.set(ad_types)

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ ایجاد شد: {obj.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'🔄 به‌روزرسانی شد: {obj.name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n🎉 عملیات با موفقیت انجام شد!\n'
            f'📦 ایجاد شده: {created_count}\n'
            f'🔄 به‌روزرسانی: {updated_count}\n'
            f'📎 هر سرویس به {len(ad_types)} نوع تبلیغ متصل شد.'
        ))
