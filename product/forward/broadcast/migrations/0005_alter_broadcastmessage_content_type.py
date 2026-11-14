# Generated manually for audio and voice content types in BroadcastMessage

from django.db import migrations, models


class Migration(migrations.Migration):
    """افزودن گزینه‌های audio و voice به فیلد content_type در مدل BroadcastMessage."""

    dependencies = [
        ("broadcast", "0004_alter_broadcastmessage_content_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="broadcastmessage",
            name="content_type",
            field=models.CharField(
                choices=[
                    ("text", "متن"),
                    ("photo", "عکس"),
                    ("video", "ویدیو"),
                    ("audio", "فایل صوتی"),
                    ("voice", "پیام صوتی (ویس)"),
                    ("document", "فایل"),
                    ("animation", "گیف"),
                    ("sticker", "استیکر"),
                ],
                db_index=True,
                default="text",
                max_length=20,
                verbose_name="نوع محتوا",
            ),
        ),
    ]
