import re
from django import forms
from windirect.connections.models import InstagramConnection


class InstagramConnectionForm(forms.ModelForm):
    """نام حساب را فقط برای آزمایش محلی وین دایرکت دریافت می‌کند."""

    class Meta:
        model = InstagramConnection
        fields = ("username",)
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control bg-dark text-light border-light",
                    "placeholder": "مثلاً winjob.ir",
                    "autocomplete": "off",
                    "dir": "ltr",
                }
            ),
        }

    def clean_username(self):
        """نام کاربری را یکسان‌سازی و از ثبت نشانی یا شناسهٔ نامعتبر جلوگیری می‌کند."""
        username = self.cleaned_data["username"].strip().lstrip("@").lower()
        if not re.fullmatch(r"[a-z0-9._]{1,30}", username):
            raise forms.ValidationError(
                "نام کاربری را بدون لینک و فقط با حروف انگلیسی، عدد، نقطه یا زیرخط وارد کنید."
            )
        return username