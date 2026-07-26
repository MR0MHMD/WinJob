from django.core.management.base import BaseCommand
from core.models import Platform

PLATFORMS = [
    {
        "name": "بله",
        "slug": "bale",
        "description": """
بله به دلیل ماهیت روزمره و کاربردی خود، بستری ارزشمند برای نمایش پیام برند شماست.
با وینجاب، تبلیغات بله بیشترین بازده ممکن را در این پیام‌رسان به‌دست بیاورید.
""",
    },
    {
        "name": "ایتا",
        "slug": "eitaa",
        "description": """
با تبلیغات در ایتا، به طیف گسترده‌ای از کاربران داخلی دسترسی خواهید داشت.
جریان کمک می‌کند کمپین‌ها دقیق، مقرون‌به‌صرفه و نتیجه‌محور اجرا شوند.
""",
    },
    {
        "name": "روبیکا",
        "slug": "rubika",
        "description": """
روبیکا امکان دیده‌شدن گسترده و تبلیغات متنوع را فراهم می‌کند.
ما به شما کمک می‌کنیم کمپین‌هایتان بیشترین تأثیر را در این بستر پرکاربرد داشته باشند.
""",
    },
    {
        "name": "سروش پلاس",
        "slug": "sorush",
        "description": """
اجرای تبلیغات در سروش با همکاری ناشران تأییدشده جریان، سریع، قابل‌اندازه‌گیری
و بدون هیچ‌گونه پیگیری اضافی انجام می‌شود.
""",
    },
    {
        "name": "تلگرام",
        "slug": "telegram",
        "description": """
در کانال‌ها و گروه‌های معتبر تلگرام تبلیغ کنید و پیام‌تان را مستقیم به مخاطب هدف برسانید.
جریان تبلیغات را در کانال‌های انتخابی شما منتشر می‌کند.
""",
    },
    {
        "name": "اینستاگرام",
        "slug": "instagram",
        "description": """
با تبلیغات اینستاگرام، برند شما در معرض دید مخاطبتان قرار می‌گیرد.
از افزایش آگاهی تا جذب کاربر، ما کمپین‌ها را به‌صورت هوشمند اجرا و مدیریت می‌کنیم
تا بهترین نتیجه حاصل شود.
""",
    },
]


class Command(BaseCommand):
    help = "Load predefined platform objects into the Platform model"

    def handle(self, *args, **options):
        created_count = 0

        for item in PLATFORMS:
            obj, created = Platform.objects.get_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["name"],
                    "description": item["description"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created: {obj.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Already exists: {obj.name}"))

        self.stdout.write(self.style.SUCCESS(f"\nDone! {created_count} new platforms created."))
