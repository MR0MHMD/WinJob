from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='نام برند')),
                ('website', models.URLField(blank=True, verbose_name='وب‌سایت')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='social_brands', to=settings.AUTH_USER_MODEL, verbose_name='مالک')),
            ],
            options={'verbose_name': 'برند', 'verbose_name_plural': 'برندها'},
        ),
        migrations.CreateModel(
            name='SocialAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(default='instagram', max_length=30, verbose_name='پلتفرم')),
                ('username', models.CharField(max_length=100, verbose_name='نام کاربری')),
                ('external_id', models.CharField(blank=True, max_length=100, null=True, unique=True, verbose_name='شناسه حساب در پلتفرم')),
                ('status', models.CharField(choices=[('disconnected', 'متصل نیست'), ('connected', 'متصل'), ('reauth_required', 'نیازمند اتصال دوباره')], default='disconnected', max_length=20, verbose_name='وضعیت اتصال')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخرین ویرایش')),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_accounts', to='social_manager.brand', verbose_name='برند')),
            ],
            options={'verbose_name': 'حساب شبکه اجتماعی', 'verbose_name_plural': 'حساب‌های شبکه اجتماعی'},
        ),
        migrations.AddConstraint(
            model_name='socialaccount',
            constraint=models.UniqueConstraint(fields=('brand', 'platform', 'username'), name='social_account_brand_platform_username_uniq'),
        ),
    ]
