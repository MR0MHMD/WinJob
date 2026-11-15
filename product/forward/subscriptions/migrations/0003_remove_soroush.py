from django.db import migrations, models


def update_trial_plan_description(apps, schema_editor):
    """بروزرسانی توضیحات پلن آزمایشی ۷ روزه به ۳ پلتفرم (بله، ایتا و روبیکا)."""
    Plan = apps.get_model("forward_subscriptions", "ForwardSubscriptionPlan")
    Plan.objects.filter(code="trial_7d").update(
        description="دسترسی کامل و رایگان به هر ۳ پلتفرم (بله، ایتا و روبیکا) به مدت ۷ روز؛ قابل استفاده یک‌بار برای هر کاربر."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("forward_subscriptions", "0002_seed_default_plans"),
    ]

    operations = [
        migrations.AlterField(
            model_name="forwardplatformaccess",
            name="platform_slug",
            field=models.CharField(
                choices=[("bale", "بله"), ("eitaa", "ایتا"), ("rubika", "روبیکا")],
                db_index=True,
                max_length=20,
                verbose_name="پلتفرم",
            ),
        ),
        migrations.RunPython(update_trial_plan_description, migrations.RunPython.noop),
    ]
