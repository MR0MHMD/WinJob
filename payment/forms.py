from django import forms
from django.utils.translation import gettext_lazy as _
from payment.models import BankAccount
from payment.utils.bank_detector import detect_bank_from_sheba


class WithdrawalRequestForm(forms.Form):
    """فرم ثبت درخواست تسویه"""

    amount = forms.CharField(
        label=_('مبلغ (تومان)'),
        widget=forms.TextInput(attrs={
            'class': 'form-control amount-input',
            'id': 'id_amount',
            'placeholder': _('مبلغ مورد نظر را وارد کنید'),
            'autocomplete': 'off',
            'inputmode': 'numeric',
        }),
        help_text=_('حداقل مبلغ قابل تسویه ۱۰۰,۰۰۰ تومان است.')
    )

    description = forms.CharField(
        label=_('توضیحات (اختیاری)'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'id': 'id_description',
            'rows': 3,
            'placeholder': _('توضیحات اضافی...')
        })
    )

    def clean_amount(self):
        amount_raw = self.cleaned_data.get('amount', '')
        amount_clean = amount_raw.replace(',', '').replace(' ', '').replace('٬', '').strip()

        if not amount_clean.isdigit():
            raise forms.ValidationError(_('لطفاً یک عدد معتبر وارد کنید.'))

        amount = int(amount_clean)

        if amount < 100000:
            raise forms.ValidationError(
                _('حداقل مبلغ قابل تسویه ۱۰۰,۰۰۰ تومان است.')
            )

        return amount


class BankAccountForm(forms.ModelForm):
    """فرم ثبت حساب بانکی"""

    class Meta:
        model = BankAccount
        fields = ['sheba_code', 'account_holder_name', 'is_default']
        widgets = {
            'sheba_code': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_sheba_code',
                'placeholder': 'xx xxxx xxxx xxxx xxxx xxxx xx',
                'dir': 'ltr',
                'autocomplete': 'off',
                'maxlength': '29',  # ۲۴ رقم + فاصله‌ها
                'inputmode': 'numeric',
            }),
            'account_holder_name': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_account_holder_name',
                'placeholder': 'نام و نام خانوادگی صاحب حساب',
                'autocomplete': 'off',
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_is_default',
            }),
        }
        labels = {
            'sheba_code': _('شماره شبا'),
            'account_holder_name': _('نام صاحب حساب'),
            'is_default': _('تنظیم به عنوان حساب پیش‌فرض'),
        }
        help_texts = {
            'sheba_code': _('شماره شبا را بدون IR وارد کنید (۲۴ رقم)'),
            'account_holder_name': _('نام صاحب حساب باید دقیقاً مطابق کارت بانکی باشد'),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # اگر اولین حساب کاربر است، چک‌باکس پیش‌فرض را به‌صورت پیش‌فرض تیک‌دار کن
        if self.user and not BankAccount.objects.filter(user=self.user).exists():
            self.fields['is_default'].initial = True

    def clean_sheba_code(self):
        sheba = self.cleaned_data.get('sheba_code', '')

        # پاکسازی
        sheba = sheba.replace(' ', '').replace('-', '').strip()
        if sheba.upper().startswith('IR'):
            sheba = sheba[2:]
        sheba = ''.join(filter(str.isdigit, sheba))

        if len(sheba) != 24:
            raise forms.ValidationError(
                _('شماره شبا باید دقیقاً ۲۴ رقم باشد (بدون IR).')
            )

        # تشخیص بانک - بررسی وجود دارد یا نه
        bank = detect_bank_from_sheba(sheba)
        if not bank:
            raise forms.ValidationError(
                _('کد بانک معتبر نیست. لطفاً شماره شبا را بررسی کنید.')
            )

        # جلوگیری از ثبت تکراری
        qs = BankAccount.objects.filter(user=self.user, sheba_code=sheba)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(
                _('این شماره شبا قبلاً برای شما ثبت شده است.')
            )

        return sheba

    def clean_account_holder_name(self):
        name = self.cleaned_data.get('account_holder_name', '').strip()
        if len(name) < 3:
            raise forms.ValidationError(
                _('نام صاحب حساب باید حداقل ۳ کاراکتر باشد.')
            )
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)

        # ✅ اصلاح: تشخیص بانک و اختصاص به فیلد bank (که ForeignKey هست)
        if instance.sheba_code:
            bank = detect_bank_from_sheba(instance.sheba_code)
            if bank:
                instance.bank = bank  # ✅ اختصاص آبجکت Bank به فیلد bank

        # تأیید خودکار
        instance.is_verified = True

        if commit:
            instance.save()
        return instance
