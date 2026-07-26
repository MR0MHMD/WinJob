from django.core.management.base import BaseCommand
from core.models import Platform, ContentType
from django.db import transaction


class Command(BaseCommand):
    help = "ایجاد دو نوع محتوای اولیه برای همه پلتفرم‌ها"

    def handle(self, *args, **options):

        # گرفتن همه پلتفرم‌ها
        all_platforms = Platform.objects.all()

        if not all_platforms.exists():
            self.stdout.write(self.style.ERROR("❌ هیچ پلتفرمی در دیتابیس وجود ندارد! اول پلتفرم‌ها رو بساز."))
            return

        created_count = 0

        content_type1_data = {
            "name": "محتوای آماده دارم",
            "slug": "ready-content",
            "description": "شما محتوای آماده خود را آپلود کرده و همان مستقیما در تبلیغ شما قرار خواهد گرفت",
            "icon": "bi-journal-bookmark-fill",
            "is_active": True,
        }

        content_type2_data = {
            "name": "تولید توسط تیم تولید محتوا",
            "slug": "content-production-team",
            "description": "شما محتوای دلخواه خود را برای تیم تولید محتوا شرح میدهید و محتوای ساخته شده توسط تیم تولید محتوا پس از تایید شما در تبلیغ شما قرار خواهد گرفت",
            "icon": "bi-people-fill",
            "is_active": True,
        }

        with transaction.atomic():
            obj1, created1 = ContentType.objects.get_or_create(
                slug=content_type1_data["slug"],
                defaults=content_type1_data
            )

            if created1:
                obj1.platform.add(*all_platforms)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ ایجاد شد: {obj1.name}"))
                self.stdout.write(f"   🔗 پلتفرم‌های متصل: {', '.join([p.name for p in all_platforms])}")
            else:
                self.stdout.write(self.style.WARNING(f"⚠️  قبلاً وجود دارد: {obj1.name}"))
                # اگه وجود داشت ولی پلتفرم‌هاش کامل نبود، اضافه کن
                existing_platforms = set(obj1.platform.all())
                needed_platforms = set(all_platforms)
                missing_platforms = needed_platforms - existing_platforms
                if missing_platforms:
                    obj1.platform.add(*missing_platforms)
                    self.stdout.write(
                        f"   🔗 پلتفرم‌های جدید اضافه شد: {', '.join([p.name for p in missing_platforms])}")

            # ایجاد آبجت دوم
            obj2, created2 = ContentType.objects.get_or_create(
                slug=content_type2_data["slug"],
                defaults=content_type2_data
            )

            if created2:
                obj2.platform.add(*all_platforms)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ ایجاد شد: {obj2.name}"))
                self.stdout.write(f"   🔗 پلتفرم‌های متصل: {', '.join([p.name for p in all_platforms])}")
            else:
                self.stdout.write(self.style.WARNING(f"⚠️  قبلاً وجود دارد: {obj2.name}"))
                existing_platforms = set(obj2.platform.all())
                needed_platforms = set(all_platforms)
                missing_platforms = needed_platforms - existing_platforms
                if missing_platforms:
                    obj2.platform.add(*missing_platforms)
                    self.stdout.write(
                        f"   🔗 پلتفرم‌های جدید اضافه شد: {', '.join([p.name for p in missing_platforms])}")

        # نمایش نتیجه نهایی
        self.stdout.write("\n" + "=" * 50)
        if created_count == 2:
            self.stdout.write(self.style.SUCCESS(f"🎉 هر دو نوع محتوا با موفقیت ایجاد شدن!"))
        elif created_count > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ {created_count} نوع محتوای جدید ایجاد شد."))
        else:
            self.stdout.write(self.style.WARNING(f"ℹ️  هیچ نوع محتوای جدیدی ایجاد نشد (همه قبلاً وجود داشتند)"))

        # نمایش لیست نهایی
        all_content_types = ContentType.objects.all()
        self.stdout.write(f"\n📋 لیست انواع محتوا در دیتابیس ({all_content_types.count()}(مورد):")
        for ct in all_content_types:
            platform_names = ", ".join([p.name for p in ct.platform.all()])
            self.stdout.write(f"   • {ct.name} - slug: {ct.slug} - پلتفرم‌ها: {platform_names}")
