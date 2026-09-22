# -*- coding: utf-8 -*-
"""
python manage.py load_channels

بارگذاری کانال‌های «رسانستان» از فایل اکسل تعرفه‌ها به همراه نرخ خدمات هر کانال.

نکات مهم:
- کاربر ناشر (publisher) باید از قبل در دیتابیس موجود باشد؛ در غیر این صورت
  کامند با خطا متوقف می‌شود (به‌صورت پیش‌فرض هیچ کاربری ساخته نمی‌شود).
- اگر کانالی از قبل وجود داشته باشد و هیچ تغییری نکرده باشد، اصلاً ذخیره
  (save) نمی‌شود. اگر تغییری داشته باشد فقط همان فیلدهای تغییر یافته
  به‌روزرسانی می‌شوند.
- همین رفتار برای نرخ‌های هر کانال (ChannelServiceRate) هم رعایت می‌شود.
"""

from pathlib import Path

import openpyxl
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser
from core.models import AdType, Category, Platform, Province
from influencers.models import Channel, ChannelServiceRate, InfluencerProfile

DEFAULT_EXCEL_PATH = (
    settings.BASE_DIR / "influencers" / "management" / "data" / "resanestan_tariffs.xlsx"
)

# شماره موبایل کاربری که باید مالک (ناشر) همه‌ی این کانال‌ها باشد
PUBLISHER_PHONE_NUMBER = "09121331333"

# نام ستون «نام رسانستان» برای رسانستان‌های مرجع
REFERENCE_CHANNEL_NAME = "رسانستان مرجع"
REFERENCE_PROVINCE_NAME = "تهران"

# دسته‌بندی همه‌ی کانال‌ها
CATEGORY_SLUG = "news-provincial"

# مسیر تصاویر (در استاتیک اپ influencers)
PROVINCE_AVATAR_STATIC_PATH = "influencers/img/resanestan-province.png"
REFERENCE_AVATAR_STATIC_PATH = "influencers/img/resanestan.png"

# نگاشت نام پلتفرم در اکسل -> اسلاگ پلتفرم در دیتابیس
PLATFORM_SLUG_MAP = {
    "بله": "bale",
    "ایتا": "eitaa",
    "سروش": "sorush",  # نام کامل در دیتابیس «سروش پلاس» است
    "روبیکا": "rubika",
}

# نگاشت اسلاگ پلتفرم -> الگوی ساخت URL کانال از روی یوزرنیم (بدون @)
PLATFORM_URL_TEMPLATE = {
    "bale": "https://ble.ir/{username}",
    "eitaa": "https://eitaa.com/{username}",
    "sorush": "https://vitrin.splus.ir/{username}",
    "rubika": "https://rubika.ir/{username}",
}

# ستون‌های نرخ در اکسل -> پسوند اسلاگ AdType مربوطه
RATE_COLUMNS = [
    ("استوری (تومان)", "story"),
    ("پست شبانه (تومان)", "night-post"),
    ("پست ثابت (تومان)", "post"),
]

# ایندکس ستون‌ها در شیت (۰-ایندکس، مطابق فایل «تعرفه شهریور ۱۴۰۵»)
COL_ROW_NUM = 0
COL_CHANNEL_NAME = 1
COL_PLATFORM = 2
COL_CHANNEL_ID = 3
COL_FOLLOWERS = 4
COL_STORY_PRICE = 5
COL_NIGHT_POST_PRICE = 6
COL_POST_PRICE = 7

HEADER_ROW_MARKER = "ردیف"


class Command(BaseCommand):
    help = "بارگذاری کانال‌های رسانستان و نرخ خدمات‌شان از فایل اکسل تعرفه"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="مسیر فایل اکسل تعرفه‌ها (پیش‌فرض: influencers/management/data/resanestan_tariffs.xlsx)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="فقط نمایش تغییرات، بدون ذخیره در دیتابیس",
        )

    # ------------------------------------------------------------------ #
    # ورودی / خروجی کمکی
    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        excel_path = Path(options["file"]) if options["file"] else DEFAULT_EXCEL_PATH

        if not excel_path.exists():
            raise CommandError(f"فایل اکسل پیدا نشد: {excel_path}")

        try:
            publisher = CustomUser.objects.get(phone_number=PUBLISHER_PHONE_NUMBER)
        except CustomUser.DoesNotExist:
            raise CommandError(
                f"کاربری با شماره موبایل {PUBLISHER_PHONE_NUMBER} پیدا نشد. "
                "این کاربر باید از قبل در دیتابیس وجود داشته باشد."
            )

        influencer_profile, _ = InfluencerProfile.objects.get_or_create(user=publisher)

        try:
            category = Category.objects.get(slug=CATEGORY_SLUG)
        except Category.DoesNotExist:
            raise CommandError(
                f"دسته‌بندی با اسلاگ «{CATEGORY_SLUG}» پیدا نشد. "
                "ابتدا 'python manage.py load_categories' را اجرا کنید."
            )

        try:
            reference_province = Province.objects.get(name=REFERENCE_PROVINCE_NAME)
        except Province.DoesNotExist:
            raise CommandError(
                f"استان «{REFERENCE_PROVINCE_NAME}» پیدا نشد. "
                "ابتدا 'python manage.py load_province' را اجرا کنید."
            )

        platforms_cache = self._load_platforms()
        ad_types_cache = self._load_ad_types(platforms_cache)
        provinces_cache = {p.name: p for p in Province.objects.all()}

        rows = self._read_excel_rows(excel_path)

        stats = {
            "channels_created": 0,
            "channels_updated": 0,
            "channels_unchanged": 0,
            "rates_created": 0,
            "rates_updated": 0,
            "rates_unchanged": 0,
            "rows_skipped": 0,
        }

        with transaction.atomic():
            for row_number, row in rows:
                try:
                    self._process_row(
                        row=row,
                        influencer_profile=influencer_profile,
                        category=category,
                        reference_province=reference_province,
                        provinces_cache=provinces_cache,
                        platforms_cache=platforms_cache,
                        ad_types_cache=ad_types_cache,
                        stats=stats,
                    )
                except CommandError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    stats["rows_skipped"] += 1
                    self.stdout.write(
                        self.style.ERROR(f"ردیف {row_number}: خطا در پردازش -> {exc}")
                    )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("\n--dry-run فعال بود؛ تغییرات ذخیره نشدند.")
                )
                transaction.set_rollback(True)

        self._print_summary(stats)

    # ------------------------------------------------------------------ #
    # آماده‌سازی کش‌ها
    # ------------------------------------------------------------------ #

    def _load_platforms(self):
        cache = {}
        for excel_name, slug in PLATFORM_SLUG_MAP.items():
            try:
                cache[excel_name] = Platform.objects.get(slug=slug)
            except Platform.DoesNotExist:
                raise CommandError(
                    f"پلتفرم با اسلاگ «{slug}» (برای «{excel_name}») پیدا نشد. "
                    "ابتدا 'python manage.py load_platforms' را اجرا کنید."
                )
        return cache

    def _load_ad_types(self, platforms_cache):
        """
        cache[excel_platform_name][rate_suffix] -> AdType
        """
        cache = {}
        for excel_name, platform in platforms_cache.items():
            slug = PLATFORM_SLUG_MAP[excel_name]
            cache[excel_name] = {}
            for _, suffix in RATE_COLUMNS:
                ad_type_slug = f"{slug}-{suffix}"
                try:
                    cache[excel_name][suffix] = AdType.objects.get(
                        platform=platform, slug=ad_type_slug
                    )
                except AdType.DoesNotExist:
                    raise CommandError(
                        f"نوع تبلیغ با اسلاگ «{ad_type_slug}» پیدا نشد. "
                        "ابتدا 'python manage.py load_adtypes' را اجرا کنید."
                    )
        return cache

    # ------------------------------------------------------------------ #
    # خواندن اکسل
    # ------------------------------------------------------------------ #

    def _read_excel_rows(self, excel_path: Path):
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb.active

        rows = []
        header_found = False
        for row_number, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if not header_found:
                if row and row[COL_ROW_NUM] == HEADER_ROW_MARKER:
                    header_found = True
                continue

            if row is None or row[COL_CHANNEL_NAME] is None:
                continue

            rows.append((row_number, row))

        if not header_found:
            raise CommandError("ردیف هدر (ستون 'ردیف') در فایل اکسل پیدا نشد.")

        return rows

    # ------------------------------------------------------------------ #
    # پردازش هر ردیف
    # ------------------------------------------------------------------ #

    def _process_row(
        self,
        row,
        influencer_profile,
        category,
        reference_province,
        provinces_cache,
        platforms_cache,
        ad_types_cache,
        stats,
    ):
        channel_full_name = str(row[COL_CHANNEL_NAME]).strip()
        platform_name_fa = str(row[COL_PLATFORM]).strip()
        channel_id = str(row[COL_CHANNEL_ID]).strip()
        followers_count = int(row[COL_FOLLOWERS] or 0)

        if platform_name_fa not in platforms_cache:
            raise ValueError(f"پلتفرم ناشناخته در اکسل: «{platform_name_fa}»")

        platform = platforms_cache[platform_name_fa]

        is_reference = channel_full_name == REFERENCE_CHANNEL_NAME
        if is_reference:
            province = reference_province
            avatar_static_path = REFERENCE_AVATAR_STATIC_PATH
        else:
            province_name = channel_full_name.replace(REFERENCE_CHANNEL_NAME.split()[0] + " ", "", 1)
            # channel_full_name مثل "رسانستان آذربایجان شرقی" -> province_name = "آذربایجان شرقی"
            if province_name not in provinces_cache:
                raise ValueError(
                    f"استان «{province_name}» (برگرفته از «{channel_full_name}») در دیتابیس پیدا نشد."
                )
            province = provinces_cache[province_name]
            avatar_static_path = PROVINCE_AVATAR_STATIC_PATH

        username = channel_id.lstrip("@").strip()
        url_template = PLATFORM_URL_TEMPLATE[PLATFORM_SLUG_MAP[platform_name_fa]]
        channel_url = url_template.format(username=username)

        channel, created, updated = self._upsert_channel(
            influencer_profile=influencer_profile,
            platform=platform,
            channel_id=channel_id,
            channel_name=channel_full_name,
            province=province,
            category=category,
            url=channel_url,
            followers_count=followers_count,
            avatar_static_path=avatar_static_path,
        )

        if created:
            stats["channels_created"] += 1
            self.stdout.write(self.style.SUCCESS(f"+ کانال ساخته شد: {channel}"))
        elif updated:
            stats["channels_updated"] += 1
            self.stdout.write(self.style.WARNING(f"~ کانال به‌روزرسانی شد: {channel}"))
        else:
            stats["channels_unchanged"] += 1

        # نرخ‌های خدمات کانال
        rate_source_columns = {
            "story": row[COL_STORY_PRICE],
            "night-post": row[COL_NIGHT_POST_PRICE],
            "post": row[COL_POST_PRICE],
        }

        for suffix, price in rate_source_columns.items():
            ad_type = ad_types_cache[platform_name_fa][suffix]
            rate_created, rate_updated = self._upsert_rate(channel, ad_type, price)
            if rate_created:
                stats["rates_created"] += 1
            elif rate_updated:
                stats["rates_updated"] += 1
            else:
                stats["rates_unchanged"] += 1

    # ------------------------------------------------------------------ #
    # Upsert کانال (بدون دست‌زدن به رکورد در صورت عدم تغییر)
    # ------------------------------------------------------------------ #

    def _upsert_channel(
        self,
        influencer_profile,
        platform,
        channel_id,
        channel_name,
        province,
        category,
        url,
        followers_count,
        avatar_static_path,
    ):
        channel = Channel.objects.filter(
            influencer=influencer_profile,
            platform=platform,
            channel_id=channel_id,
        ).first()

        target_fields = {
            "channel_name": channel_name,
            "province": province,
            "category": category,
            "url": url,
            "followers_count": followers_count,
        }

        if channel is None:
            channel = Channel(
                influencer=influencer_profile,
                platform=platform,
                channel_id=channel_id,
                status="approved",
                is_active=True,
                **target_fields,
            )
            channel.save()
            self._set_avatar_if_needed(channel, avatar_static_path)
            return channel, True, False

        changed_fields = []
        for field_name, value in target_fields.items():
            if getattr(channel, field_name) != value:
                setattr(channel, field_name, value)
                changed_fields.append(field_name)

        avatar_changed = self._set_avatar_if_needed(channel, avatar_static_path, save=False)
        if avatar_changed:
            changed_fields.append("avatar")

        if changed_fields:
            channel.save(update_fields=changed_fields)
            return channel, False, True

        return channel, False, False

    def _set_avatar_if_needed(self, channel, static_path, save=True):
        """
        اگر آواتار کانال قبلاً همین فایل نبود، فایل استاتیک را در media کپی می‌کند.
        خروجی True یعنی آواتار تغییر کرد.
        """
        expected_name = Path(static_path).name

        current_name = Path(channel.avatar.name).name if channel.avatar else None
        if current_name == expected_name:
            return False

        absolute_path = finders.find(static_path)
        if not absolute_path:
            self.stdout.write(
                self.style.WARNING(
                    f"  تصویر استاتیک پیدا نشد: {static_path} (آواتار کانال «{channel}» تنظیم نشد)"
                )
            )
            return False

        with open(absolute_path, "rb") as f:
            channel.avatar.save(expected_name, ContentFile(f.read()), save=save)

        return True

    # ------------------------------------------------------------------ #
    # Upsert نرخ خدمت
    # ------------------------------------------------------------------ #

    def _upsert_rate(self, channel, ad_type, price):
        rate = ChannelServiceRate.objects.filter(channel=channel, ad_type=ad_type).first()

        if rate is None:
            ChannelServiceRate.objects.create(
                channel=channel, ad_type=ad_type, price=price, is_active=True
            )
            return True, False

        if int(rate.price) != int(price):
            rate.price = price
            rate.save(update_fields=["price"])
            return False, True

        return False, False

    # ------------------------------------------------------------------ #
    # خلاصه پایانی
    # ------------------------------------------------------------------ #

    def _print_summary(self, stats):
        self.stdout.write(self.style.SUCCESS("\n===== خلاصه =====\n"))
        self.stdout.write(f"کانال‌های ساخته‌شده:      {stats['channels_created']}")
        self.stdout.write(f"کانال‌های به‌روزرسانی‌شده: {stats['channels_updated']}")
        self.stdout.write(f"کانال‌های بدون تغییر:     {stats['channels_unchanged']}")
        self.stdout.write(f"نرخ‌های ساخته‌شده:        {stats['rates_created']}")
        self.stdout.write(f"نرخ‌های به‌روزرسانی‌شده:   {stats['rates_updated']}")
        self.stdout.write(f"نرخ‌های بدون تغییر:       {stats['rates_unchanged']}")
        if stats["rows_skipped"]:
            self.stdout.write(self.style.ERROR(f"ردیف‌های خطادار (نادیده گرفته شد): {stats['rows_skipped']}"))
