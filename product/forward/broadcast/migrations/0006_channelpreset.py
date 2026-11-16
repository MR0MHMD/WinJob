from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_jalali.db.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("broadcast", "0005_alter_broadcastmessage_content_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChannelPreset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "name",
                    models.CharField(
                        help_text="مثلاً: کانال‌های فروش، اخبار فوری، مشتریان VIP",
                        max_length=80,
                        verbose_name="نام پروفایل ارسال",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")),
                ("updated_at", django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")),
                (
                    "channels",
                    models.ManyToManyField(
                        blank=True,
                        related_name="presets",
                        to="broadcast.broadcastchannel",
                        verbose_name="کانال‌های عضو",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channel_presets",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "پروفایل ارسال",
                "verbose_name_plural": "پروفایل‌های ارسال",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "name"), name="unique_user_preset_name"),
                ],
            },
        ),
    ]
