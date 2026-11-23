# Generated manually for WinForward: replace ForwardTokenPricing DB model with Python constants.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("forward_subscriptions", "0005_token_system"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ForwardTokenPricing",
        ),
    ]
