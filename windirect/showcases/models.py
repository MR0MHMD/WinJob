from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from windirect.common.models import PanelAsset


class Showcase(PanelAsset):
    """مجموعهٔ مرتب کارت‌ها برای پاسخ به دایرکت."""

    class Meta(PanelAsset.Meta):
        db_table = "windirect_showcase"
        verbose_name = _("ویترین")
        verbose_name_plural = _("ویترین‌ها")


class ShowcaseCard(models.Model):
    """کارت تصویری ویترین با یک دکمهٔ پیوند."""

    showcase = models.ForeignKey(
        Showcase,
        on_delete=models.CASCADE,
        related_name="cards",
        verbose_name=_("ویترین"),
    )
    title = models.CharField(_("عنوان کارت"), max_length=80)
    subtitle = models.CharField(_("توضیحات"), max_length=80, blank=True)
    image_url = models.URLField(
        _("پیوند تصویر"),
        max_length=1000,
        validators=[URLValidator(schemes=["https"])],
        help_text=_("نشانی عمومی HTTPS تصویر محصول"),
    )
    button_title = models.CharField(_("عنوان دکمه"), max_length=20)
    button_url = models.URLField(
        _("پیوند دکمه"), max_length=1000, validators=[URLValidator(schemes=["https"])]
    )
    position = models.PositiveSmallIntegerField(
        _("ترتیب نمایش"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )

    class Meta:
        db_table = "windirect_showcasecard"
        verbose_name = _("کارت ویترین")
        verbose_name_plural = _("کارت‌های ویترین")
        ordering = ["position", "pk"]

    def __str__(self):
        return self.title
