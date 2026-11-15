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


# ============================================================
# Rubika Forms (Web Panel)
# ============================================================


class RubikaPhoneForm(forms.Form):
    """فرم مرحله اول ورود به روبیکا — دریافت شماره موبایل و ارسال کد تایید."""

    phone_number = forms.CharField(
        label="شماره موبایل روبیکا",
        max_length=15,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "مثلاً: 09123456789",
            "dir": "ltr",
            "autocomplete": "tel",
        }),
        help_text="شماره موبایلی که با آن در روبیکا حساب کاربری دارید وارد کنید.",
    )

    def clean_phone_number(self):
        """نرمال‌سازی شماره موبایل به فرمت استاندارد 989xxxxxxxxx برای API روبیکا."""
        raw = self.cleaned_data["phone_number"].strip().replace(" ", "").replace("-", "")
        if raw.startswith("+"):
            raw = raw[1:]
        if raw.startswith("09") and len(raw) == 11:
            raw = "98" + raw[1:]
        elif raw.startswith("9") and len(raw) == 10:
            raw = "98" + raw
        if not raw.startswith("989") or len(raw) != 12 or not raw.isdigit():
            raise forms.ValidationError("فرمت شماره موبایل معتبر نیست (مثال صحیح: 09123456789).")
        return raw


class RubikaVerifyCodeForm(forms.Form):
    """فرم مرحله دوم ورود به روبیکا — دریافت و اعتبارسنجی کد تایید ۵ رقمی."""

    phone_code = forms.CharField(
        label="کد تایید (OTP)",
        max_length=10,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light text-center",
            "placeholder": "کد ارسال‌شده به روبیکا یا پیامک",
            "dir": "ltr",
            "autocomplete": "one-time-code",
        }),
        help_text="کد تاییدی که به پیامک یا پیام‌های داخلی روبیکای شما ارسال شده را وارد کنید.",
    )

    def clean_phone_code(self):
        """پاکسازی فاصله‌های اضافه و بررسی عددی بودن کد تایید."""
        code = self.cleaned_data["phone_code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("کد تایید باید فقط شامل اعداد باشد.")
        return code


class RubikaChannelForm(forms.Form):
    """فرم افزودن دستی کانال روبیکا با نام کاربری یا شناسه GUID و بررسی دسترسی ارسال."""

    channel_identifier = forms.CharField(
        label="نام کاربری یا شناسه کانال (GUID)",
        max_length=64,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "مثلاً: winjob_news یا c0B123456789...",
            "dir": "ltr",
            "autocomplete": "off",
        }),
        help_text="نام کاربری کانال (بدون یا با @) یا شناسه GUID کانال (شروع با c0) را وارد کنید.",
    )

    title = forms.CharField(
        label="نام نمایشی کانال (اختیاری)",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "در صورت خالی بودن، عنوان واقعی از روبیکا خوانده می‌شود",
        }),
    )

    def __init__(self, *args, **kwargs):
        """دریافت کاربر و نمونه آداپتور روبیکا برای بررسی کانال هنگام اعتبارسنجی."""
        self.user = kwargs.pop("user", None)
        self.rubika_adapter = kwargs.pop("rubika_adapter", None)
        self.resolved_channel = None
        super().__init__(*args, **kwargs)

    def clean(self):
        """استعلام اطلاعات کانال از روبیکا، بررسی تکراری نبودن و تست دسترسی ارسال."""
        cleaned = super().clean()
        identifier = (cleaned.get("channel_identifier") or "").strip().lstrip("@")
        if not identifier or not self.rubika_adapter or not self.user:
            return cleaned

        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel
        from product.forward.messengers.adapters.base import MessengerError

        try:
            info = self.rubika_adapter.get_chat_info(identifier)
        except MessengerError as exc:
            raise forms.ValidationError(f"کانال در روبیکا یافت نشد یا قابل دسترس نیست: {exc}")

        chat_id = info.get("chat_id")
        if not chat_id:
            raise forms.ValidationError("شناسه GUID کانال از روبیکا دریافت نشد.")

        rubika_platform = Platform.objects.filter(slug="rubika").first()
        if rubika_platform and BroadcastChannel.objects.filter(
            user=self.user, platform=rubika_platform, chat_id=chat_id, is_active=True
        ).exists():
            raise forms.ValidationError("این کانال قبلاً به حساب شما متصل شده است.")

        if not self.rubika_adapter.check_bot_is_admin(chat_id):
            raise forms.ValidationError("حساب روبیکای شما در این کانال دسترسی ارسال پیام (ادمین) ندارد.")

        self.resolved_channel = {
            "chat_id": chat_id,
            "title": (cleaned.get("title") or "").strip() or info.get("title") or chat_id,
            "username": info.get("username") or (identifier if not identifier.startswith("c0") else ""),
        }
        return cleaned


# ============================================================
# Soroush Plus Forms (Web Panel)
# ============================================================


class SoroushPhoneForm(forms.Form):
    """فرم مرحله اول ورود به سروش‌پلاس — دریافت شماره موبایل و ارسال کد تایید."""

    phone_number = forms.CharField(
        label="شماره موبایل سروش‌پلاس",
        max_length=16,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "مثلاً: 09123456789",
            "dir": "ltr",
            "autocomplete": "tel",
        }),
        help_text="شماره موبایلی که با آن در سروش‌پلاس حساب کاربری دارید وارد کنید.",
    )

    def clean_phone_number(self):
        """نرمال‌سازی شماره موبایل به فرمت استاندارد +989xxxxxxxxx برای SPlusthon."""
        raw = self.cleaned_data["phone_number"].strip().replace(" ", "").replace("-", "")
        if raw.startswith("+"):
            raw = raw[1:]
        if raw.startswith("09") and len(raw) == 11:
            raw = "98" + raw[1:]
        elif raw.startswith("9") and len(raw) == 10:
            raw = "98" + raw
        if not raw.startswith("989") or len(raw) != 12 or not raw.isdigit():
            raise forms.ValidationError("فرمت شماره موبایل معتبر نیست (مثال صحیح: 09123456789).")
        return f"+{raw}"


class SoroushVerifyCodeForm(forms.Form):
    """فرم مرحله دوم ورود به سروش‌پلاس — دریافت کد تایید و رمز دومرحله‌ای اختیاری."""

    phone_code = forms.CharField(
        label="کد تایید (OTP)",
        max_length=10,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light text-center",
            "placeholder": "کد ارسال‌شده به سروش‌پلاس یا پیامک",
            "dir": "ltr",
            "autocomplete": "one-time-code",
        }),
        help_text="کد تاییدی که به پیامک یا داخل اپ سروش‌پلاس ارسال شده را وارد کنید.",
    )

    password = forms.CharField(
        label="رمز تایید دومرحله‌ای (در صورت فعال بودن)",
        max_length=128,
        required=False,
        widget=forms.PasswordInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "اگر رمز دومرحله‌ای ندارید خالی بگذارید",
            "dir": "ltr",
        }),
    )

    def clean_phone_code(self):
        """پاکسازی فاصله‌های اضافه و بررسی عددی بودن کد تایید."""
        code = self.cleaned_data["phone_code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("کد تایید باید فقط شامل اعداد باشد.")
        return code


class SoroushChannelForm(forms.Form):
    """فرم افزودن دستی کانال سروش‌پلاس با نام کاربری یا شناسه عددی و بررسی دسترسی ارسال."""

    channel_identifier = forms.CharField(
        label="نام کاربری یا شناسه کانال",
        max_length=64,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "مثلاً: winjob_news یا 123456789",
            "dir": "ltr",
            "autocomplete": "off",
        }),
        help_text="نام کاربری کانال (بدون یا با @) یا شناسه عددی کانال را وارد کنید.",
    )

    title = forms.CharField(
        label="نام نمایشی کانال (اختیاری)",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "در صورت خالی بودن، عنوان واقعی از سروش‌پلاس خوانده می‌شود",
        }),
    )

    def __init__(self, *args, **kwargs):
        """دریافت کاربر و نمونه آداپتور سروش‌پلاس برای بررسی کانال هنگام اعتبارسنجی."""
        self.user = kwargs.pop("user", None)
        self.soroush_adapter = kwargs.pop("soroush_adapter", None)
        self.resolved_channel = None
        super().__init__(*args, **kwargs)

    def clean(self):
        """استعلام اطلاعات کانال از سروش‌پلاس، بررسی تکراری نبودن و تست دسترسی ارسال."""
        cleaned = super().clean()
        identifier = (cleaned.get("channel_identifier") or "").strip().lstrip("@")
        if not identifier or not self.soroush_adapter or not self.user:
            return cleaned

        from core.models import Platform
        from product.forward.broadcast.models import BroadcastChannel
        from product.forward.messengers.adapters.base import MessengerError

        try:
            info = self.soroush_adapter.get_chat_info(identifier)
        except MessengerError as exc:
            raise forms.ValidationError(f"کانال در سروش‌پلاس یافت نشد یا قابل دسترس نیست: {exc}")

        chat_id = info.get("chat_id")
        if not chat_id:
            raise forms.ValidationError("شناسه کانال از سروش‌پلاس دریافت نشد.")

        soroush_platform = Platform.objects.filter(slug="soroush").first()
        if soroush_platform and BroadcastChannel.objects.filter(
            user=self.user, platform=soroush_platform, chat_id=chat_id, is_active=True
        ).exists():
            raise forms.ValidationError("این کانال قبلاً به حساب شما متصل شده است.")

        if not self.soroush_adapter.check_bot_is_admin(chat_id):
            raise forms.ValidationError("حساب سروش‌پلاس شما در این کانال دسترسی ارسال پیام (ادمین) ندارد.")

        self.resolved_channel = {
            "chat_id": chat_id,
            "title": (cleaned.get("title") or "").strip() or info.get("title") or chat_id,
            "username": info.get("username") or (identifier if not identifier.lstrip("-").isdigit() else ""),
        }
        return cleaned
