# Generated manually for WinForward: per-channel AI watermark & custom signature settings.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("broadcast", "0010_broadcastjob_public_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="broadcastchannel",
            name="watermark_mode",
            field=models.CharField(
                choices=[
                    ("off", "غیرفعال (ارسال بدون تغییر)"),
                    ("remove_append", "حذف واترمارک مبدا + افزودن امضای اختصاصی"),
                    ("rewrite", "بازسازی هوشمند واترمارک با اطلاعات این کانال"),
                ],
                db_index=True,
                default="off",
                max_length=20,
                verbose_name="حالت پردازش واترمارک هوش مصنوعی",
            ),
        ),
        migrations.AddField(
            model_name="broadcastchannel",
            name="custom_signature",
            field=models.TextField(
                blank=True,
                default="",
                help_text="متن امضا/واترمارک اختصاصی این کانال (در حالت حذف + امضای اختصاصی زیر پیام اضافه می‌شود)",
                max_length=1500,
                verbose_name="امضای اختصاصی کانال",
            ),
        ),
        migrations.AddField(
            model_name="broadcastchannel",
            name="watermark_display_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="اختیاری: آیدی یا لینک دلخواه برای جایگزینی در حالت بازسازی هوشمند (به‌ویژه برای کانال‌های خصوصی)",
                max_length=160,
                verbose_name="آیدی یا لینک نمایشی در واترمارک",
            ),
        ),
    ]
