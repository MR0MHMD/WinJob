from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps  # ← این رو اضافه کن


class Command(BaseCommand):
    help = 'تنظیم گروه و دسترسی‌های مدیران استانی'

    def handle(self, *args, **options):
        # ایجاد گروه مدیران استانی
        group, created = Group.objects.get_or_create(name='مدیران استانی')

        if created:
            self.stdout.write(self.style.SUCCESS('✅ گروه مدیران استانی ایجاد شد'))
        else:
            self.stdout.write('📋 گروه مدیران استانی از قبل وجود داشت')

        models_list = [
            # اینفلوئنسرها
            ('influencers', 'InfluencerChannel'),
            ('influencers', 'InfluencerProfile'),
            ('influencers', 'InfluencerServiceRate'),

            # تبلیغ‌دهندگان
            ('advertisers', 'AdvertiserProfile'),

            # کمپین‌ها
            ('campaigns', 'Campaign'),
            ('campaigns', 'CampaignInvoice'),
            ('campaigns', 'Payment'),

            # تیم محتوا (اختیاری)
            # ('content_team', 'ContentTeam'),
            # ('content_team', 'ContentTeamMember'),
            # ('content_team', 'ContentOrder'),
        ]

        total_permissions = 0

        for app_label, model_name in models_list:
            try:
                # دریافت مدل به صورت داینامیک
                model = apps.get_model(app_label, model_name)
                content_type = ContentType.objects.get_for_model(model)
                permissions = Permission.objects.filter(content_type=content_type)

                for perm in permissions:
                    group.permissions.add(perm)
                    total_permissions += 1
                    self.stdout.write(f'  ✓ {app_label}.{model_name}: {perm.name}')

                self.stdout.write(self.style.SUCCESS(f'  → {len(permissions)} دسترسی برای {model_name} اضافه شد'))

            except LookupError:
                self.stdout.write(self.style.WARNING(f'  ⚠ مدل {app_label}.{model_name} پیدا نشد، رد شد'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ خطا برای {model_name}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\n✅ تنظیمات با موفقیت انجام شد - {total_permissions} دسترسی اضافه شد'))