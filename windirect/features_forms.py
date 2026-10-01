"""فرم‌های پنل ابزارهای وین دایرکت با دسترسی محدود به مالک."""
from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from .models import (InstagramConnection, DirectRule, Showcase, ShowcaseCard, ConversationForm, FormQuestion)


def style_fields(form):
    """کلاس‌های مشترک تم سایت را به ورودی‌ها اضافه می‌کند."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs['class'] = 'form-check-input'
        elif isinstance(widget, forms.Select):
            widget.attrs['class'] = 'form-select bg-dark text-light border-light'
        else:
            widget.attrs['class'] = 'form-control bg-dark text-light border-light'
        if isinstance(widget, forms.Textarea):
            widget.attrs['rows'] = 3


class AssetForm(forms.ModelForm):
    """فقط حساب‌های آزمایشی مالک را در دسترس فرم قرار می‌دهد."""
    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['connection'].queryset = InstagramConnection.objects.filter(owner=owner, status='simulated')
        if self.instance.pk:
            self.fields['connection'].disabled = True
        style_fields(self)


class ShowcaseForm(AssetForm):
    """تنظیمات عمومی ویترین."""
    class Meta:
        model = Showcase
        fields = ['connection', 'name', 'is_active']


class ConversationFormEditor(AssetForm):
    """تنظیمات پرسش‌نامه و پیام پایان آن."""
    class Meta:
        model = ConversationForm
        fields = ['connection', 'name', 'completion_text', 'cancel_keyword', 'is_active']


class DirectRuleForm(AssetForm):
    """تعریف محرک و پاسخ با جلوگیری از انتخاب ابزار کاربر دیگر."""
    class Meta:
        model = DirectRule
        fields = ['connection', 'name', 'keyword', 'match_type', 'priority', 'response_type', 'reply_text', 'showcase', 'form', 'is_active']

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, owner=owner, **kwargs)
        self.fields['showcase'].queryset = Showcase.objects.filter(connection__owner=owner, is_active=True)
        self.fields['form'].queryset = ConversationForm.objects.filter(connection__owner=owner, is_active=True)
        self.fields['reply_text'].help_text = 'برای پاسخ متنی تکمیل کنید. ویترین یا فرم را فقط برای همان نوع پاسخ انتخاب کنید.'

    def clean(self):
        """فقط ابزار مربوط به نوع پاسخ انتخاب‌شده را ذخیره می‌کند."""
        data = super().clean()
        if data.get('response_type') != 'showcase':
            data['showcase'] = None
        if data.get('response_type') != 'form':
            data['form'] = None
        if data.get('response_type') != 'text':
            data['reply_text'] = ''
        from .subscriptions.access import require_feature
        connection = data.get('connection')
        response_type = data.get('response_type')
        if connection and response_type in ('form', 'showcase'):
            require_feature(connection.owner, 'forms' if response_type == 'form' else 'showcases')
        return data


class StyledChildForm(forms.ModelForm):
    """ورودی‌های کارت و سؤال را با تم سایت هماهنگ می‌کند."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class OrderedChildren(BaseInlineFormSet):
    """ترتیب‌های تکراری را رد می‌کند تا جریان سؤال و کارت روشن باشد."""
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        allowed_ids = set(self.get_queryset().values_list('pk', flat=True))
        for form in self.forms:
            child = form.cleaned_data.get('id')
            if child is not None and child.pk not in allowed_ids:
                raise ValidationError('یکی از موارد ارسالی متعلق به این ابزار نیست. صفحه را دوباره باز کنید.')
        positions = [f.cleaned_data.get('position') for f in self.forms
                     if f.cleaned_data and not f.cleaned_data.get('DELETE')]
        if len(set(positions)) != len(positions):
            raise ValidationError('ترتیب‌ها باید غیرتکراری باشند.')


CardFormSet = inlineformset_factory(Showcase, ShowcaseCard, form=StyledChildForm,
    formset=OrderedChildren, fields=['title', 'subtitle', 'image_url', 'button_title', 'button_url', 'position'],
    extra=0, min_num=1, max_num=10, validate_min=True, validate_max=True, absolute_max=20, can_delete=True)
QuestionFormSet = inlineformset_factory(ConversationForm, FormQuestion, form=StyledChildForm,
    formset=OrderedChildren, fields=['prompt', 'kind', 'options', 'position'],
    extra=0, min_num=1, max_num=20, validate_min=True, validate_max=True, absolute_max=30, can_delete=True)


class DirectSimulationForm(forms.Form):
    """پیام ورودی برای یک مخاطب ثابت در شبیه‌ساز مکالمه."""
    connection = forms.ModelChoiceField(label='حساب آزمایشی', queryset=InstagramConnection.objects.none())
    sender_id = forms.CharField(label='شناسهٔ مخاطب آزمایشی', max_length=100, initial='visitor-1', help_text='برای ادامهٔ فرم، همین حساب و شناسه را نگه دارید.')
    text = forms.CharField(label='پیام مخاطب', max_length=2000, widget=forms.Textarea)
    message_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['connection'].queryset = InstagramConnection.objects.filter(owner=owner, status='simulated')
        style_fields(self)
