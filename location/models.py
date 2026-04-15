from django.db import models
from django.utils.text import slugify

from core.utils import generate_english_slug


class Province(models.Model):
    name = models.CharField("نام", max_length=100, unique=True)
    slug = models.SlugField("اسلاگ", max_length=120, unique=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "استان"
        verbose_name_plural = "استان‌ها"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True)
            slug = base_slug
            i = 1
            while Province.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class City(models.Model):
    province = models.ForeignKey(
        'Province',
        on_delete=models.CASCADE,
        related_name='cities',
        verbose_name='استان'
    )
    name = models.CharField('نام', max_length=150)
    slug = models.SlugField('اسلاگ', max_length=160, blank=True)

    class Meta:
        verbose_name = 'شهر'
        verbose_name_plural = 'شهر ها'
        ordering = ['name']
        unique_together = (('province', 'slug'),)

    def __str__(self):
        return f"{self.name} — {self.province.name}"


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_english_slug(self.name)
        super().save(*args, **kwargs)