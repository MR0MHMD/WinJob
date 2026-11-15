# Generated manually for WinForward subscription Invoice and Transaction types

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """افزودن نوع فاکتور winforward، ارتباط با سفارش اشتراک وین فوروارد و انواع تراکنش آن."""

    dependencies = [
        ("forward_subscriptions", "0002_seed_default_plans"),
        ("payment", "0017_alter_invoice_subscription_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="type",
            field=models.CharField(
                choices=[
                    ("campaign", "فاکتور کمپین"),
                    ("wallet", "فاکتور شارژ کیف پول"),
                    ("windirect", "فاکتور اشتراک وین دایرکت"),
                    ("winforward", "فاکتور اشتراک وین فوروارد"),
                    ("content_order", "فاکتور سفارش محتوا"),
                    ("market_order", "فاکتور سفارش وین مارکت"),
                ],
                default="campaign",
                max_length=20,
                verbose_name="نوع فاکتور",
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="forward_subscription_order",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invoice",
                to="forward_subscriptions.forwardsubscriptionorder",
                verbose_name="سفارش اشتراک وین فوروارد",
            ),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="type",
            field=models.CharField(
                choices=[
                    ("subscription_payment", "پرداخت اشتراک از کیف پول"),
                    ("subscription_gateway", "پرداخت اشتراک از درگاه"),
                    ("forward_subscription_payment", "پرداخت اشتراک وین فوروارد از کیف پول"),
                    ("forward_subscription_gateway", "پرداخت اشتراک وین فوروارد از درگاه"),
                    ("deposit", "شارژ کیف پول"),
                    ("withdraw", "برداشت از کیف پول"),
                    ("campaign_payment", "پرداخت کمپین"),
                    ("campaign_refund", "بازگشت وجه کمپین"),
                    ("gateway_payment", "پرداخت مستقیم از درگاه"),
                    ("gateway_refund", "بازگشت وجه از درگاه"),
                    ("influencer_payment", "پرداخت به ناشر"),
                    ("team_payment", "پرداخت به تیم تولید محتوا"),
                    ("content_order_payment", "پرداخت سفارش تولید محتوا"),
                    ("content_order_refund", "بازگشت وجه سفارش محتوا"),
                    ("influencer_withdrawal", "تسویه ناشر"),
                    ("content_team_withdrawal", "تسویه تیم محتوا"),
                    ("market_order_payment", "پرداخت سفارش وین مارکت"),
                    ("market_order_refund", "بازگشت وجه سفارش وین مارکت"),
                    ("market_order_supplier_payment", "واریز به کیف پول فروشنده"),
                ],
                max_length=40,
                verbose_name="نوع تراکنش",
            ),
        ),
    ]
