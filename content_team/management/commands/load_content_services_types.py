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

        # ========== دیتای سرویس‌ها (بدون فیلد unit) ==========
        services_data = [
            {
                'name': 'طراحی استوری',
                'slug': 'instagram-story-design',
                'description': 'طراحی حرفه‌ای استوری‌های جذاب و تعاملی برای اینستاگرام با متحرک‌سازی ملایم',
                'icon': 'bi-camera-reels',
                'allowed_units': ['second', 'quantity'],
                'display_order': 0,
            },
            {
                'name': 'تولید ویدیو کوتاه',
                'slug': 'short-video-production',
                'description': 'تولید ویدیوهای کوتاه ۱۵ تا ۶۰ ثانیه‌ای مناسب ریلز، تیک‌تاک و یوتیوب شورت',
                'icon': 'bi-film',
                'allowed_units': ['second', 'minute'],
                'display_order': 1,
            },
            {
                'name': 'موشن گرافیک',
                'slug': 'motion-graphics',
                'description': 'ساخت انیمیشن‌های گرافیکی، تایپوگرافی متحرک و ویدیوهای تبلیغاتی پویا',
                'icon': 'bi-stars',
                'allowed_units': ['second'],
                'display_order': 2,
            },
            {
                'name': 'عکاسی تبلیغاتی',
                'slug': 'commercial-photography',
                'description': 'عکاسی حرفه‌ای از محصولات، غذا، مد و فضاهای تجاری برای استفاده در کمپین‌ها',
                'icon': 'bi-camera',
                'allowed_units': ['quantity'],
                'display_order': 3,
            },
            {
                'name': 'طراحی پوستر و بنر',
                'slug': 'poster-banner-design',
                'description': 'طراحی بنرهای تبلیغاتی، پوسترهای شبکه‌های اجتماعی و اورچهای ویژه کمپین',
                'icon': 'bi-brush',
                'allowed_units': ['quantity'],
                'display_order': 4,
            },
            {
                'name': 'پادکست و محتوای صوتی',
                'slug': 'podcast-audio-content',
                'description': 'تولید پادکست، ضبط حرفه‌ای صدا، میکس و مسترینگ برای تبلیغات صوتی',
                'icon': 'bi-mic',
                'allowed_units': ['second', 'minute'],
                'display_order': 5,
            },
            {
                'name': 'اینفوگرافیک متحرک',
                'slug': 'animated-infographic',
                'description': 'تبدیل داده‌ها و آمار به انیمیشن‌های جذاب و قابل فهم برای محتوای آموزشی',
                'icon': 'bi-graph-up',
                'allowed_units': ['second'],
                'display_order': 6,
            },
            {
                'name': 'تدوین ویدیو',
                'slug': 'video-editing',
                'description': 'تدوین حرفه‌ای، رنگ‌اصلاحی، افکت‌گذاری و اصلاح صدای ویدیوهای خام',
                'icon': 'bi-scissors',
                'allowed_units': ['minute', 'quantity'],
                'display_order': 7,
            },
        ]

        created_count = 0
        updated_count = 0

        for service_data in services_data:
            # ========== ایجاد یا به‌روزرسانی سرویس (بدون فیلد unit) ==========
            obj, created = ContentServiceType.objects.update_or_create(
                slug=service_data['slug'],
                defaults={
                    'name': service_data['name'],
                    'description': service_data['description'],
                    'icon': service_data['icon'],
                    'allowed_units': service_data['allowed_units'],  # ← فیلد جدید
                    'is_active': True,
                    'display_order': service_data['display_order'],
                }
            )

            # اضافه کردن همه AdTypeها به این سرویس
            obj.ad_type.set(ad_types)

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ ایجاد شد: {obj.name}'))
                self.stdout.write(f'   └─ واحدهای مجاز: {obj.get_allowed_units_display()}')
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'🔄 به‌روزرسانی شد: {obj.name}'))
                self.stdout.write(f'   └─ واحدهای مجاز: {obj.get_allowed_units_display()}')

        # ========== گزارش نهایی ==========
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('🎉 عملیات با موفقیت انجام شد!')
        self.stdout.write('=' * 50)
        self.stdout.write(f'📦 سرویس‌های ایجاد شده: {created_count}')
        self.stdout.write(f'🔄 سرویس‌های به‌روزرسانی شده: {updated_count}')
        self.stdout.write(f'📎 هر سرویس به {len(ad_types)} نوع تبلیغ متصل شد.')
        self.stdout.write('\n💡 نکته: برای تغییر واحدهای مجاز هر سرویس، به ادمین بروید.')
