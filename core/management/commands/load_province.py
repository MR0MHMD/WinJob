# core/management/commands/load_provinces.py

import json
import urllib.request
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from core.models import Province


PROVINCES_URL = (
    "https://raw.githubusercontent.com/sajaddp/list-of-cities-in-Iran/main/dist/json/provinces.json"
)


class Command(BaseCommand):
    help = "بارگذاری استان‌های ایران از منبع رسمی sajaddp"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="قبل از لود، همه استان‌های موجود پاک شن (خطرناک!)",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted = Province.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"🗑  {deleted[0]} استان حذف شد."))

        self.stdout.write("📥 دانلود لیست استان‌ها...")
        with urllib.request.urlopen(PROVINCES_URL) as resp:
            provinces_data = json.loads(resp.read().decode("utf-8"))

        self.stdout.write(f"   {len(provinces_data)} استان دریافت شد.")

        created = 0
        updated = 0
        unchanged = 0

        with transaction.atomic():
            for p in provinces_data:
                source_id = str(p["id"]).strip()
                name = p["name"].strip()
                slug = p.get("slug") or slugify(name, allow_unicode=True)

                obj = Province.objects.filter(source_id=source_id).first()

                if obj is None:
                    # اگه با همین نام هست، فقط source_id رو ست کن
                    obj = Province.objects.filter(name=name).first()
                    if obj:
                        if obj.source_id != source_id:
                            obj.source_id = source_id
                            obj.save()
                            updated += 1
                            self.stdout.write(self.style.SUCCESS(
                                f"🔄 Updated source_id: {name} → {source_id}"
                            ))
                        else:
                            unchanged += 1
                    else:
                        Province.objects.create(
                            source_id=source_id,
                            name=name,
                            slug=slug,
                        )
                        created += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"✅ Created: {name} (id={source_id})"
                        ))
                else:
                    if obj.name != name:
                        obj.name = name
                        obj.save()
                        updated += 1
                    else:
                        unchanged += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ تمام! {created} جدید، {updated} بروزرسانی، {unchanged} بدون تغییر."
        ))