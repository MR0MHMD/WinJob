"""ورودی‌های خرید اشتراک؛ قیمت و مالکیت از سرور تعیین می‌شوند."""

from django import forms
from windirect.common.forms import style_fields


class SubscriptionPaymentForm(forms.Form):
    """روش پرداخت را از میان دو مسیر موجود پروژه می‌پذیرد."""

    method = forms.ChoiceField(
        label="روش پرداخت",
        choices=[("wallet", "کیف پول"), ("gateway", "زرین‌پال")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)