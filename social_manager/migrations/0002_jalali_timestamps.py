from django.db import migrations
import django_jalali.db.models


class Migration(migrations.Migration):
    dependencies = [
        ('social_manager', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='brand',
            name='created_at',
            field=django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name='زمان ایجاد'),
        ),
        migrations.AlterField(
            model_name='socialaccount',
            name='created_at',
            field=django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name='زمان ایجاد'),
        ),
        migrations.AlterField(
            model_name='socialaccount',
            name='updated_at',
            field=django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name='آخرین ویرایش'),
        ),
    ]
