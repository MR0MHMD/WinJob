from django.db import migrations


def activate_telegram_platform(apps, schema_editor):
    """فعال‌سازی پلتفرم تلگرام در سیستم وین‌فوروارد."""
    Platform = apps.get_model("core", "Platform")
    tg = Platform.objects.filter(slug="telegram").first()
    if tg:
        if not tg.is_forward_active:
            tg.is_forward_active = True
            tg.save(update_fields=["is_forward_active"])
    else:
        Platform.objects.create(
            name="تلگرام",
            slug="telegram",
            is_forward_active=True,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_platform_is_forward_active"),
    ]

    operations = [
        migrations.RunPython(activate_telegram_platform, reverse_code=noop),
    ]
