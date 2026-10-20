# market/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from accounts.models import Address
from core.models import Province, City
from django.core.exceptions import ValidationError
from .models import Product, Category, ShippingMethod
from .utils.slug_utils import has_persian, clean_slug, generate_english_slug, ensure_unique_slug


class MultipleFileInput(forms.FileInput):
    """input type=file که از multiple پشتیبانی می‌کنه"""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """
    FileField که چند فایل رو قبول می‌کنه
    مقادیر cleaned_data یه لیست از فایل‌هاست
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data if d]
        else:
            result = [single_file_clean(data, initial)] if data else []
        return result

class AddressForm(forms.ModelForm):
    """فرم آدرس کاربر"""

    class Meta:
        model = Address
        fields = ['title', 'province', 'city', 'address', 'plaque', 'unit', 'postal_code']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثلاً: خانه، محل کار',
                'maxlength': 50,
            }),
            'province': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_province',
            }),
            'city': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_city',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'خیابان، کوچه، ...',
            }),
            'plaque': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثلاً: 12',
                'maxlength': 10,
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثلاً: 3',
                'maxlength': 10,
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '۱۰ رقم',
                'maxlength': 10,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['province'].queryset = Province.objects.all().order_by('name')
        self.fields['province'].empty_label = '— انتخاب استان —'
        self.fields['city'].empty_label = '— ابتدا استان را انتخاب کنید —'
        self.fields['title'].required = False
        self.fields['plaque'].required = False
        self.fields['unit'].required = False
        self.fields['postal_code'].required = False

        province_id = None
        if self.instance and self.instance.pk and self.instance.province_id:
            province_id = self.instance.province_id
        elif self.data.get('province'):
            try:
                province_id = int(self.data.get('province'))
            except (ValueError, TypeError):
                province_id = None

        if province_id:
            self.fields['city'].queryset = (
                City.objects.filter(province_id=province_id).order_by('name')
            )
        else:
            self.fields['city'].queryset = City.objects.none()

    def clean(self):
        cleaned = super().clean()
        province = cleaned.get('province')
        city = cleaned.get('city')
        if province and city and city.province_id != province.id:
            self.add_error('city', _('شهر انتخاب شده با استان مطابقت ندارد.'))
        return cleaned


# ============================================================
# Product Form
# ============================================================
class ProductForm(forms.ModelForm):
    """فرم ایجاد و ویرایش محصول توسط فروشنده"""

    # ---- تصاویر ----
    images = MultipleFileField(
        label=_("تصاویر محصول"),
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'd-none',
            'id': 'id_images',
            'accept': 'image/*',
        }),
    )

    main_image_index = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.HiddenInput(attrs={'id': 'id_main_image_index'}),
    )

    features_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_features_json'}),
    )

    # ---- قیمت‌ها (CharField با فرمت کاما) ----
    base_price = forms.CharField(
        label=_('قیمت پایه (تومان)'),
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-dark price-input',
            'placeholder': 'مثلاً: 500,000',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'id': 'id_base_price',
        }),
    )

    discount_price = forms.CharField(
        label=_('قیمت با تخفیف (تومان)'),
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-dark price-input',
            'placeholder': 'خالی بگذارید اگر تخفیف ندارد',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'id': 'id_discount_price',
        }),
    )

    stock = forms.CharField(
        label=_('موجودی انبار'),
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-dark price-input',
            'placeholder': 'مثلاً: 10',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'id': 'id_stock',
        }),
    )

    class Meta:
        model = Product
        fields = [
            'title', 'category',
            'short_description', 'description',
            'base_price', 'discount_price', 'stock',
            'shipping_methods',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-dark',
                'placeholder': 'مثلاً: جارو برقی شارژی',
                'maxlength': 200,
                'id': 'id_title',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select form-select-dark',
                'id': 'id_category',
            }),
            'short_description': forms.TextInput(attrs={
                'class': 'form-control form-control-dark',
                'placeholder': 'توضیح کوتاه برای کارت محصول (حداکثر ۳۰۰ کاراکتر)',
                'maxlength': 300,
                'id': 'id_short_description',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control form-control-dark',
                'rows': 6,
                'placeholder': 'توضیحات کامل محصول...',
                'id': 'id_description',
            }),
            'shipping_methods': forms.CheckboxSelectMultiple(attrs={
                'class': 'shipping-method-checkbox',
            }),
        }
        labels = {
            'title': _('عنوان محصول'),
            'category': _('دسته‌بندی'),
            'short_description': _('توضیح کوتاه'),
            'description': _('توضیحات کامل'),
            'shipping_methods': _('روش‌های ارسال'),
        }

    def __init__(self, *args, **kwargs):
        self.supplier = kwargs.pop('supplier', None)
        super().__init__(*args, **kwargs)

        # --- تنظیمات دسته‌بندی ---
        self.fields['category'].queryset = Category.objects.filter(is_active=True).order_by('order', 'name')
        self.fields['category'].empty_label = '— انتخاب دسته‌بندی —'

        # --- تنظیمات روش‌های ارسال ---
        self.fields['shipping_methods'].queryset = ShippingMethod.objects.filter(is_active=True).order_by('order', 'name')
        self.fields['shipping_methods'].required = False

    # ------------------------------------------------------
    # CLEAN: TITLE
    # ------------------------------------------------------
    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if len(title) < 3:
            raise ValidationError(_('عنوان محصول باید حداقل ۳ کاراکتر باشد.'))
        return title

    # ------------------------------------------------------
    # CLEAN: BASE PRICE
    # ------------------------------------------------------
    def clean_base_price(self):
        value = self.cleaned_data.get('base_price', '')
        value = str(value).replace(',', '').replace(' ', '').replace('٬', '').strip()

        if not value:
            raise ValidationError(_('قیمت پایه الزامی است.'))

        if not value.isdigit():
            raise ValidationError(_('قیمت پایه باید فقط شامل اعداد باشد.'))

        price = int(value)
        if price <= 0:
            raise ValidationError(_('قیمت پایه باید بزرگ‌تر از صفر باشد.'))

        return price

    # ------------------------------------------------------
    # CLEAN: DISCOUNT PRICE
    # ------------------------------------------------------
    def clean_discount_price(self):
        value = self.cleaned_data.get('discount_price', '')
        value = str(value).replace(',', '').replace(' ', '').replace('٬', '').strip()

        if not value:
            return None

        if not value.isdigit():
            raise ValidationError(_('قیمت با تخفیف باید فقط شامل اعداد باشد.'))

        price = int(value)
        if price <= 0:
            raise ValidationError(_('قیمت با تخفیف باید بزرگ‌تر از صفر باشد.'))

        return price

    # ------------------------------------------------------
    # CLEAN: STOCK
    # ------------------------------------------------------
    def clean_stock(self):
        value = self.cleaned_data.get('stock', '')
        value = str(value).replace(',', '').replace(' ', '').replace('٬', '').strip()

        if not value:
            return 0

        if not value.isdigit():
            raise ValidationError(_('موجودی باید فقط شامل اعداد باشد.'))

        return int(value)

    # ------------------------------------------------------
    # CLEAN: CROSS FIELDS
    # ------------------------------------------------------
    def clean(self):
        cleaned = super().clean()
        base = cleaned.get('base_price')
        discount = cleaned.get('discount_price')

        if discount is not None and base is not None:
            if discount >= base:
                self.add_error(
                    'discount_price',
                    _('قیمت با تخفیف باید کمتر از قیمت پایه باشد.')
                )

        return cleaned

    # ------------------------------------------------------
    # SAVE: auto-generate slug
    # ------------------------------------------------------
    def save(self, commit=True):
        instance = super().save(commit=False)

        # اگه slug خالیه (محصول جدید)، خودکار از title بساز
        if not instance.slug:
            slug = generate_english_slug(instance.title, fallback_prefix='product')
            instance.slug = ensure_unique_slug(slug, instance=instance)

        if commit:
            instance.save()
        return instance


# market/forms.py
import re
from django import forms
from market.models import GuestOrder


class GuestCheckoutForm(forms.ModelForm):
    """فرم صفحه چک‌اوت مهمان"""

    phone_number = forms.CharField(
        max_length=11, min_length=11, required=True,
        widget=forms.TextInput(attrs={
            'class': 'mk-form-input',
            'placeholder': '09xxxxxxxxx',
            'inputmode': 'numeric',
            'maxlength': '11',
            'dir': 'ltr',
        }),
        error_messages={
            'required': 'شماره تلفن الزامی است.',
            'min_length': 'شماره تلفن باید دقیقاً ۱۱ رقم باشد.',
            'max_length': 'شماره تلفن باید دقیقاً ۱۱ رقم باشد.',
        },
    )
    national_id = forms.CharField(
        max_length=10, min_length=10, required=True,
        widget=forms.TextInput(attrs={
            'class': 'mk-form-input',
            'placeholder': 'xxxxxxxxxx',
            'inputmode': 'numeric',
            'maxlength': '10',
            'dir': 'ltr',
        }),
        error_messages={
            'required': 'کد ملی الزامی است.',
            'min_length': 'کد ملی باید دقیقاً ۱۰ رقم باشد.',
            'max_length': 'کد ملی باید دقیقاً ۱۰ رقم باشد.',
        },
    )

    class Meta:
        model = GuestOrder
        fields = [
            'receiver_name', 'phone_number', 'national_id',
            'province', 'city', 'address', 'postal_code',
        ]
        widgets = {
            'receiver_name': forms.TextInput(attrs={'class': 'mk-form-input'}),
            'province': forms.Select(attrs={'class': 'mk-form-input'}),
            'city': forms.Select(attrs={'class': 'mk-form-input'}),
            'address': forms.Textarea(attrs={'class': 'mk-form-input', 'rows': 3}),
            'postal_code': forms.TextInput(attrs={
                'class': 'mk-form-input', 'inputmode': 'numeric', 'maxlength': '10', 'dir': 'ltr',
            }),
        }

    def clean_phone_number(self):
        v = self.cleaned_data['phone_number'].strip()
        if not re.fullmatch(r'\d{11}', v):
            raise forms.ValidationError('شماره تلفن باید فقط شامل ۱۱ رقم باشد.')
        if not v.startswith('09'):
            raise forms.ValidationError('شماره تلفن باید با ۰۹ شروع شود.')
        return v

    def clean_national_id(self):
        v = self.cleaned_data['national_id'].strip()
        if not re.fullmatch(r'\d{10}', v):
            raise forms.ValidationError('کد ملی باید فقط شامل ۱۰ رقم باشد.')
        # چک‌سام کد ملی ایران
        if len(set(v)) == 1:  # همه ارقام برابر مثل 1111111111
            raise forms.ValidationError('کد ملی معتبر نیست.')
        checksum = sum(int(v[i]) * (10 - i) for i in range(9)) % 11
        c = int(v[9])
        if not ((checksum < 2 and c == checksum) or (checksum >= 2 and c == 11 - checksum)):
            raise forms.ValidationError('کد ملی معتبر نیست.')
        return v


class GuestOTPForm(forms.Form):
    """فرم ورود رمز خرید پیامک‌شده"""
    purchase_password = forms.CharField(
        max_length=6, min_length=6, required=True,
        widget=forms.TextInput(attrs={
            'class': 'mk-form-input mk-otp-input',
            'placeholder': '------',
            'inputmode': 'numeric',
            'maxlength': '6',
            'dir': 'ltr',
            'autocomplete': 'one-time-code',
        }),
        error_messages={
            'required': 'رمز خرید الزامی است.',
            'min_length': 'رمز خرید ۶ رقمی است.',
            'max_length': 'رمز خرید ۶ رقمی است.',
        },
    )

    def clean_purchase_password(self):
        v = self.cleaned_data['purchase_password'].strip()
        if not re.fullmatch(r'\d{6}', v):
            raise forms.ValidationError('رمز خرید باید فقط شامل ۶ رقم باشد.')
        return v