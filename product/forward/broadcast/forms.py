"""فرم‌های مربوط به وین فوروارد."""

from django import forms
from product.forward.broadcast.models import BroadcastMessage, BroadcastChannel


class BroadcastSendForm(forms.ModelForm):
    """فرم ارسال پیام جدید به چند کانال."""

    channels = forms.ModelMultipleChoiceField(queryset=BroadcastChannel.objects.none(),
                                              widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
                                              label="کانال‌های مقصد", required=True, )

    class Meta:
        """تنظیمات متادیتای فرم."""
        model = BroadcastMessage
        fields = ["content_type", "text", "file"]
        widgets = {
            "content_type": forms.Select(attrs={"class": "form-select", "id": "id_content_type"}),
            "text": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "placeholder": "متن پیام خود را اینجا بنویسید..."}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        """دریافت کاربر برای فیلتر کردن کانال‌های قابل انتخاب."""
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["channels"].queryset = BroadcastChannel.objects.filter(user=user, is_active=True,
                                                                               bot_is_admin=True)


# ============================================================
# Eitaa Forms (Web Panel)
# ============================================================


class EitaaTokenForm(forms.Form):
    """فرم ورود و اعتبارسنجی توکن ایتایار."""

    api_token = forms.CharField(
        label="توکن ایتایار",
        max_length=256,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "توکن ربات ایتایار خود را اینجا وارد کنید",
            "dir": "ltr",
            "autocomplete": "off",
            "spellcheck": "false",
        }),
        help_text="توکن را از پنل eitaayar.ir دریافت کنید.",
    )

    def clean_api_token(self):
        token = self.cleaned_data["api_token"].strip()

        if len(token) < 20 or " " in token:
            raise forms.ValidationError("توکن معتبر به نظر نمی‌رسد (باید یک رشته طولانی و بدون فاصله باشد).")

        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        from product.forward.messengers.adapters.base import MessengerError

        try:
            adapter = EitaaAdapter(token=token)
            bot_username = adapter.get_bot_username()
            if not bot_username:
                raise forms.ValidationError("توکن نامعتبر است یا ربات در ایتا یافت نشد.")
        except MessengerError as e:
            raise forms.ValidationError(f"خطا در اعتبارسنجی توکن: {e}")

        return token


class EitaaChannelForm(forms.Form):
    """فرم افزودن کانال ایتا با اعتبارسنجی از طریق ارسال پیام تستی."""

    chat_id = forms.CharField(
        label="شناسه کانال",
        max_length=64,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "مثلاً: 1404 یا winjob_news",
            "dir": "ltr",
            "autocomplete": "off",
        }),
        help_text="شناسه عددی یا نام کاربری کانال در ایتا (بدون @).",
    )

    title = forms.CharField(
        label="نام نمایشی کانال",
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "مثلاً: کانال اخبار وین‌جاب",
        }),
        help_text="این نام فقط در پنل وین‌فوروارد نمایش داده می‌شود.",
    )

    username = forms.CharField(
        label="نام کاربری کانال (اختیاری)",
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "بدون @ — مثلاً: winjob_news",
            "dir": "ltr",
        }),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.api_token = kwargs.pop("api_token", None)
        super().__init__(*args, **kwargs)

    def clean_chat_id(self):
        chat_id = self.cleaned_data["chat_id"].strip().lstrip("@")
        if not chat_id:
            raise forms.ValidationError("شناسه کانال الزامی است.")
        return chat_id

    def clean(self):
        cleaned = super().clean()
        chat_id = cleaned.get("chat_id")

        if not self.user or not self.api_token or not chat_id:
            return cleaned

        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel

        eitaa = Platform.objects.filter(slug="eitaa").first()
        if eitaa and BroadcastChannel.objects.filter(
                user=self.user, platform=eitaa, chat_id=chat_id, is_active=True
        ).exists():
            raise forms.ValidationError("این کانال قبلاً به حساب شما متصل شده است.")

        from product.forward.messengers.adapters.eitaa import EitaaAdapter
        from product.forward.messengers.adapters.base import MessengerError

        try:
            adapter = EitaaAdapter(token=self.api_token)
            adapter.send_text(
                chat_id,
                "✅ این یک پیام تستی از وین‌فوروارد است.\n"
                "کانال شما با موفقیت متصل شد و از این پس می‌توانید پیام‌ها را از اینجا دریافت کنید.",
            )
        except MessengerError as e:
            raise forms.ValidationError(
                f"خطا در اتصال به کانال: {e} — مطمئن شوید حساب @sender به عنوان ادمین در کانال تعریف شده است."
            )

        return cleaned
