from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="InstagramConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=100)),
                ("instagram_user_id", models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ("status", models.CharField(choices=[("simulated", "آزمایشی"), ("disconnected", "قطع شده"), ("connected", "متصل")], default="simulated", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="windirect_connections", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Automation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("media_id", models.CharField(blank=True, help_text="خالی یعنی همهٔ پست‌های این حساب", max_length=100)),
                ("keyword", models.CharField(max_length=100)),
                ("match_type", models.CharField(choices=[("contains", "شامل"), ("exact", "برابر")], default="contains", max_length=10)),
                ("reply_text", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automations", to="windirect.instagramconnection")),
            ],
        ),
        migrations.CreateModel(
            name="CommentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_comment_id", models.CharField(max_length=100)),
                ("media_id", models.CharField(max_length=100)),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comment_events", to="windirect.instagramconnection")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("connection", "external_comment_id"), name="windirect_unique_comment")]},
        ),
        migrations.CreateModel(
            name="AutomationExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("simulated", "شبیه‌سازی شد"), ("sent", "ارسال شد"), ("failed", "ناموفق")], default="simulated", max_length=20)),
                ("response_text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("automation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="executions", to="windirect.automation")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="executions", to="windirect.commentevent")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("automation", "event"), name="windirect_unique_execution")]},
        ),
    ]
