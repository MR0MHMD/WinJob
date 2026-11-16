from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("broadcast", "0007_broadcastchannel_avatar"),
    ]

    operations = [
        migrations.AlterField(
            model_name="broadcastmessage",
            name="text",
            field=models.TextField(
                blank=True,
                help_text="حداکثر ۴۰۹۶ کاراکتر — برای عکس/ویدیو/صوت به عنوان کپشن استفاده می‌شود",
                max_length=4096,
                verbose_name="متن پیام",
            ),
        ),
    ]
