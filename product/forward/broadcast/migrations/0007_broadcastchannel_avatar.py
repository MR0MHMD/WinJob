from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("broadcast", "0006_channelpreset"),
    ]

    operations = [
        migrations.AddField(
            model_name="broadcastchannel",
            name="avatar",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="broadcast/channels/avatars/",
                verbose_name="عکس پروفایل کانال",
            ),
        ),
    ]
