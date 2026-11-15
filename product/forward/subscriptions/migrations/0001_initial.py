# Generated manually for product.forward.subscriptions

import django.db.models.deletion
import django.utils.timezone
import django_jalali.db.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """مایگریشن اولیه ایجاد جداول پلن، حساب اشتراک، دسترسی پلتفرم و سفارش وین فوروارد."""

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ForwardSubscriptionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=40, unique=True, verbose_name="کد پلن")),
                ("name", models.CharField(max_length=100, verbose_name="نام پلن")),
                ("description", models.TextField(blank=True, verbose_name="توضیحات")),
                ("duration_days", models.PositiveSmallIntegerField(default=30, verbose_name="مدت اعتبار (روز)")),
                (
                    "price_per_platform",
                    models.PositiveBigIntegerField(
                        default=0,
                        help_text="برای پلن رایگان ۷ روزه مقدار ۰ و برای پلن‌های پولی قیمت هر پلتفرم به تومان ثبت شود.",
                        verbose_name="قیمت هر پلتفرم (تومان)",
                    ),
                ),
                ("is_trial", models.BooleanField(default=False, verbose_name="دوره رایگان یک‌بارمصرف")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال برای فروش")),
                ("is_featured", models.BooleanField(default=False, verbose_name="پیشنهادی")),
                ("position", models.PositiveSmallIntegerField(default=1, verbose_name="ترتیب نمایش")),
                ("created_at", django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")),
                ("updated_at", django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")),
            ],
            options={
                "verbose_name": "پلن اشتراک وین فوروارد",
                "verbose_name_plural": "پلن‌های اشتراک وین فوروارد",
                "ordering": ["position", "duration_days", "pk"],
            },
        ),
        migrations.CreateModel(
            name="ForwardSubscriptionAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trial_used_at", django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name="زمان فعال‌سازی دوره رایگان")),
                ("first_paid_at", django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name="زمان اولین خرید پولی")),
                ("created_at", django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="forward_subscription_account",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "حساب اشتراک وین فوروارد",
                "verbose_name_plural": "حساب‌های اشتراک وین فوروارد",
                "ordering": ["-pk"],
            },
        ),
        migrations.CreateModel(
            name="ForwardSubscriptionOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "order_kind",
                    models.CharField(
                        choices=[("new", "خرید جدید"), ("renew", "تمدید اشتراک"), ("add_platform", "افزودن پلتفرم در میانه دوره")],
                        default="new",
                        max_length=20,
                        verbose_name="نوع سفارش",
                    ),
                ),
                (
                    "platforms",
                    models.JSONField(
                        default=list,
                        help_text="لیست slug پلتفرم‌های انتخاب‌شده (مثلاً ['bale', 'eitaa']).",
                        verbose_name="پلتفرم‌های انتخاب‌شده",
                    ),
                ),
                ("duration_days", models.PositiveSmallIntegerField(default=30, verbose_name="مدت اعمال‌شده (روز)")),
                ("price_per_platform", models.PositiveBigIntegerField(default=0, verbose_name="مبلغ واحد هر پلتفرم (تومان)")),
                ("subtotal_amount", models.PositiveBigIntegerField(default=0, verbose_name="جمع پایه (تومان)")),
                ("vat_amount", models.PositiveBigIntegerField(default=0, verbose_name="مالیات (تومان)")),
                ("total_amount", models.PositiveBigIntegerField(default=0, verbose_name="مبلغ قابل پرداخت (تومان)")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "در انتظار پرداخت"), ("paid", "پرداخت‌شده"), ("cancelled", "لغوشده")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                        verbose_name="وضعیت",
                    ),
                ),
                ("paid_at", django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name="زمان پرداخت")),
                ("created_at", django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to="forward_subscriptions.forwardsubscriptionplan",
                        verbose_name="پلن",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forward_subscription_orders",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "سفارش اشتراک وین فوروارد",
                "verbose_name_plural": "سفارش‌های اشتراک وین فوروارد",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ForwardPlatformAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "platform_slug",
                    models.CharField(
                        choices=[("bale", "بله"), ("eitaa", "ایتا"), ("rubika", "روبیکا"), ("soroush", "سروش‌پلاس")],
                        db_index=True,
                        max_length=20,
                        verbose_name="پلتفرم",
                    ),
                ),
                ("started_at", django_jalali.db.models.jDateTimeField(default=django.utils.timezone.now, verbose_name="شروع اشتراک")),
                ("expires_at", django_jalali.db.models.jDateTimeField(db_index=True, verbose_name="پایان اشتراک")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("updated_at", django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")),
                (
                    "plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="platform_accesses",
                        to="forward_subscriptions.forwardsubscriptionplan",
                        verbose_name="آخرین پلن",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forward_platform_accesses",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "دسترسی پلتفرم وین فوروارد",
                "verbose_name_plural": "دسترسی پلتفرم‌های وین فوروارد",
                "ordering": ["platform_slug"],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "platform_slug"), name="unique_forward_user_platform_access"),
                ],
            },
        ),
    ]
