"""ایجاد پلن‌های اولیه بدون تغییر قیمت‌ها و تنظیمات ثبت‌شدهٔ قبلی."""

from django.core.management.base import BaseCommand
from django.db import transaction
from windirect.models import SubscriptionPlan, SubscriptionOffer


class Command(BaseCommand):
    help = "ساخت پلن رایگان، پایه و حرفه‌ای؛ قیمت‌های پولی را از ادمین تنظیم کنید."

    @transaction.atomic
    def handle(self, *args, **options):
        """دادهٔ موجود را بازنویسی نمی‌کند و قیمت ساختگی برای فروش نمی‌گذارد."""
        definitions = [
            (
                "trial",
                "رایگان",
                {
                    "is_trial": True,
                    "level": 0,
                    "forms": True,
                    "showcases": True,
                    "max_pages": 5,
                    "position": 1,
                },
            ),
            ("basic", "پایه", {"level": 1, "max_pages": 1, "position": 2}),
            (
                "professional",
                "حرفه‌ای",
                {
                    "level": 2,
                    "forms": True,
                    "showcases": True,
                    "max_pages": 5,
                    "is_featured": True,
                    "position": 3,
                },
            ),
        ]
        for code, name, values in definitions:
            plan, _ = SubscriptionPlan.objects.get_or_create(
                code=code, defaults={"name": name, **values}
            )
            for days in ([30] if plan.is_trial else [30, 90, 365]):
                SubscriptionOffer.objects.get_or_create(
                    plan=plan,
                    duration_days=days,
                    defaults={"price": 0, "is_active": plan.is_trial},
                )
        self.stdout.write(
            self.style.SUCCESS(
                "پلن‌ها آماده‌اند. قیمت دوره‌های پولی را در ادمین وارد و قابل فروش کنید."
            )
        )
