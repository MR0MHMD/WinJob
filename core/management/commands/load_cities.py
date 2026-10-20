# core/management/commands/load_cities.py

import json
import urllib.request
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Province, City


CITIES_URL = (
    "https://raw.githubusercontent.com/sajaddp/list-of-cities-in-Iran/main/dist/json/cities.json"
)


class Command(BaseCommand):
    help = "بارگذاری همه شهرهای ایران از مخزن رسمی sajaddp"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="قبل از لود، همه شهرهای موجود پاک شن",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted = City.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"🗑  {deleted[0]} شهر حذف شد."))

        # ---- ۱. خواندن استان‌ها از دیتابیس ----
        # province_id (عددی) → Province object
        province_map = {
            str(p.source_id): p
            for p in Province.objects.filter(source_id__isnull=False)
        }
        self.stdout.write(f"   {len(province_map)} استان با source_id توی دیتابیس موجوده.")

        if not province_map:
            self.stdout.write(self.style.ERROR(
                "❌ هیچ استانی با source_id وجود نداره!\n"
                "   اول این دستور رو بزن:\n"
                "   python manage.py load_provinces"
            ))
            return

        # ---- ۲. خواندن شهرها ----
        self.stdout.write("📥 دانلود لیست شهرها...")
        with urllib.request.urlopen(CITIES_URL) as resp:
            cities_data = json.loads(resp.read().decode("utf-8"))
        self.stdout.write(f"   {len(cities_data)} شهر دریافت شد.")

        # ---- ۳. لود توی دیتابیس ----
        created = 0
        skipped = 0
        unknown_province = 0

        # برای سرعت، اسلاگ‌های موجود رو cache می‌کنیم
        existing_keys = set(
            City.objects.values_list("province_id", "slug")
        )

        with transaction.atomic():
            for c in cities_data:
                province_src = str(c["province_id"]).strip()
                province = province_map.get(province_src)

                if not province:
                    unknown_province += 1
                    continue

                name = c["name"].strip()
                slug = c["slug"].strip()

                # چک تکراری
                key = (province.id, slug)
                if key in existing_keys:
                    skipped += 1
                    continue

                City.objects.create(
                    province=province,
                    name=name,
                    slug=slug,
                )
                existing_keys.add(key)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ تمام! "
            f"{created} شهر جدید، "
            f"{skipped} تکراری، "
            f"{unknown_province} ناموفق (استان ناشناس)."
        ))
