import getpass
import json
import math
import os
import re
import warnings
from difflib import SequenceMatcher
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Max
from django.urls import reverse

from blog.ai_image import ImageGenerationError, generate_featured_image
from blog.ai_writer import DEFAULT_MODEL, GenerationError, generate_article, generate_auto_article
from blog.models import BlogCategory, BlogTags, Post


def _normalize_title(value):
    value = (value or '').strip().lower()
    value = value.replace('ي', 'ی').replace('ك', 'ک')
    value = re.sub(r'[‌\s]+', ' ', value)
    value = re.sub(r'[^\w؀-ۿ ]+', '', value)
    return value.strip()


def _is_too_similar(new_title, old_titles, threshold=0.86):
    normalized = _normalize_title(new_title)
    if not normalized:
        return True
    for old in old_titles:
        old_normalized = _normalize_title(old)
        if not old_normalized:
            continue
        if normalized == old_normalized:
            return True
        if SequenceMatcher(None, normalized, old_normalized).ratio() >= threshold:
            return True
    return False



def _unique_post_slug(base_slug):
    candidate = base_slug
    counter = 2
    while Post.objects.filter(slug=candidate).exists():
        suffix = f'-{counter}'
        candidate = f'{base_slug[:180-len(suffix)]}{suffix}'
        counter += 1
    return candidate


def _select_balanced_category():
    categories = list(
        BlogCategory.objects.annotate(
            generated_post_count=Count('posts'),
            last_generated_post=Max('posts__created_at'),
        )
    )
    if not categories:
        raise CommandError(
            'هیچ دسته‌بندی بلاگی وجود ندارد. ابتدا python manage.py load_blog_categories را اجرا کنید.'
        )

    categories.sort(
        key=lambda category: (
            category.generated_post_count,
            category.last_generated_post is not None,
            category.last_generated_post,
            category.pk,
        )
    )
    return categories[0]


class Command(BaseCommand):
    help = (
        'Automatically choose category/topic, generate article + FLUX image, '
        'then save one DRAFT. Never publishes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--topic')
        parser.add_argument('--author-id', type=int)
        parser.add_argument('--category-id', type=int)
        parser.add_argument('--model', default=None)
        parser.add_argument('--no-image', action='store_true')
        parser.add_argument('--list-options', action='store_true', help='List active staff authors and categories; no API call.')

    def handle(self, *args, **options):
        users = get_user_model().objects.filter(is_active=True, is_staff=True)
        if options['list_options']:
            self.stdout.write('Authors (active staff):')
            for user in users.order_by('pk'):
                self.stdout.write(f'{user.pk}: {user.nickname or "Staff"}')
            self.stdout.write('Categories:')
            for category in BlogCategory.objects.order_by('pk'):
                self.stdout.write(f'{category.pk}: {category.name}')
            return

        author_id = options['author_id']
        if author_id is None:
            raw_author_id = os.environ.get('BLOG_DEFAULT_AUTHOR_ID', '').strip()
            if raw_author_id:
                try:
                    author_id = int(raw_author_id)
                except ValueError:
                    raise CommandError('BLOG_DEFAULT_AUTHOR_ID باید عدد صحیح باشد.') from None

        author = users.filter(pk=author_id).first() if author_id is not None else users.order_by('pk').first()
        if author is None:
            raise CommandError(
                'نویسنده فعال staff پیدا نشد. BLOG_DEFAULT_AUTHOR_ID را تنظیم کنید '
                'یا --author-id بدهید.'
            )

        if options['category_id'] is not None:
            category = BlogCategory.objects.filter(pk=options['category_id']).first()
            if category is None:
                raise CommandError('دسته‌بندی انتخابی پیدا نشد.')
        else:
            category = _select_balanced_category()

        key = os.environ.get('CHABOKAN_API_KEY', '').strip()
        if not key:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', getpass.GetPassWarning)
                    key = getpass.getpass('Chabokan API key (hidden): ')
            except (getpass.GetPassWarning, EOFError):
                raise CommandError('ورود مخفی کلید ممکن نیست. فرمان را در Terminal اجرا کنید یا CHABOKAN_API_KEY را تنظیم کنید.') from None
        model = options['model'] or os.environ.get('CHABOKAN_MODEL', DEFAULT_MODEL)

        recent_global_titles = list(Post.objects.order_by('-created_at').values_list('title', flat=True)[:30])
        recent_category_titles = list(
            Post.objects.filter(category=category).order_by('-created_at').values_list('title', flat=True)[:20]
        )

        topic_override = (options['topic'] or '').strip()
        self.stdout.write(f'Category selected: {category.pk} | {category.name}')
        self.stdout.write('Generating article with Chabokan (one request, no automatic retry)...')
        try:
            if topic_override:
                if not 5 <= len(topic_override) <= 500:
                    raise CommandError('موضوع --topic باید بین ۵ تا ۵۰۰ کاراکتر باشد.')
                article, usage = generate_article(topic_override, key, model)
            else:
                article, usage = generate_auto_article(
                    category.name,
                    recent_category_titles,
                    recent_global_titles,
                    key,
                    model,
                )
        except GenerationError as exc:
            raise CommandError(str(exc)) from None

        if _is_too_similar(article['title'], recent_global_titles):
            raise CommandError(
                'عنوان تولیدشده بیش از حد شبیه یکی از عنوان‌های اخیر است؛ '
                'برای جلوگیری از هزینه اضافی، درخواست دوم خودکار ارسال نشد.'
            )

        self.stdout.write('Usage (cost unit as reported by provider): ' + json.dumps(usage, ensure_ascii=False))
        image_bytes = None
        image_error = None
        image_enabled = (
            not options['no_image']
            and os.environ.get('BLOG_IMAGE_ENABLED', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}
        )
        if image_enabled:
            self.stdout.write('Generating featured image with Cloudflare FLUX...')
            try:
                image_bytes = generate_featured_image(
                    article['visual_concept'],
                    os.environ.get('CLOUDFLARE_ACCOUNT_ID', ''),
                    os.environ.get('CLOUDFLARE_API_TOKEN', ''),
                    os.environ.get('BLOG_IMAGE_STEPS', '6'),
                )
            except ImageGenerationError as exc:
                image_error = str(exc)
                self.stderr.write(self.style.WARNING('Featured image failed; article will still be saved as DRAFT: ' + image_error))

        with transaction.atomic():
            if Post.objects.filter(title=article['title']).exists():
                raise CommandError('مقاله‌ای با همین عنوان وجود دارد؛ پیش‌نویس جدید ذخیره نشد.')
            post = Post.objects.create(
                user=author,
                category=category,
                title=article['title'],
                content=article['content'],
                slug=_unique_post_slug(article['slug']),
                status=Post.Status.DRAFT,
                read_time=max(1, math.ceil(len(article['content'].split()) / 200)),
            )
            for name in article['tags']:
                tag = BlogTags.objects.filter(name=name).order_by('pk').first()
                if tag is None:
                    tag = BlogTags.objects.create(name=name, slug=uuid4().hex)
                post.tags.add(tag)
            if image_bytes:
                post.image.save(
                    f'ai-blog-{post.pk}-{uuid4().hex[:8]}.jpg',
                    ContentFile(image_bytes),
                    save=True,
                )
        self.stdout.write(self.style.SUCCESS(f'Draft saved: id={post.pk} | {post.title}'))
        self.stdout.write('Category: ' + category.name)
        self.stdout.write('Tags: ' + ', '.join(post.tags.values_list('name', flat=True)))
        self.stdout.write('Image: ' + (post.image.name if post.image else 'none'))
        if image_error:
            self.stdout.write('Image warning: ' + image_error)
        self.stdout.write('Admin: ' + reverse('admin:blog_post_change', args=[post.pk]))
