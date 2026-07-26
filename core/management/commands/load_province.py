from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Province


class Command(BaseCommand):
    help = "Load 31 Iranian provinces with Fingilish slugs into Province model"

    PROVINCES = [
        ("آذربایجان شرقی", "azarbayjan-sharghi"),
        ("آذربایجان غربی", "azarbayjan-gharbi"),
        ("اردبیل", "ardabil"),
        ("اصفهان", "isfahan"),
        ("البرز", "alborz"),
        ("ایلام", "ilam"),
        ("بوشهر", "bushehr"),
        ("تهران", "tehran"),
        ("چهارمحال و بختیاری", "chaharmahal-bakhtiari"),
        ("خراسان جنوبی", "khorasan-jonubi"),
        ("خراسان رضوی", "khorasan-razavi"),
        ("خراسان شمالی", "khorasan-shomali"),
        ("خوزستان", "khuzestan"),
        ("زنجان", "zanjan"),
        ("سمنان", "semnan"),
        ("سیستان و بلوچستان", "sistan-baluchestan"),
        ("فارس", "fars"),
        ("قزوین", "qazvin"),
        ("قم", "qom"),
        ("کردستان", "kordestan"),
        ("کرمان", "kerman"),
        ("کرمانشاه", "kermanshah"),
        ("کهگیلویه و بویراحمد", "kohgiluyeh-boyerahmad"),
        ("گلستان", "golestan"),
        ("گیلان", "gilan"),
        ("لرستان", "lorestan"),
        ("مازندران", "mazandaran"),
        ("مرکزی", "markazi"),
        ("هرمزگان", "hormozgan"),
        ("همدان", "hamadan"),
        ("یزد", "yazd"),
    ]

    def handle(self, *args, **options):
        created = 0
        updated = 0
        unchanged = 0

        with transaction.atomic():
            for name, slug in self.PROVINCES:
                obj = Province.objects.filter(name=name).first()
                if obj is None:
                    # ایجاد رکورد جدید با اسلاگ مشخص
                    Province.objects.create(name=name, slug=slug)
                    self.stdout.write(self.style.SUCCESS(f"Created: {name} -> {slug}"))
                    created += 1
                else:
                    # اگر اسلاگ متفاوت است، به‌روزرسانی کن
                    if (obj.slug or "") != slug:
                        obj.slug = slug
                        obj.save()
                        self.stdout.write(self.style.SUCCESS(f"Updated slug: {name} -> {slug}"))
                        updated += 1
                    else:
                        self.stdout.write(self.style.WARNING(f"Exists (unchanged): {name} -> {slug}"))
                        unchanged += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created} created, {updated} updated, {unchanged} unchanged."
        ))
