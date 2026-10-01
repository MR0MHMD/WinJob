"""ورودی‌های خرید اشتراک؛ قیمت و مالکیت از سرور تعیین می‌شوند."""

from django import forms
from ..features_forms import style_fields


class SubscriptionOrderForm(forms.Form):
    """کد معرفی و نوع عملیات خرید را دریافت می‌کند."""

    referral_code = forms.CharField(
        label="کد معرف؛ اختیاری و فقط اولین خرید", max_length=40, required=False
    )
    kind = forms.ChoiceField(
        choices=[("purchase", "خرید یا تمدید"), ("upgrade", "ارتقا")],
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class SubscriptionPaymentForm(forms.Form):
    """روش پرداخت را از میان دو مسیر موجود پروژه می‌پذیرد."""

    method = forms.ChoiceField(
        label="روش پرداخت", choices=[("wallet", "کیف پول"), ("gateway", "زرین‌پال")]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
