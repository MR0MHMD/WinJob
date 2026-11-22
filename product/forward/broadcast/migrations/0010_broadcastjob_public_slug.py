# Generated manually for WinForward public report slug

import secrets
import string

from django.db import migrations, models


def _populate_public_slugs(apps, schema_editor):
    BroadcastJob = apps.get_model("broadcast", "BroadcastJob")
    alphabet = string.ascii_letters + string.digits
    used = set(
        BroadcastJob.objects.exclude(public_slug__isnull=True)
        .exclude(public_slug="")
        .values_list("public_slug", flat=True)
    )
    for job in BroadcastJob.objects.all().only("pk", "public_slug"):
        if job.public_slug:
            continue
        while True:
            slug = "".join(secrets.choice(alphabet) for _ in range(15))
            if slug not in used:
                used.add(slug)
                job.public_slug = slug
                job.save(update_fields=["public_slug"])
                break


class Migration(migrations.Migration):

    dependencies = [
        ("broadcast", "0009_broadcasthub"),
    ]

    operations = [
        migrations.AddField(
            model_name="broadcastjob",
            name="public_slug",
            field=models.CharField(
                blank=True,
                help_text="کد ۱۵ کاراکتری تصادفی برای مشاهده عمومی گزارش بدون نیاز به لاگین",
                max_length=15,
                null=True,
                verbose_name="شناسه عمومی گزارش",
            ),
        ),
        migrations.RunPython(_populate_public_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="broadcastjob",
            name="public_slug",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="کد ۱۵ کاراکتری تصادفی برای مشاهده عمومی گزارش بدون نیاز به لاگین",
                max_length=15,
                unique=True,
                verbose_name="شناسه عمومی گزارش",
            ),
        ),
    ]
