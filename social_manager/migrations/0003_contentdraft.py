from django.db import migrations, models
import django.db.models.deletion
import django_jalali.db.models


class Migration(migrations.Migration):
    dependencies = [
        ('social_manager', '0002_jalali_timestamps'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContentDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان داخلی')),
                ('content_format', models.CharField(choices=[('post', 'پست'), ('carousel', 'اسلایدی'), ('reel', 'ریلز'), ('story', 'استوری')], max_length=12, verbose_name='قالب محتوا')),
                ('objective', models.CharField(blank=True, max_length=200, verbose_name='هدف محتوا')),
                ('idea', models.TextField(blank=True, verbose_name='شرح ایده')),
                ('hook', models.TextField(blank=True, verbose_name='جمله شروع')),
                ('caption', models.TextField(blank=True, verbose_name='کپشن')),
                ('call_to_action', models.TextField(blank=True, verbose_name='دعوت به اقدام')),
                ('hashtags', models.TextField(blank=True, verbose_name='هشتگ‌ها')),
                ('planned_for', django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name='زمان پیشنهادی انتشار')),
                ('status', models.CharField(choices=[('idea', 'ایده'), ('draft', 'پیش‌نویس'), ('review', 'در انتظار بررسی'), ('approved', 'تأیید شده')], default='idea', max_length=12, verbose_name='وضعیت')),
                ('created_at', django_jalali.db.models.jDateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('updated_at', django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name='آخرین ویرایش')),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='content_drafts', to='social_manager.brand', verbose_name='برند')),
            ],
            options={
                'verbose_name': 'پیش‌نویس شبکه اجتماعی',
                'verbose_name_plural': 'پیش‌نویس‌های شبکه اجتماعی',
                'ordering': ('planned_for', '-created_at'),
                'indexes': [models.Index(fields=['brand', 'status', 'planned_for'], name='social_mana_brand_i_878a34_idx')],
            },
        ),
    ]
