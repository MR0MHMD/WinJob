"""تنظیمات پیکربندی اپ اشتراک‌های وین فوروارد."""

from django.apps import AppConfig


class ForwardSubscriptionsConfig(AppConfig):
    """کلاس پیکربندی اپ اشتراک وین فوروارد با label یکتا برای جلوگیری از تداخل با وین‌دایرکت."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "product.forward.subscriptions"
    label = "forward_subscriptions"
    verbose_name = "اشتراک‌های وین فوروارد"
