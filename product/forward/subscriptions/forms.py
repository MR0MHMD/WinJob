"""فرم‌های مربوط به انتخاب پلن و پلتفرم‌های اشتراک وین فوروارد."""

from django import forms

from .models import FORWARD_PLATFORMS, ForwardSubscriptionOrder, ForwardSubscriptionPlan


class ForwardSubscriptionCheckoutForm(forms.Form):
    """فرم انتخاب پلن و پلتفرم‌ها برای خرید اشتراک جدید، تمدید یا افزودن پلتفرم در میانه دوره."""

    plan_id = forms.ModelChoiceField(
        queryset=ForwardSubscriptionPlan.objects.filter(is_active=True),
        label="پلن اشتراک",
    )
    order_kind = forms.ChoiceField(
        choices=ForwardSubscriptionOrder.OrderKind.choices,
        initial=ForwardSubscriptionOrder.OrderKind.NEW,
        required=False,
    )
    platforms = forms.MultipleChoiceField(
        choices=FORWARD_PLATFORMS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="پلتفرم‌های مورد نیاز",
    )
