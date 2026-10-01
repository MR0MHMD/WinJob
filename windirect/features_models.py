"""مدل‌های دایرکت، ویترین و فرم‌های مکالمه‌ای وین دایرکت."""
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels


class PanelAsset(models.Model):
    """اطلاعات مشترک ابزارهای قابل استفاده در قوانین دایرکت."""
    connection = models.ForeignKey('InstagramConnection', on_delete=models.PROTECT, verbose_name=_("حساب اینستاگرام"))
    name = models.CharField(_("عنوان"), max_length=150)
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-pk']

    def __str__(self):
        return self.name


class Showcase(PanelAsset):
    """مجموعهٔ مرتب کارت‌ها برای پاسخ به دایرکت."""
    class Meta(PanelAsset.Meta):
        verbose_name = _("ویترین")
        verbose_name_plural = _("ویترین‌ها")


class ShowcaseCard(models.Model):
    """کارت تصویری ویترین با یک دکمهٔ پیوند."""
    showcase = models.ForeignKey(Showcase, on_delete=models.CASCADE, related_name='cards', verbose_name=_("ویترین"))
    title = models.CharField(_("عنوان کارت"), max_length=80)
    subtitle = models.CharField(_("توضیحات"), max_length=80, blank=True)
    image_url = models.URLField(_("پیوند تصویر"), max_length=1000, validators=[URLValidator(schemes=['https'])], help_text=_("نشانی عمومی HTTPS تصویر محصول"))
    button_title = models.CharField(_("عنوان دکمه"), max_length=20)
    button_url = models.URLField(_("پیوند دکمه"), max_length=1000, validators=[URLValidator(schemes=['https'])])
    position = models.PositiveSmallIntegerField(_("ترتیب نمایش"), default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])

    class Meta:
        verbose_name = _("کارت ویترین")
        verbose_name_plural = _("کارت‌های ویترین")
        ordering = ['position', 'pk']

    def __str__(self):
        return self.title


class ConversationForm(PanelAsset):
    """تعریف پرسش‌نامه‌ای که پاسخ‌ها را مرحله‌به‌مرحله دریافت می‌کند."""
    completion_text = models.TextField(_("پیام پایان فرم"), max_length=1000, default='پاسخ‌های شما با موفقیت ثبت شد. همکاران ما با شما تماس می‌گیرند.')
    cancel_keyword = models.CharField(_("کلمهٔ لغو فرم"), max_length=50, default='لغو')

    class Meta(PanelAsset.Meta):
        verbose_name = _("فرم مکالمه‌ای")
        verbose_name_plural = _("فرم‌های مکالمه‌ای")


class FormQuestion(models.Model):
    """پرسش و نوع اعتبارسنجی پاسخ در یک فرم."""
    class Kind(models.TextChoices):
        TEXT = 'text', _("متن")
        NUMBER = 'number', _("عدد صحیح")
        EMAIL = 'email', _("ایمیل")
        PHONE = 'phone', _("شماره همراه ایران")
        CHOICE = 'choice', _("انتخاب از گزینه‌ها")

    form = models.ForeignKey(ConversationForm, on_delete=models.CASCADE, related_name='questions', verbose_name=_("فرم"))
    prompt = models.CharField(_("متن سؤال"), max_length=500)
    kind = models.CharField(_("نوع پاسخ"), max_length=15, choices=Kind.choices, default=Kind.TEXT)
    options = models.TextField(_("گزینه‌ها"), blank=True, max_length=1000, help_text=_("فقط برای سؤال انتخابی؛ هر گزینه در یک خط (۲ تا ۱۰ گزینه)."))
    position = models.PositiveSmallIntegerField(_("ترتیب سؤال"), default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])

    class Meta:
        verbose_name = _("سؤال فرم")
        verbose_name_plural = _("سؤال‌های فرم")
        ordering = ['position', 'pk']

    def clean(self):
        """گزینه‌های پرسش انتخابی را پیش از ذخیره بررسی می‌کند."""
        super().clean()
        if self.kind == self.Kind.CHOICE:
            values = [v.strip() for v in self.options.splitlines() if v.strip()]
            if not 2 <= len(values) <= 10 or len(set(values)) != len(values):
                raise ValidationError({'options': '۲ تا ۱۰ گزینهٔ غیرتکراری وارد کنید.'})
            self.options = '\n'.join(values)

    def __str__(self):
        return self.prompt


class DirectRule(PanelAsset):
    """قانون پاسخ به پیام ورودی؛ اولین قانون منطبق اجرا می‌شود."""
    class ResponseType(models.TextChoices):
        TEXT = 'text', _("پاسخ متنی")
        SHOWCASE = 'showcase', _("نمایش ویترین")
        FORM = 'form', _("شروع فرم")

    keyword = models.CharField(_("کلمهٔ فعال‌کننده"), max_length=100)
    match_type = models.CharField(_("نوع تطبیق"), max_length=20, choices=[('exact', 'برابر'), ('contains', 'شامل')], default='exact')
    priority = models.PositiveSmallIntegerField(_("اولویت"), default=10, help_text=_("عدد کمتر زودتر بررسی می‌شود؛ در تساوی، قانون قدیمی‌تر."))
    response_type = models.CharField(_("نوع پاسخ"), max_length=15, choices=ResponseType.choices, default=ResponseType.TEXT)
    reply_text = models.TextField(_("متن پاسخ"), max_length=1000, blank=True)
    showcase = models.ForeignKey(Showcase, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("ویترین"))
    form = models.ForeignKey(ConversationForm, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("فرم"))

    class Meta(PanelAsset.Meta):
        verbose_name = _("قانون دایرکت")
        verbose_name_plural = _("قوانین دایرکت")
        ordering = ['priority', 'pk']
        indexes = [models.Index(fields=['connection', 'is_active', 'priority'], name='wd_direct_route_idx')]

    def clean(self):
        """پاسخ انتخابی و تعلق ابزار به همان حساب را کنترل می‌کند."""
        super().clean()
        if not self.keyword.strip():
            raise ValidationError({'keyword': 'کلمهٔ فعال‌کننده خالی است.'})
        if self.response_type == self.ResponseType.TEXT and not self.reply_text.strip():
            raise ValidationError({'reply_text': 'متن پاسخ را وارد کنید.'})
        for field, kind in [('showcase', 'showcase'), ('form', 'form')]:
            asset = getattr(self, field, None)
            if self.response_type == kind and asset is None:
                raise ValidationError({field: 'ابزار پاسخ را انتخاب کنید.'})
            if asset and asset.connection_id != self.connection_id:
                raise ValidationError({field: 'ابزار باید متعلق به همین حساب باشد.'})


class FormSubmission(models.Model):
    """نسخهٔ ثابت سؤال‌ها و جواب‌های یک مخاطب؛ مستقل از ویرایش بعدی فرم."""
    class Status(models.TextChoices):
        ACTIVE = 'active', _("در حال تکمیل")
        COMPLETED = 'completed', _("تکمیل‌شده")
        CANCELLED = 'cancelled', _("لغوشده")

    form = models.ForeignKey(ConversationForm, on_delete=models.PROTECT, related_name='submissions', verbose_name=_("فرم"))
    connection = models.ForeignKey('InstagramConnection', on_delete=models.PROTECT, verbose_name=_("حساب"))
    sender_id = models.CharField(_("شناسهٔ مخاطب آزمایشی"), max_length=100)
    status = models.CharField(_("وضعیت"), max_length=15, choices=Status.choices, default=Status.ACTIVE)
    schema = models.JSONField(_("نسخهٔ سؤال‌ها و تنظیمات"), default=dict)
    answers = models.JSONField(_("پاسخ‌ها"), default=list)
    created_at = jmodels.jDateTimeField(_("تاریخ شروع"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("آخرین پاسخ"), auto_now=True)
    completed_at = jmodels.jDateTimeField(_("تاریخ تکمیل"), null=True, blank=True)

    class Meta:
        verbose_name = _("پاسخ‌نامه")
        verbose_name_plural = _("پاسخ‌نامه‌ها")
        ordering = ['-pk']
        constraints = [models.UniqueConstraint(fields=['connection', 'sender_id'], condition=models.Q(status='active'), name='wd_one_active_form')]

    def __str__(self):
        return f'{self.form} — {self.sender_id}'


class DirectMessageEvent(models.Model):
    """پیام نمونه و خروجی ثبت‌شده برای جلوگیری از اجرای تکراری."""
    connection = models.ForeignKey('InstagramConnection', on_delete=models.PROTECT, verbose_name=_("حساب"))
    external_message_id = models.CharField(_("شناسهٔ پیام"), max_length=100)
    sender_id = models.CharField(_("شناسهٔ مخاطب آزمایشی"), max_length=100)
    text = models.TextField(_("متن ورودی"), max_length=2000)
    rule = models.ForeignKey(DirectRule, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("قانون اجراشده"))
    response = models.JSONField(_("خروجی شبیه‌سازی"), default=dict)
    created_at = jmodels.jDateTimeField(_("تاریخ دریافت"), auto_now_add=True)

    class Meta:
        verbose_name = _("پیام آزمایشی دایرکت")
        verbose_name_plural = _("پیام‌های آزمایشی دایرکت")
        ordering = ['-pk']
        constraints = [models.UniqueConstraint(fields=['connection', 'external_message_id'], name='wd_unique_direct_message')]

    def __str__(self):
        return self.external_message_id
