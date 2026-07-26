from django.core.management.base import BaseCommand
from core.models import Platform
from campaigns.models import AdType


class Command(BaseCommand):
    help = "Create default AdTypes for platforms"

    def handle(self, *args, **options):

        platforms = [
            ("بله", "bale"),
            ("ایتا", "eitaa"),
            ("سروش پلاس", "sorush"),
            ("روبیکا", "rubika"),
            ("تلگرام", "telegram"),
            ("اینستاگرام", "instagram"),
        ]

        created = 0

        for name, slug in platforms:
            try:
                platform = Platform.objects.get(slug=slug)
            except Platform.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Platform not found: {slug}"))
                continue

            ad_types = [
                {
                    "name": f"استوری {name}",
                    "slug": f"{slug}-story",
                    "icon": "bi-plus-circle",
                    "description": f"تبلیغ استوری در {name} روشی سریع و تاثیرگذار برای دیده شدن برند شماست. "
                                   f"این نوع تبلیغ در قالب استوری منتشر می‌شود و برای معرفی سریع خدمات یا جذب مخاطب بسیار مناسب است."
                },
                {
                    "name": f"پست {name}",
                    "slug": f"{slug}-post",
                    "icon": "bi-postcard",
                    "description": f"تبلیغ پستی در {name} به صورت انتشار یک پست در کانال یا صفحه انجام می‌شود "
                                   f"و یکی از رایج‌ترین روش‌های تبلیغات برای رساندن پیام برند به مخاطبان هدف است."
                },
                {
                    "name": f"پست شبانه {name}",
                    "slug": f"{slug}-night-post",
                    "icon": "bi-moon-stars-fill",
                    "description": f"پست شبانه در {name} در بازه زمانی ۱۲ شب تا ۱۲ ظهر منتشر می‌شود. "
                                   f"این زمان معمولاً رقابت تبلیغاتی کمتری دارد و می‌تواند باعث دیده شدن بهتر تبلیغ شما شود."
                },
            ]

            # پین فقط برای غیر اینستاگرام
            if slug != "instagram":
                ad_types.append({
                    "name": f"پین در لیست پیام های {name}",
                    "slug": f"{slug}-pin",
                    "icon": "bi-pin-angle-fill",
                    "description": f"در این نوع تبلیغ، پیام شما در بالای لیست پیام‌های {name} پین می‌شود "
                                   f"و برای مدت مشخصی در معرض دید کاربران قرار می‌گیرد که باعث افزایش بازدید و تعامل می‌شود."
                })

            for item in ad_types:
                obj, was_created = AdType.objects.get_or_create(
                    platform=platform,
                    slug=item["slug"],
                    defaults={
                        "name": item["name"],
                        "icon": item["icon"],
                        "description": item["description"],
                        "is_active": True,
                    }
                )

                if was_created:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"Created: {obj}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Exists: {obj}"))

        self.stdout.write(self.style.SUCCESS(f"\n✅ {created} ad types created"))
