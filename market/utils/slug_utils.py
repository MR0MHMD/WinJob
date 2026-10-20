# market/utils/slug_utils.py
"""
ابزارهای ساخت اسلاگ انگلیسی
"""
import re
import uuid
import logging

from django.utils.text import slugify

logger = logging.getLogger(__name__)

PERSIAN_PATTERN = re.compile(r'[\u0600-\u06FF]')
ASCII_SLUG_PATTERN = re.compile(r'[^a-z0-9\-_]')


def has_persian(text):
    """آیا متن شامل حروف فارسی/عربی است؟"""
    return bool(PERSIAN_PATTERN.search(text or ''))


def translate_to_english(text):
    """
    ترجمه‌ی متن فارسی به انگلیسی
    اگه کتابخانه نصب نبود یا خطا داد، رشته‌ی خالی برمی‌گردونه
    """
    if not text or not has_persian(text):
        return text or ''

    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='fa', target='en').translate(text) or ''
        return result.strip()
    except ImportError:
        logger.warning("deep-translator نصب نیست؛ ترجمه غیرفعال است.")
        return ''
    except Exception as e:
        logger.warning(f"خطا در ترجمه: {e}")
        return ''


def clean_slug(slug):
    """
    پاکسازی اسلاگ — فقط حروف کوچک انگلیسی، اعداد، خط تیره و آندرلاین
    """
    if not slug:
        return ''
    slug = slug.strip().lower()
    slug = ASCII_SLUG_PATTERN.sub('-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-_')
    return slug


def generate_english_slug(title, fallback_prefix='product'):
    """
    ساخت اسلاگ انگلیسی از عنوان فارسی
    1. اگه عنوان انگلیسی بود، فقط slugify
    2. اگه فارسی بود، ترجمه کن و بعد slugify
    3. اگه ترجمه شکست خورد، fallback به prefix-random
    """
    if not title:
        return f"{fallback_prefix}-{uuid.uuid4().hex[:8]}"

    if not has_persian(title):
        slug = clean_slug(slugify(title))
        if slug and len(slug) >= 2:
            return slug
        return f"{fallback_prefix}-{uuid.uuid4().hex[:8]}"

    english = translate_to_english(title)
    if english:
        slug = clean_slug(slugify(english))
        if slug and len(slug) >= 3:
            return slug

    return f"{fallback_prefix}-{uuid.uuid4().hex[:8]}"


def ensure_unique_slug(slug, instance=None, model=None):
    """
    اطمینان از یکتا بودن اسلاگ (با اضافه‌کردن -1، -2 و ...)
    """
    if model is None:
        from market.models import Product
        model = Product

    base_slug = slug
    qs = model.objects.filter(slug=slug)
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)

    counter = 1
    while qs.exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
        qs = model.objects.filter(slug=slug)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)

    return slug