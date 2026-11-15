"""مایگریشن داده برای ثبت ۴ پلن پیش‌فرض اشتراک وین فوروارد."""

from django.db import migrations


def seed_plans(apps, schema_editor):
    """ثبت پلن‌های پیش‌فرض ۷ روزه رایگان، ۳۰ روزه، ۹۰ روزه و یک‌ساله در دیتابیس."""
    Plan = apps.get_model("forward_subscriptions", "ForwardSubscriptionPlan")
    defaults = [
        {
            "code": "trial_7",
            "name": "اشتراک رایگان ۷ روزه",
            "description": "دسترسی کامل و رایگان به هر ۴ پلتفرم (بله، ایتا، روبیکا و سروش‌پلاس) به مدت ۷ روز؛ قابل استفاده یک‌بار برای هر کاربر.",
            "duration_days": 7,
            "price_per_platform": 0,
            "is_trial": True,
            "is_active": True,
            "is_featured": False,
            "position": 1,
        },
        {
            "code": "plan_30",
            "name": "اشتراک یک‌ماهه (۳۰ روزه)",
            "description": "۵۰ هزار تومان به ازای هر پلتفرم انتخابی (پلتفرم بله اجباری است).",
            "duration_days": 30,
            "price_per_platform": 50000,
            "is_trial": False,
            "is_active": True,
            "is_featured": False,
            "position": 2,
        },
        {
            "code": "plan_90",
            "name": "اشتراک سه‌ماهه (۹۰ روزه)",
            "description": "۱۳۵ هزار تومان به ازای هر پلتفرم انتخابی با تخفیف ۱۰٪ (پلتفرم بله اجباری است).",
            "duration_days": 90,
            "price_per_platform": 135000,
            "is_trial": False,
            "is_active": True,
            "is_featured": True,
            "position": 3,
        },
        {
            "code": "plan_365",
            "name": "اشتراک یک‌ساله (۳۶۵ روزه)",
            "description": "۵۰۰ هزار تومان به ازای هر پلتفرم انتخابی با بیشترین صرفه‌جویی (پلتفرم بله اجباری است).",
            "duration_days": 365,
            "price_per_platform": 500000,
            "is_trial": False,
            "is_active": True,
            "is_featured": False,
            "position": 4,
        },
    ]
    for item in defaults:
        Plan.objects.update_or_create(code=item["code"], defaults=item)


def unseed_plans(apps, schema_editor):
    """حذف پلن‌های پیش‌فرض در صورت برگشت مایگریشن."""
    Plan = apps.get_model("forward_subscriptions", "ForwardSubscriptionPlan")
    Plan.objects.filter(code__in=["trial_7", "plan_30", "plan_90", "plan_365"]).delete()


class Migration(migrations.Migration):
    """افزودن خودکار ۴ پلن پیش‌فرض اشتراک وین فوروارد."""

    dependencies = [
        ("forward_subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]
