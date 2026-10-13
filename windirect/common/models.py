from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class PanelAsset(models.Model):
    """اطلاعات مشترک ابزارهای قابل استفاده در قوانین دایرکت."""

    connection = models.ForeignKey(
        "windirect_connections.InstagramConnection",
        on_delete=models.PROTECT,
        verbose_name=_("حساب اینستاگرام"),
    )
    name = models.CharField(_("عنوان"), max_length=150)
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-pk"]

    def __str__(self):
        return self.name
