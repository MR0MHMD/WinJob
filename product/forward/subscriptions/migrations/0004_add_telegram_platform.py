from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forward_subscriptions", "0003_remove_soroush"),
    ]

    operations = [
        migrations.AlterField(
            model_name="forwardplatformaccess",
            name="platform_slug",
            field=models.CharField(
                choices=[("bale", "بله"), ("eitaa", "ایتا"), ("rubika", "روبیکا"), ("telegram", "تلگرام")],
                db_index=True,
                max_length=20,
                verbose_name="پلتفرم",
            ),
        ),
    ]
