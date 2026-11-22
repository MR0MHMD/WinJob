from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_jalali.db.models


def seed_token_system(apps, schema_editor):
    """حذف اشتراک‌های قدیمی و ایجاد بسته‌های استاندارد توکن و جدول نرخ‌های پیش‌فرض."""
    ForwardSubscriptionPlan = apps.get_model("forward_subscriptions", "ForwardSubscriptionPlan")
    ForwardPlatformAccess = apps.get_model("forward_subscriptions", "ForwardPlatformAccess")
    ForwardSubscriptionAccount = apps.get_model("forward_subscriptions", "ForwardSubscriptionAccount")
    ForwardTokenPricing = apps.get_model("forward_subscriptions", "ForwardTokenPricing")

    # پاکسازی اشتراک‌های تستی قدیمی و ریست هدیه برای دریافت ۳۵۰ توکن رایگان
    ForwardPlatformAccess.objects.all().delete()
    ForwardSubscriptionAccount.objects.all().update(
        trial_used_at=None,
        token_balance=0,
        total_tokens_earned=0,
        total_tokens_spent=0,
    )

    # غیرفعال‌سازی پلن‌های زمانی قدیمی
    ForwardSubscriptionPlan.objects.all().update(is_active=False, is_featured=False)

    # ایجاد تنظیمات پیش‌فرض نرخ مصرف توکن
    if not ForwardTokenPricing.objects.exists():
        ForwardTokenPricing.objects.create(
            text_cost=2,
            photo_cost=2,
            caption_extra_cost=2,
            sticker_gif_cost=3,
            media_under_5mb_cost=5,
            media_5_to_10mb_cost=7,
            media_10_to_20mb_cost=10,
            max_file_size_mb=20,
            hub_extra_cost=2,
            ai_watermark_extra_cost=5,
            free_gift_tokens=350,
        )

    packages = [
        {
            "code": "token-gift-350",
            "name": "هدیه شروع رایگان",
            "description": "۳۵۰ توکن رایگان بدون تاریخ انقضا برای تست کامل روی هر ۴ پیام‌رسان (یک‌بار برای هر کاربر).",
            "duration_days": 0,
            "tokens_amount": 350,
            "price_per_platform": 0,
            "discount_percent": 0,
            "is_trial": True,
            "is_active": True,
            "is_featured": False,
            "position": 0,
        },
        {
            "code": "token-starter-2k",
            "name": "بسته شروع",
            "description": "مناسب برای شروع و کانال‌های کم‌تعداد — هر توکن ۵۰ تومان، بدون تاریخ انقضا.",
            "duration_days": 0,
            "tokens_amount": 2000,
            "price_per_platform": 100000,
            "discount_percent": 0,
            "is_trial": False,
            "is_active": True,
            "is_featured": False,
            "position": 1,
        },
        {
            "code": "token-economic-5k",
            "name": "بسته اقتصادی",
            "description": "مناسب ادمین‌های فعال با ۱۰٪ تخفیف — هر توکن ۴۵ تومان، بدون تاریخ انقضا.",
            "duration_days": 0,
            "tokens_amount": 5000,
            "price_per_platform": 225000,
            "discount_percent": 10,
            "is_trial": False,
            "is_active": True,
            "is_featured": False,
            "position": 2,
        },
        {
            "code": "token-pro-10k",
            "name": "بسته حرفه‌ای",
            "description": "پرفروش‌ترین بسته با ۲۰٪ تخفیف — هر توکن ۴۰ تومان، مناسب ارسال روزانه چندپلتفرمی.",
            "duration_days": 0,
            "tokens_amount": 10000,
            "price_per_platform": 400000,
            "discount_percent": 20,
            "is_trial": False,
            "is_active": True,
            "is_featured": True,
            "position": 3,
        },
        {
            "code": "token-agency-25k",
            "name": "بسته تیمی و آژانسی",
            "description": "بیشترین صرفه‌جویی با ۳۰٪ تخفیف — هر توکن ۳۵ تومان، ایده‌آل برای هاب‌های تیمی و شبکه‌های کانال.",
            "duration_days": 0,
            "tokens_amount": 25000,
            "price_per_platform": 875000,
            "discount_percent": 30,
            "is_trial": False,
            "is_active": True,
            "is_featured": False,
            "position": 4,
        },
    ]

    for pkg in packages:
        code = pkg.pop("code")
        ForwardSubscriptionPlan.objects.update_or_create(code=code, defaults=pkg)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("forward_subscriptions", "0004_add_telegram_platform"),
    ]

    operations = [
        migrations.AddField(
            model_name="forwardsubscriptionplan",
            name="tokens_amount",
            field=models.PositiveIntegerField(
                default=0,
                help_text="تعداد توکنی که پس از خرید این بسته به کیف توکن کاربر اضافه می‌شود.",
                verbose_name="تعداد توکن بسته",
            ),
        ),
        migrations.AddField(
            model_name="forwardsubscriptionplan",
            name="discount_percent",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="درصد تخفیف نمایشی"),
        ),
        migrations.AlterField(
            model_name="forwardsubscriptionplan",
            name="price_per_platform",
            field=models.PositiveBigIntegerField(
                default=0,
                help_text="قیمت نهایی بسته توکن به تومان (برای هدیه رایگان مقدار ۰ ثبت شود).",
                verbose_name="قیمت بسته (تومان)",
            ),
        ),
        migrations.AddField(
            model_name="forwardsubscriptionaccount",
            name="token_balance",
            field=models.PositiveBigIntegerField(
                default=0,
                help_text="موجودی قابل ویرایش توکن کاربر (بدون تاریخ انقضا؛ تغییر مستقیم از ادمین در تاریخچه ثبت می‌شود).",
                verbose_name="موجودی توکن فعلی",
            ),
        ),
        migrations.AddField(
            model_name="forwardsubscriptionaccount",
            name="total_tokens_earned",
            field=models.PositiveBigIntegerField(default=0, verbose_name="مجموع توکن‌های دریافتی"),
        ),
        migrations.AddField(
            model_name="forwardsubscriptionaccount",
            name="total_tokens_spent",
            field=models.PositiveBigIntegerField(default=0, verbose_name="مجموع توکن‌های مصرف‌شده"),
        ),
        migrations.AddField(
            model_name="forwardsubscriptionorder",
            name="tokens_amount",
            field=models.PositiveIntegerField(default=0, verbose_name="تعداد توکن سفارش"),
        ),
        migrations.AlterField(
            model_name="forwardsubscriptionorder",
            name="duration_days",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="مدت اعمال‌شده (روز)"),
        ),
        migrations.CreateModel(
            name="ForwardTokenPricing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text_cost", models.PositiveSmallIntegerField(default=2, verbose_name="متن ساده (توکن)")),
                ("photo_cost", models.PositiveSmallIntegerField(default=2, verbose_name="عکس بدون کپشن (توکن)")),
                ("caption_extra_cost", models.PositiveSmallIntegerField(default=2, verbose_name="افزودن کپشن به رسانه (توکن)")),
                ("sticker_gif_cost", models.PositiveSmallIntegerField(default=3, verbose_name="استیکر و گیف (توکن)")),
                ("media_under_5mb_cost", models.PositiveSmallIntegerField(default=5, verbose_name="صوت/ویس/فایل/ویدیو زیر ۵ مگ (توکن)")),
                ("media_5_to_10mb_cost", models.PositiveSmallIntegerField(default=7, verbose_name="فایل/ویدیو ۵ تا ۱۰ مگ (توکن)")),
                ("media_10_to_20mb_cost", models.PositiveSmallIntegerField(default=10, verbose_name="فایل/ویدیو ۱۰ تا ۲۰ مگ (توکن)")),
                ("max_file_size_mb", models.PositiveSmallIntegerField(default=20, verbose_name="حداکثر حجم مجاز فایل (مگابایت)")),
                ("hub_extra_cost", models.PositiveSmallIntegerField(default=2, verbose_name="افزونه ارسال از هاب تیمی (توکن)")),
                ("ai_watermark_extra_cost", models.PositiveSmallIntegerField(default=5, verbose_name="افزونه حذف واترمارک هوش مصنوعی (توکن)")),
                ("free_gift_tokens", models.PositiveIntegerField(default=350, verbose_name="هدیه رایگان اولیه (توکن)")),
                ("updated_at", django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name="آخرین ویرایش")),
            ],
            options={
                "verbose_name": "تنظیمات نرخ مصرف توکن",
                "verbose_name_plural": "تنظیمات نرخ مصرف توکن",
            },
        ),
        migrations.CreateModel(
            name="ForwardTokenTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tx_type",
                    models.CharField(
                        choices=[
                            ("gift", "هدیه رایگان اولیه"),
                            ("purchase", "خرید بسته توکن"),
                            ("spend", "مصرف ارسال پیام"),
                            ("admin_adjust", "ویرایش دستی ادمین"),
                            ("refund", "بازگشت توکن"),
                        ],
                        db_index=True,
                        max_length=20,
                        verbose_name="نوع تراکنش",
                    ),
                ),
                ("amount", models.BigIntegerField(verbose_name="مقدار تغییر (مثبت/منفی)")),
                ("balance_after", models.PositiveBigIntegerField(default=0, verbose_name="موجودی پس از تراکنش")),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="شرح تراکنش")),
                ("broadcast_job_id", models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name="شناسه ارسال مرتبط")),
                ("created_at", django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name="زمان ثبت")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forward_token_transactions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "تراکنش توکن وین فوروارد",
                "verbose_name_plural": "تراکنش‌های توکن وین فوروارد",
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.RunPython(seed_token_system, reverse_code=noop),
    ]
