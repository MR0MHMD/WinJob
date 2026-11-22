from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_jalali.db.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
        ("broadcast", "0008_alter_broadcastmessage_text"),
    ]

    operations = [
        migrations.CreateModel(
            name="BroadcastHub",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("group_chat_id", models.CharField(db_index=True, max_length=128, verbose_name="شناسه عددی گروه")),
                ("title", models.CharField(max_length=255, verbose_name="نام گروه / هاب")),
                (
                    "publish_mode",
                    models.CharField(
                        choices=[("all", "همه پیام‌های گروه"), ("hashtag", "فقط پیام‌های دارای #ارسال")],
                        default="all",
                        max_length=20,
                        verbose_name="حالت انتشار",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")),
                ("updated_at", django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")),
                (
                    "channels",
                    models.ManyToManyField(
                        blank=True,
                        related_name="hubs",
                        to="broadcast.broadcastchannel",
                        verbose_name="کانال‌های مقصد اضافی",
                    ),
                ),
                (
                    "platform",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="broadcast_hubs",
                        to="core.platform",
                        verbose_name="پلتفرم گروه",
                    ),
                ),
                (
                    "preset",
                    models.ForeignKey(
                        blank=True,
                        help_text="پروفایلی که پیام‌های این گروه خودکار به کانال‌های آن ارسال می‌شوند.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hubs",
                        to="broadcast.channelpreset",
                        verbose_name="پروفایل ارسال متصل",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="broadcast_hubs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="مالک هاب",
                    ),
                ),
            ],
            options={
                "verbose_name": "هاب ارسال گروهی",
                "verbose_name_plural": "هاب‌های ارسال گروهی",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="broadcasthub",
            constraint=models.UniqueConstraint(fields=("platform", "group_chat_id"), name="unique_hub_platform_group"),
        ),
    ]
