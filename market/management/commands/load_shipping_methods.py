# market/management/commands/load_shipping_methods.py

from django.core.management.base import BaseCommand
from django.db import transaction

from market.models import ShippingMethod


DEFAULT_METHODS = [
    {
        "slug": "post-pishtaz",
        "name": "پست پیشتاز",
        "icon": "bi-truck",
        "description": "ارسال عادی ۳ تا ۵ روز کاری",
        "order": 1,
        "is_active": True,
    },
    {
        "slug": "tipax",
        "name": "تیپاکس",
        "icon": "bi-lightning-charge-fill",
        "description": "ارسال سریع ۱ تا ۲ روز کاری",
        "order": 2,
        "is_active": True,
    },
]


class Command(BaseCommand):
    help = "بارگذاری روش‌های ارسال پیش‌فرض (پست پیشتاز و تیپاکس)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="مقادیر روش‌های ارسال موجود رو به مقادیر پیش‌فرض برگردون",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options.get("reset", False)

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for item in DEFAULT_METHODS:
            slug = item["slug"]

            existing = ShippingMethod.objects.filter(slug=slug).first()

            if existing is None:
                ShippingMethod.objects.create(**item)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✅ ساخته شد: {item['name']} ({slug})")
                )
            else:
                if reset:
                    for field, value in item.items():
                        setattr(existing, field, value)
                    existing.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"♻️  آپدیت شد: {item['name']} ({slug})")
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.NOTICE(f"⏭  از قبل موجوده: {item['name']} ({slug})")
                    )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"🎯 خلاصه: {created_count} ساخته شد، "
                f"{updated_count} آپدیت شد، {skipped_count} رد شد."
            )
        )

        if skipped_count > 0 and not reset:
            self.stdout.write(
                self.style.NOTICE(
                    "💡 برای بازنویسی مقادیر موجود، با --reset اجرا کن:\n"
                    "   python manage.py load_shipping_methods --reset"
                )
            )