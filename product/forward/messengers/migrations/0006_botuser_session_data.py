# Generated manually for Rubika session storage in BotUser

from django.db import migrations, models


class Migration(migrations.Migration):
    """افزودن فیلد JSONField برای ذخیره اطلاعات نشست روبیکا در مدل BotUser."""

    dependencies = [
        ("messengers", "0005_remove_botuser_session_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="botuser",
            name="session_data",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="ذخیره اطلاعات نشست برای پلتفرم‌هایی مثل روبیکا (auth و private_key).",
                verbose_name="اطلاعات نشست",
            ),
        ),
    ]
