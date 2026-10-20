# market/management/commands/load_market_categories.py

from django.core.management.base import BaseCommand
from django.db import transaction

from market.models import Category


DEFAULT_CATEGORIES = [
    {"name": "موبایل و تبلت",           "slug": "mobile-tablet",         "icon": "bi-phone",              "order": 1},
    {"name": "لپ‌تاپ و کامپیوتر",        "slug": "laptop-computer",       "icon": "bi-laptop",             "order": 2},
    {"name": "لوازم جانبی دیجیتال",      "slug": "digital-accessories",   "icon": "bi-headphones",         "order": 3},
    {"name": "دوربین و عکاسی",           "slug": "camera-photography",    "icon": "bi-camera",             "order": 4},
    {"name": "تلویزیون و صوتی",          "slug": "tv-audio",              "icon": "bi-tv",                 "order": 5},
    {"name": "کنسول بازی و گیمینگ",      "slug": "gaming-consoles",       "icon": "bi-controller",         "order": 6},
    {"name": "لوازم خانگی برقی",         "slug": "home-appliances",       "icon": "bi-house-door",         "order": 7},
    {"name": "لوازم آشپزخانه",           "slug": "kitchen-utensils",      "icon": "bi-cup-hot",            "order": 8},
    {"name": "پوشاک مردانه",             "slug": "men-clothing",          "icon": "bi-person",             "order": 9},
    {"name": "پوشاک زنانه",              "slug": "women-clothing",        "icon": "bi-person-heart",       "order": 10},
    {"name": "کیف و کفش",                "slug": "bags-shoes",            "icon": "bi-bag",                "order": 11},
    {"name": "ساعت و اکسسوری",           "slug": "watch-accessories",     "icon": "bi-watch",              "order": 12},
    {"name": "آرایشی و زیبایی",          "slug": "beauty-cosmetics",      "icon": "bi-flower1",            "order": 13},
    {"name": "عطر و ادکلن",              "slug": "perfume-cologne",       "icon": "bi-droplet",            "order": 14},
    {"name": "مراقبت از پوست",           "slug": "skincare",              "icon": "bi-heart-pulse",        "order": 15},
    {"name": "سلامت و پزشکی",             "slug": "health-medical",        "icon": "bi-capsule",            "order": 16},
    {"name": "ورزش و تناسب اندام",       "slug": "sports-fitness",        "icon": "bi-bicycle",            "order": 17},
    {"name": "کمپینگ و سفر",             "slug": "camping-travel",        "icon": "bi-backpack2",          "order": 18},
    {"name": "ابزار و تجهیزات",          "slug": "tools-equipment",       "icon": "bi-tools",              "order": 19},
    {"name": "خودرو و موتورسیکلت",       "slug": "auto-motorcycle",       "icon": "bi-car-front",          "order": 20},
    {"name": "کتاب و لوازم‌التحریر",      "slug": "books-stationery",      "icon": "bi-book",               "order": 21},
    {"name": "اسباب‌بازی و کودک",         "slug": "toys-kids",             "icon": "bi-balloon",            "order": 22},
    {"name": "نوزاد و سیسمونی",          "slug": "baby-nursery",          "icon": "bi-emoji-smile",        "order": 23},
    {"name": "حیوانات خانگی",            "slug": "pets",                  "icon": "bi-heart",              "order": 24},
    {"name": "مواد غذایی و نوشیدنی",     "slug": "food-beverages",        "icon": "bi-cup-straw",          "order": 25},
    {"name": "گل و گیاه",                "slug": "flowers-plants",        "icon": "bi-flower2",            "order": 26},
    {"name": "صنایع دستی",               "slug": "handicrafts",           "icon": "bi-palette",            "order": 27},
    {"name": "لوازم اداری",              "slug": "office-supplies",       "icon": "bi-briefcase",          "order": 28},
    {"name": "موسیقی و آلات",             "slug": "music-instruments",     "icon": "bi-music-note-beamed",  "order": 29},
    {"name": "فیلم و سریال",             "slug": "movies-series",         "icon": "bi-camera-reels",       "order": 30},
]


class Command(BaseCommand):
    help = "بارگذاری دسته‌بندی‌های پیش‌فرض وین‌مارکت"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="مقادیر دسته‌بندی‌های موجود را هم آپدیت کن",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options.get("reset", False)

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for item in DEFAULT_CATEGORIES:
            slug = item["slug"]
            existing = Category.objects.filter(slug=slug).first()

            if existing is None:
                Category.objects.create(
                    name=item["name"],
                    slug=item["slug"],
                    icon=item["icon"],
                    order=item["order"],
                    is_active=True,
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ ساخته شد: {item['name']}"))
            else:
                if reset:
                    existing.name = item["name"]
                    existing.icon = item["icon"]
                    existing.order = item["order"]
                    existing.save(update_fields=["name", "icon", "order"])
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f"♻️  آپدیت شد: {item['name']}"))
                else:
                    skipped_count += 1
                    self.stdout.write(self.style.NOTICE(f"⏭  موجود: {item['name']}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"🎯 خلاصه: {created_count} ساخته شد، "
            f"{updated_count} آپدیت، {skipped_count} رد شد."
        ))

        if skipped_count > 0 and not reset:
            self.stdout.write(self.style.NOTICE(
                "💡 برای بازنویسی مقادیر موجود، با --reset اجرا کن:\n"
                "   python manage.py load_market_categories --reset"
            ))