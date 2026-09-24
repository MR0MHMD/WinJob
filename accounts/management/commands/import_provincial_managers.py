"""Import the 30 provincial managers from the supplied PDF.

Install: accounts/management/commands/import_provincial_managers.py
Run: python manage.py import_provincial_managers
Preview: python manage.py import_provincial_managers --dry-run

Yazd is omitted because its PDF row has no name or phone number.
Wallets are created exclusively by the project's existing user-save signal.
Existing matching accounts are skipped; their passwords remain unchanged.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction


# Province name, nickname, phone number. Do not depend on database-specific IDs.
MANAGERS = (
    ('خراسان رضوی', 'حسین صاحب الزمانی', '09154291693'),
    ('سمنان', 'ابوالفضل علیزاده', '09190799170'),
    ('گلستان', 'محسن نادران', '09117024797'),
    ('خوزستان', 'میلاد امینی موحد', '09167031681'),
    ('چهارمحال و بختیاری', 'سجاد محمدی', '09139778634'),
    ('لرستان', 'مهدی سلیمی', '09165736716'),
    ('کرمانشاه', 'عزیزی', '09189217219'),
    ('البرز', 'محمود یوسفی', '09125671734'),
    ('مرکزی', 'هادی ساجدی فر', '09187578002'),
    ('قزوین', 'محسن واعظی', '09363520774'),
    ('قم', 'محمد جواد امینی', '09121519159'),
    ('آذربایجان شرقی', 'خسرو اکبری', '09144038018'),
    ('گیلان', 'رضانژاد', '09210307729'),
    ('هرمزگان', 'زندوی', '09171613919'),
    ('خراسان شمالی', 'حسین قلعه نوئی', '09155844368'),
    ('کهگیلویه و بویراحمد', 'علی شریفی', '09101401432'),
    ('خراسان جنوبی', 'بنی خزایی', '09179784759'),
    ('سیستان و بلوچستان', 'جواد حائری', '09104081807'),
    ('کرمان', 'محسن رضایی', '09363536369'),
    ('زنجان', 'بیگ دلی', '09192415069'),
    ('تهران', 'روشن', '09198330771'),
    ('اصفهان', 'پسندیده', '09133175829'),
    ('همدان', 'رضا ویسی', '09188141443'),
    ('ایلام', 'سجاد زارعی', '09139017456'),
    ('فارس', 'فرزاد چکامه', '09177078566'),
    ('بوشهر', 'سید دستغیبی', '09164694758'),
    ('آذربایجان غربی', 'علیرضا حیدری', '09149418097'),
    ('کردستان', 'عبدالله زاده', '09189835236'),
    ('اردبیل', 'قبادی', '09149540081'),
    ('مازندران', 'حسینی نیا', '09112163716'),

)


def normalize_province(value):
    return "".join(value.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").split())


class Command(BaseCommand):
    help = "ساخت ۳۰ مدیر استانی؛ کیف پول توسط سیگنال موجود پروژه ساخته می‌شود."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="بررسی اطلاعات بدون ذخیره کاربر یا اجرای سیگنال ذخیره",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        Province = User._meta.get_field("province").remote_field.model
        role = User.Role.REGIONAL_MANAGER
        pending = []
        skipped = 0
        errors = []

        try:
            with transaction.atomic():
                # Lock existing provinces to serialize concurrent command runs
                # on database backends that support row locks.
                provinces = {}
                for province in Province.objects.select_for_update().order_by("pk"):
                    provinces.setdefault(normalize_province(province.name), []).append(province)

                for province_name, nickname, phone in MANAGERS:
                    matches = provinces.get(normalize_province(province_name), [])
                    if len(matches) != 1:
                        errors.append(f"استان {province_name}: استان موجود نیست یا نام آن مبهم است.")
                        continue
                    province = matches[0]
                    existing = User.objects.filter(phone_number=phone).first()
                    other_managers = User.objects.filter(role=role, province=province)
                    if existing is not None:
                        other_managers = other_managers.exclude(pk=existing.pk)
                    if other_managers.exists():
                        errors.append(f"استان {province_name}: مدیر استانی دیگری دارد.")
                        continue
                    if existing is not None:
                        if (
                            existing.role == role
                            and existing.province_id == province.pk
                            and existing.nickname == nickname
                            and existing.is_active
                        ):
                            skipped += 1
                        else:
                            errors.append(f"شماره {phone}: حساب موجود با اطلاعات فهرست تطابق ندارد.")
                        continue
                    user = User(
                        phone_number=phone, nickname=nickname, province=province,
                        role=role, is_active=True, is_staff=False, is_superuser=False,
                    )
                    # Validate without saving or firing signals during preflight.
                    user.set_unusable_password()
                    try:
                        user.full_clean()
                    except ValidationError as exc:
                        errors.append(f"{province_name} / {nickname}: {exc}")
                    else:
                        pending.append(user)

                if errors:
                    raise CommandError("هیچ تغییری ثبت نشد:\n" + "\n".join(errors))

                if options["dry_run"]:
                    self.stdout.write(self.style.SUCCESS(
                        f"بررسی موفق: {len(pending)} کاربر آماده ساخت؛ {skipped} کاربر از قبل موجود. "
                        "هیچ تغییری ثبت نشد."
                    ))
                    return

                for user in pending:
                    user.set_password("12345678")
                    # Normal save runs model validation and post_save signals.
                    # Do not use bulk_create or create wallets here.
                    user.save()
        except (ValidationError, IntegrityError) as exc:
            raise CommandError(f"ساخت کاربران لغو شد و تغییرات دیتابیس برگشت داده شد: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(
            f"انجام شد: {len(pending)} کاربر ساخته شد؛ {skipped} کاربر موجود بدون تغییر باقی ماند."
        ))
        self.stdout.write("یزد: نام و شماره در PDF موجود نیست؛ حسابی ساخته نشد.")
