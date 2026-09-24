"""Create the initial WinJob editorial categories without replacing existing data."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from blog.models import BlogCategory


CATEGORIES = (
    ('راهنمای تبلیغات', 'advertising-guide'),
    ('تبلیغات در پیام‌رسان‌ها', 'messenger-advertising'),
    ('انتخاب و ارزیابی رسانه', 'media-selection'),
    ('برنامه‌ریزی و مدیریت کمپین', 'campaign-management'),
    ('تولید محتوای تبلیغاتی', 'advertising-content'),
    ('تحلیل و سنجش عملکرد تبلیغات', 'advertising-analytics'),
    ('رشد و مدیریت کانال', 'channel-growth'),
    ('آموزش استفاده از وین‌جاب', 'winjob-guides'),
)


class Command(BaseCommand):
    help = 'Create initial blog categories; sequential reruns preserve existing categories.'

    def handle(self, *args, **options):
        results = []
        created_count = 0
        with transaction.atomic():
            for name, slug in CATEGORIES:
                matches = list(BlogCategory.objects.filter(
                    Q(name=name) | Q(slug=slug)
                ).order_by('pk'))
                if len(matches) > 1:
                    raise CommandError(
                        f'چند دسته‌بندی با نام یا اسلاگ «{name}» وجود دارد؛ '
                        'برای جلوگیری از انتخاب اشتباه، عملیات برگشت داده شد.'
                    )
                if matches:
                    category = matches[0]
                    created = False
                else:
                    category = BlogCategory.objects.create(name=name, slug=slug)
                    created_count += 1
                    created = True
                results.append((category, created))

        for category, created in results:
            status = 'ساخته شد' if created else 'از قبل موجود بود'
            self.stdout.write(f'{category.pk} | {category.name} | {category.slug} | {status}')
        self.stdout.write(self.style.SUCCESS(
            f'پایان: {created_count} دسته جدید؛ {len(results) - created_count} دسته موجود.'
        ))
