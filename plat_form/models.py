from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Platform(models.Model):
    name = models.CharField(_("نام"), max_length=50)
    slug = models.SlugField(_("اسلاگ"), max_length=160)
    description = models.TextField(_('توضیحات'), max_length=750)
    logo = models.ImageField(_('لوگو'), upload_to="platform/logos", null=True, blank=True)
    is_active = models.BooleanField(_('فعال باشد؟'), default=True)

    class Meta:
        verbose_name = _('پلتفرم')
        verbose_name_plural = _('پلتفرم ها')
        ordering = ['-is_active', 'name']

    def get_absolute_url(self):
        return reverse('core:landing_page', kwargs={'slug': self.slug})

    def __str__(self):
        return self.name
