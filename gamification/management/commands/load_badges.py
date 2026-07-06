from django.core.management.base import BaseCommand
from gamification.models import Badge


class Command(BaseCommand):
    help = 'ایجاد ۶ نشان (پلاستیکی، چوبی، برنزی، نقره‌ای، طلایی، زمردی)'

    def handle(self, *args, **options):
        badges_data = [
            {
                'slug': 'plastic',
                'name': 'پلاستیکی',
                'min_points': -99999999,
                'order': 1,
                'description': "شروع دوباره! زمان بازگشت به مسیر اصلی فرا رسیده.",
            },
            {
                'slug': 'wood',
                'name': 'چوبی',
                'min_points': 0,
                'order': 2,
                'description': "نقطۀ شروع حرفه‌ای شما. با ادامه مسیر رشد کنید.",
            },
            {
                'slug': 'bronze',
                'name': 'برنزی',
                'min_points': 500,
                'order': 3,
                'description': "اولین قدم جدی در مسیر پیشرفت. نشان‌دهنده تعهد و پشتکار شماست.",
            },
            {
                'slug': 'silver',
                'name': 'نقره‌ای',
                'min_points': 1000,
                'order': 4,
                'description': "وارد جمع حرفه‌ای‌ها شده‌اید. توانایی شما در جلب رضایت مشتریان اثبات شده است.",
            },
            {
                'slug': 'gold',
                'name': 'طلایی',
                'min_points': 2000,
                'order': 5,
                'description': "جزو بهترین‌ها هستید. کیفیت کار شما زبانزد و اعتبارتان در پلتفرم ما بالا رفته.",
            },
            {
                'slug': 'emerald',
                'name': 'زمردی',
                'min_points': 3500,
                'order': 6,
                'description': "اسطوره‌ای در پلتفرم! عملکرد استثنایی شما الهام‌بخش دیگران است.",
            },
        ]

        created_count = 0
        updated_count = 0

        for data in badges_data:
            badge, created = Badge.objects.update_or_create(
                slug=data['slug'],
                defaults={
                    'name': data['name'],
                    'min_points': data['min_points'],
                    'order': data['order'],
                    'description': data['description'],
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ نشان «{data['name']}» ایجاد شد."))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"🔄 نشان «{data['name']}» به‌روزرسانی شد."))

        self.stdout.write(self.style.SUCCESS(
            f"\n✨ عملیات پایان یافت.\n"
            f"✅ {created_count} نشان جدید ایجاد شد.\n"
            f"🔄 {updated_count} نشان به‌روزرسانی شد."
        ))
