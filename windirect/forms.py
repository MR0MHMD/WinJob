import re

from django import forms

from .models import Automation, InstagramConnection


class InstagramConnectionForm(forms.ModelForm):
    """نام حساب را فقط برای آزمایش محلی وین دایرکت دریافت می‌کند."""

    class Meta:
        model = InstagramConnection
        fields = ("username",)
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-control bg-dark text-light border-light",
                "placeholder": "مثلاً winjob.ir",
                "autocomplete": "off",
                "dir": "ltr",
            }),
        }

    def clean_username(self):
        """نام کاربری را یکسان‌سازی و از ثبت نشانی یا شناسهٔ نامعتبر جلوگیری می‌کند."""
        username = self.cleaned_data["username"].strip().lstrip("@").lower()
        if not re.fullmatch(r"[a-z0-9._]{1,30}", username):
            raise forms.ValidationError("نام کاربری را بدون لینک و فقط با حروف انگلیسی، عدد، نقطه یا زیرخط وارد کنید.")
        return username


class AutomationForm(forms.ModelForm):
    """قانون را برای یکی از حساب‌های آزمایشی همین کاربر ویرایش می‌کند."""

    class Meta:
        model = Automation
        fields = ("connection", "name", "media_id", "keyword", "match_type", "reply_text", "is_active")
        widgets = {
            "connection": forms.Select(attrs={"class": "form-select bg-dark text-light border-light"}),
            "name": forms.TextInput(attrs={"class": "form-control bg-dark text-light border-light", "placeholder": "مثلاً پاسخ به پرسش قیمت"}),
            "media_id": forms.TextInput(attrs={"class": "form-control bg-dark text-light border-light", "placeholder": "اختیاری؛ خالی یعنی همهٔ پست‌ها", "dir": "ltr"}),
            "keyword": forms.TextInput(attrs={"class": "form-control bg-dark text-light border-light", "placeholder": "مثلاً قیمت"}),
            "match_type": forms.Select(attrs={"class": "form-select bg-dark text-light border-light"}),
            "reply_text": forms.Textarea(attrs={"class": "form-control bg-dark text-light border-light", "rows": 5, "placeholder": "متن پاسخی که در شبیه‌سازی ثبت می‌شود"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, owner, **kwargs):
        """انتخاب حساب را به حساب‌های آزمایشی مالک محدود می‌کند."""
        super().__init__(*args, **kwargs)
        self.fields["connection"].queryset = InstagramConnection.objects.filter(
            owner=owner, status=InstagramConnection.Status.SIMULATED,
        )

    def clean_keyword(self):
        """کلیدواژهٔ خالی یا فقط فاصله را رد می‌کند."""
        keyword = self.cleaned_data["keyword"].strip()
        if not keyword:
            raise forms.ValidationError("کلیدواژه نمی‌تواند خالی باشد.")
        return keyword

    def clean_reply_text(self):
        """از ثبت پاسخ بدون متن جلوگیری می‌کند."""
        reply = self.cleaned_data["reply_text"].strip()
        if not reply:
            raise forms.ValidationError("متن پاسخ را وارد کنید.")
        return reply


class SimulationForm(forms.Form):
    """یک کامنت نمونه را بدون ارسال پیام برای قانون‌ها اجرا می‌کند."""

    connection = forms.ModelChoiceField(
        label="حساب آزمایشی", queryset=InstagramConnection.objects.none(),
        widget=forms.Select(attrs={"class": "form-select bg-dark text-light border-light"}),
    )
    media_id = forms.CharField(
        label="شناسهٔ پست نمونه", max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control bg-dark text-light border-light", "placeholder": "مثلاً post-1", "dir": "ltr"}),
    )
    text = forms.CharField(
        label="متن کامنت نمونه", max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-control bg-dark text-light border-light", "rows": 3, "placeholder": "مثلاً قیمت این محصول چنده؟"}),
    )

    def __init__(self, *args, owner, **kwargs):
        """فقط حساب‌های آزمایشی همین کاربر را برای اجرا نمایش می‌دهد."""
        super().__init__(*args, **kwargs)
        self.fields["connection"].queryset = InstagramConnection.objects.filter(
            owner=owner, status=InstagramConnection.Status.SIMULATED,
        )

    def clean_media_id(self):
        """شناسهٔ پست خالی را رد می‌کند."""
        value = self.cleaned_data["media_id"].strip()
        if not value:
            raise forms.ValidationError("شناسهٔ پست نمونه را وارد کنید.")
        return value

    def clean_text(self):
        """کامنت بدون متن را رد می‌کند."""
        value = self.cleaned_data["text"].strip()
        if not value:
            raise forms.ValidationError("متن کامنت نمونه را وارد کنید.")
        return value
