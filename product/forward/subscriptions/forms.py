"""فرم خرید بسته توکن وین فوروارد."""

from django import forms
from .models import ForwardSubscriptionPlan


class ForwardTokenPackageCheckoutForm(forms.Form):
    """فرم انتخاب بسته توکن برای ثبت سفارش یا دریافت هدیه رایگان."""

    plan_id = forms.ModelChoiceField(
        queryset=ForwardSubscriptionPlan.objects.filter(is_active=True),
        widget=forms.HiddenInput,
    )
