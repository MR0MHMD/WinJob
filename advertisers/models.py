from django.utils.translation import gettext_lazy as _
from gamification.mixins import GamificationMixin
from django_jalali.db import models as jmodels
from django.db import models


class AdvertiserProfile(GamificationMixin, models.Model):
    user = models.OneToOneField("accounts.CustomUser", on_delete=models.CASCADE, related_name='advertiser_profile',
                                verbose_name=_('کاربر'))
    business_name = models.CharField(_('نام کسب‌وکار'), max_length=200)
    category = models.ForeignKey("core.Category", on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name=_('دسته‌بندی'))
    description = models.TextField(_('توضیحات کسب‌وکار'), blank=True)
    website = models.URLField(_('وبسایت'), blank=True)
    can_create_free_campaign = models.BooleanField(_('میتواند کمپین رایگان بسازد؟'), default=False)
    is_verified = models.BooleanField(_('تأیید شده'), default=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ ویرایش'), auto_now=True)

    class Meta:
        verbose_name = _('تبلیغ دهنده')
        verbose_name_plural = _('تبلیغ دهندگان')
        ordering = ['-created_at']

    def __str__(self): return self.business_name

    @property
    def wallet_balance(self):
        return self.user.wallet.balance

    def get_full_location(self): return self.user.province

    get_full_location.short_description = _('موقعیت جغرافیایی')

    def active_campaigns_count(self): return self.campaigns.filter(campaign_status='approved').count()

    active_campaigns_count.short_description = _('کمپین‌های فعال')
