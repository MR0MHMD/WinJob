from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Bank


BANKS = [
    {"name": "بانک مرکزی جمهوری اسلامی ایران", "slug": "markazi", "code": "010", "order": 1},
    {"name": "بانک صنعت و معدن", "slug": "sanat-madan", "code": "011", "order": 2},
    {"name": "بانک ملت", "slug": "mellat", "code": "012", "order": 3},
    {"name": "بانک رفاه کارگران", "slug": "refah", "code": "013", "order": 4},
    {"name": "بانک مسکن", "slug": "maskan", "code": "014", "order": 5},
    {"name": "بانک سپه", "slug": "sepah", "code": "015", "order": 6},
    {"name": "بانک کشاورزی", "slug": "keshavarzi", "code": "016", "order": 7},
    {"name": "بانک ملی ایران", "slug": "melli", "code": "017", "order": 8},
    {"name": "بانک تجارت", "slug": "tejarat", "code": "018", "order": 9},
    {"name": "بانک صادرات ایران", "slug": "saderat", "code": "019", "order": 10},
    {"name": "بانک توسعه صادرات ایران", "slug": "tosee-saderat", "code": "020", "order": 11},
    {"name": "پست بانک ایران", "slug": "postbank", "code": "021", "order": 12},
    {"name": "بانک توسعه تعاون", "slug": "tosee-taavon", "code": "022", "order": 13},
    {"name": "بانک کارآفرین", "slug": "karafarin", "code": "053", "order": 14},
    {"name": "بانک پارسیان", "slug": "parsian", "code": "054", "order": 15},
    {"name": "بانک اقتصاد نوین", "slug": "eghtesad-novin", "code": "055", "order": 16},
    {"name": "بانک سامان", "slug": "saman", "code": "056", "order": 17},
    {"name": "بانک پاسارگاد", "slug": "pasargad", "code": "057", "order": 18},
    {"name": "بانک سرمایه", "slug": "sarmayeh", "code": "058", "order": 19},
    {"name": "بانک سینا", "slug": "sina", "code": "059", "order": 20},
    {"name": "بانک قرض‌الحسنه مهر ایران", "slug": "mehr-iran", "code": "060", "order": 21},
    {"name": "بانک شهر", "slug": "shahr", "code": "061", "order": 22},
    {"name": "بانک آینده", "slug": "ayandeh", "code": "062", "order": 23},
    {"name": "بانک گردشگری", "slug": "gardeshgari", "code": "064", "order": 24},
    {"name": "بانک دی", "slug": "day", "code": "066", "order": 25},
    {"name": "بانک ایران زمین", "slug": "iran-zamin", "code": "069", "order": 26},
    {"name": "بانک قرض‌الحسنه رسالت", "slug": "resalat", "code": "070", "order": 27},
    {"name": "بانک خاورمیانه", "slug": "khavarmiane", "code": "078", "order": 28},
]


class Command(BaseCommand):
    help = "بارگذاری لیست کامل بانک‌های ایرانی به همراه لوگو"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="حتی اگر بانک وجود داشته باشد، اطلاعات و لوگوی آن را به‌روزرسانی کن",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        logo_count = 0
        missing_logo_count = 0

        force = options["force"]

        # مسیر:
        # static/core/images/banks/
        banks_logo_dir = (
            Path(settings.BASE_DIR)
            / "static"
            / "core"
            / "images"
            / "banks"
        )

        self.stdout.write(
            self.style.NOTICE(
                f"مسیر لوگوها: {banks_logo_dir}"
            )
        )
        self.stdout.write("")

        for bank_data in BANKS:

            # -----------------------------------------
            # ایجاد یا بروزرسانی بانک
            # -----------------------------------------

            bank, created = Bank.objects.update_or_create(
                code=bank_data["code"],
                defaults={
                    "name": bank_data["name"],
                    "slug": bank_data["slug"],
                    "is_active": True,
                    "order": bank_data["order"],
                },
            )

            if created:
                created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ ایجاد شد: {bank.name} ({bank.code})"
                    )
                )

            elif force:
                updated_count += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"↻ به‌روزرسانی شد: {bank.name} ({bank.code})"
                    )
                )

            else:
                self.stdout.write(
                    f"- قبلاً وجود داشت: {bank.name} ({bank.code})"
                )

            # -----------------------------------------
            # پیدا کردن لوگو
            # -----------------------------------------

            logo_path = banks_logo_dir / f"{bank.slug}.webp"

            if not logo_path.exists():
                missing_logo_count += 1

                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ لوگو پیدا نشد: {logo_path}"
                    )
                )

                continue

            # -----------------------------------------
            # ذخیره لوگو
            # -----------------------------------------

            # اگر بانک جدید است یا force فعال شده،
            # لوگو را ذخیره می‌کنیم.
            if created or force:

                with logo_path.open("rb") as logo_file:
                    bank.logo.save(
                        f"{bank.slug}.webp",
                        File(logo_file),
                        save=True,
                    )

                logo_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ لوگو اضافه شد: {bank.slug}.webp"
                    )
                )

        # -----------------------------------------
        # گزارش نهایی
        # -----------------------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"تمام شد! "
                f"{created_count} بانک جدید ایجاد شد"
            )
        )

        if force:
            self.stdout.write(
                self.style.WARNING(
                    f"{updated_count} بانک به‌روزرسانی شد"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{logo_count} لوگو با موفقیت ذخیره شد"
            )
        )

        if missing_logo_count:
            self.stdout.write(
                self.style.ERROR(
                    f"{missing_logo_count} لوگو پیدا نشد"
                )
            )
