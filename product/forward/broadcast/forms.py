"""فرم‌های مربوط به وین فوروارد."""

from django import forms
from product.forward.broadcast.models import BroadcastMessage, BroadcastChannel


class BroadcastSendForm(forms.ModelForm):
    """فرم ارسال پیام جدید به چند کانال."""

    channels = forms.ModelMultipleChoiceField(queryset=BroadcastChannel.objects.none(), widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}), label="کانال‌های مقصد", required=True,)

    class Meta:
        """تنظیمات متادیتای فرم."""
        model = BroadcastMessage
        fields = ["content_type", "text", "file"]
        widgets = {
            "content_type": forms.Select(attrs={"class": "form-select", "id": "id_content_type"}),
            "text": forms.Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": "متن پیام خود را اینجا بنویسید..."}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        """دریافت کاربر برای فیلتر کردن کانال‌های قابل انتخاب."""
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["channels"].queryset = BroadcastChannel.objects.filter(user=user, is_active=True, bot_is_admin=True)
