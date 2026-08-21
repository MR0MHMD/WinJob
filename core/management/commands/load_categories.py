from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Category


class Command(BaseCommand):
    help = 'ایجاد دسته‌بندی‌های جامع برای تبلیغ دهنده و اینفلوئنسر'

    CATEGORIES_DATA = [
        # 1. ورزشی
        {"slug": "sports", "name": "ورزشی", "icon": "bi-trophy",
         "description": "ورزش‌های حرفه‌ای، تناسب اندام و فعالیت‌های ورزشی"},

        # 2. مذهبی
        {"slug": "religious", "name": "مذهبی", "icon": "bi-building",
         "description": "محتوای مذهبی، معنوی و مراسم‌های مذهبی"},

        # 3. هنر ادبیات و سینما
        {"slug": "art-literature-cinema", "name": "هنر، ادبیات و سینما", "icon": "bi-palette",
         "description": "نقد فیلم، کتاب، شعر، موسیقی و آثار هنری"},

        # 4. توسعه فردی و انگیزشی
        {"slug": "self-development", "name": "توسعه فردی و انگیزشی", "icon": "bi-graph-up",
         "description": "مهارت‌های زندگی، موفقیت و رشد شخصی"},

        # 5. سفر
        {"slug": "travel", "name": "سفر", "icon": "bi-airplane",
         "description": "تورهای گردشگری،旅‌نامه و جاهای دیدنی"},

        # 6. سرگرمی و اوقات فراغت
        {"slug": "entertainment", "name": "سرگرمی و اوقات فراغت", "icon": "bi-emoji-smile",
         "description": "تفریحات، بازی‌ها و فعالیت‌های سرگرم‌کننده"},

        # 7. مد و استایل
        {"slug": "fashion-style", "name": "مد و استایل", "icon": "bi-scissors",
         "description": "لباس، اکسسوری، آرایش و استایل شخصی"},

        # 8. خانواده و سبک زندگی
        {"slug": "family-lifestyle", "name": "خانواده و سبک زندگی", "icon": "bi-house-heart",
         "description": "روابط خانوادگی، تربیت فرزند و زندگی روزمره"},

        # 9. تکنولوژی و بازی
        {"slug": "tech-gaming", "name": "تکنولوژی و بازی", "icon": "bi-joystick",
         "description": "گجت‌ها، نرم‌افزارها، بازی‌های ویدیویی و تکنولوژی"},

        # 10. اخبار و استانی
        {"slug": "news-provincial", "name": "اخبار و استانی", "icon": "bi-newspaper",
         "description": "رویدادهای جاری، خبرهای محلی و استانی"},

        # 11. کسب و کار و مارکتینگ
        {"slug": "business-marketing", "name": "کسب و کار و مارکتینگ", "icon": "bi-briefcase",
         "description": "استارتاپ‌ها، بازاریابی، فروش و کارآفرینی"},

        # 12. وسایل نقلیه
        {"slug": "vehicles", "name": "وسایل نقلیه", "icon": "bi-car-front",
         "description": "خودرو، موتور، دوچرخه و صنعت حمل و نقل"},

        # 13. سیاسی و حقوقی
        {"slug": "political-legal", "name": "سیاسی و حقوقی", "icon": "bi-gavel",
         "description": "تحولات سیاسی، قوانین و مسائل حقوقی"},

        # 14. حیوانات خانگی
        {"slug": "pets", "name": "حیوانات خانگی", "icon": "bi-heart",
         "description": "نگهداری حیوانات، تربیت و مراقبت از پت‌ها"},

        # 15. فروشگاه و آنلاین شاپ
        {"slug": "online-shop", "name": "فروشگاه و آنلاین شاپ", "icon": "bi-bag",
         "description": "تخفیف‌ها، معرفی محصول و فروش اینترنتی"},

        # 16. عمومی
        {"slug": "general", "name": "عمومی", "icon": "bi-globe",
         "description": "محتوای متنوع و همه‌پسند بدون موضوع خاص"},

        # 17. آموزشی و دانشجویی
        {"slug": "educational", "name": "آموزشی و دانشجویی", "icon": "bi-book",
         "description": "دروس تخصصی، کنکور و محتوای علمی"},

        # 18. غذا و نوشیدنی
        {"slug": "food-drink", "name": "غذا و نوشیدنی", "icon": "bi-cup-straw",
         "description": "دستور پخت، رستوران‌ها و نقد غذا"},

        # 19. خانه و ساختمان
        {"slug": "home-construction", "name": "خانه و ساختمان", "icon": "bi-building",
         "description": "دکوراسیون، بازسازی و معماری داخلی"},

        # 20. سلامتی و تندرستی
        {"slug": "health-wellness", "name": "سلامتی و تندرستی", "icon": "bi-activity",
         "description": "تناسب اندام، رژیم غذایی و سلامت روان"},
    ]

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 شروع ایجاد دسته‌بندی‌ها...'))

        # پاک کردن داده‌های قبلی
        deleted_count, _ = Category.objects.all().delete()
        self.stdout.write(f'   🗑️  {deleted_count} دسته قبلی پاک شد')

        created_count = 0

        for category_data in self.CATEGORIES_DATA:
            category = Category.objects.create(
                name=category_data['name'],
                slug=category_data['slug'],
                description=category_data['description'],
                icon=category_data['icon'],
                order=0,
                is_active=True
            )
            created_count += 1
            self.stdout.write(f'   ✅ {category.name} - {category.slug}')

        self.stdout.write(self.style.SUCCESS(f'\n✨ تمام! {created_count} دسته‌بندی ایجاد شد'))
        self.stdout.write(self.style.SUCCESS('🎯 همه دسته‌بندی‌ها فعال و آماده استفاده هستند!'))
