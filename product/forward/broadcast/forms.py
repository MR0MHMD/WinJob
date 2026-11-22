"""فرم‌های مربوط به وین فوروارد."""

from django import forms
from product.forward.broadcast.models import BroadcastMessage, BroadcastChannel, ChannelPreset, BroadcastHub


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
        """دریافت کاربر برای فیلتر کردن کانال‌ها و مشخص کردن وضعیت اشتراک هر پلتفرم."""
        from product.forward.subscriptions.access import get_active_platform_slugs

        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.active_platform_slugs = get_active_platform_slugs(user) if user else set()
        self.channel_items = []
        if user:
            qs = BroadcastChannel.objects.filter(
                user=user, is_active=True, bot_is_admin=True
            ).select_related("platform")
            self.fields["channels"].queryset = qs
            selected_ids = set(str(v) for v in (self.data.getlist("channels") if self.is_bound else []))
            for ch in qs:
                self.channel_items.append({
                    "channel": ch,
                    "has_access": ch.platform.slug in self.active_platform_slugs,
                    "checked": str(ch.pk) in selected_ids,
                })

    def clean_channels(self):
        """اطمینان از داشتن اشتراک فعال برای تمام کانال‌های انتخاب‌شده."""
        channels = self.cleaned_data.get("channels")
        for ch in channels:
            if ch.platform.slug not in self.active_platform_slugs:
                raise forms.ValidationError(
                    f"برای ارسال به کانال «{ch.title}» باید اشتراک فعال پلتفرم {ch.platform.name} را داشته باشید."
                )
        return channels


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



# ============================================================
# Soroush+ Forms (Web Panel)
# ============================================================


class SoroushPhoneForm(forms.Form):
    """فرم مرحله اول ورود به سروش‌پلاس — دریافت شماره موبایل و ارسال کد تایید."""

    phone_number = forms.CharField(
        label="شماره موبایل سروش‌پلاس",
        max_length=15,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "مثلاً: 09123456789",
            "dir": "ltr",
            "autocomplete": "tel",
        }),
        help_text="شماره موبایل اکانت سروش‌پلاسی که در کانال‌هایتان ادمین یا سازنده است را وارد کنید.",
    )

    def clean_phone_number(self):
        """نرمال‌سازی شماره موبایل به فرمت استاندارد +989xxxxxxxxx برای سروش‌پلاس."""
        raw = self.cleaned_data["phone_number"].strip().replace(" ", "").replace("-", "")
        if raw.startswith("+"):
            raw = raw[1:]
        if raw.startswith("0098"):
            raw = raw[2:]
        if raw.startswith("09") and len(raw) == 11:
            raw = "98" + raw[1:]
        elif raw.startswith("9") and len(raw) == 10:
            raw = "98" + raw
        if not raw.startswith("989") or len(raw) != 12 or not raw.isdigit():
            raise forms.ValidationError("فرمت شماره موبایل معتبر نیست (مثال صحیح: 09123456789).")
        return "+" + raw


class SoroushVerifyCodeForm(forms.Form):
    """فرم مرحله دوم ورود به سروش‌پلاس — تایید کد OTP و رمز دو مرحله‌ای اختیاری."""

    phone_code = forms.CharField(
        label="کد تایید (OTP)",
        max_length=10,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-light text-center",
            "placeholder": "کد ارسال‌شده به سروش‌پلاس یا پیامک",
            "dir": "ltr",
            "autocomplete": "one-time-code",
        }),
        help_text="کد تاییدی که به پیامک یا برنامه سروش‌پلاس شما ارسال شده را وارد کنید.",
    )
    two_step_password = forms.CharField(
        label="رمز تایید دو مرحله‌ای (اختیاری)",
        required=False,
        widget=forms.PasswordInput(attrs={
            "class": "form-control form-control-light",
            "placeholder": "فقط در صورتی که روی اکانت سروش‌پلاس رمز دو مرحله‌ای فعال دارید",
            "dir": "ltr",
            "autocomplete": "current-password",
        }),
    )

    def clean_phone_code(self):
        code = self.cleaned_data["phone_code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("کد تایید باید فقط شامل اعداد باشد.")
        return code


# ============================================================
# Channel Preset Forms (Web Panel)
# ============================================================


class ChannelPresetForm(forms.ModelForm):
    """فرم ساخت و ویرایش پکیج ارسال (گروه کانال‌ها) برای انتخاب سریع در وب و ربات بله."""

    channels = forms.ModelMultipleChoiceField(
        queryset=BroadcastChannel.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="کانال‌های عضو این پکیج",
        required=True,
        error_messages={"required": "لطفاً حداقل یک کانال را برای این پکیج انتخاب کنید."},
    )

    class Meta:
        model = ChannelPreset
        fields = ["name", "channels"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-light",
                    "placeholder": "مثلاً: کانال‌های فروش، اخبار فوری، مشتریان VIP",
                    "maxlength": "80",
                }
            )
        }
        labels = {
            "name": "نام پکیج ارسال",
        }

    def __init__(self, *args, **kwargs):
        """فیلتر کردن کانال‌ها به کانال‌های فعال و متصل کاربر."""
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["channels"].queryset = (
                BroadcastChannel.objects.filter(
                    user=self.user,
                    is_active=True,
                    bot_is_admin=True,
                )
                .select_related("platform")
                .order_by("platform__name", "title")
            )

    def clean_name(self):
        """بررسی تکراری نبودن نام پکیج برای همین کاربر."""
        from product.forward.broadcast.models import ChannelPreset

        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("نام پکیج ارسال الزامی است.")
        if self.user:
            qs = ChannelPreset.objects.filter(user=self.user, name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("پکیجی با این نام قبلاً ثبت شده است.")
        return name


class BroadcastHubForm(forms.ModelForm):
    """فرم ویرایش و پیکربندی پکیج، کانال‌های مقصد و حالت انتشار گروه هاب."""

    channels = forms.ModelMultipleChoiceField(
        queryset=BroadcastChannel.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="کانال‌های مقصد اضافی (اختیاری)",
        required=False,
    )

    class Meta:
        model = BroadcastHub
        fields = ["title", "preset", "channels", "publish_mode", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control form-control-light", "maxlength": "255"}),
            "preset": forms.Select(attrs={"class": "form-select form-control-light"}),
            "publish_mode": forms.Select(attrs={"class": "form-select form-control-light"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "title": "نام نمایشی هاب",
            "preset": "پکیج ارسال متصل (پیشنهادی)",
            "publish_mode": "شرط ارسال پیام‌های گروه",
            "is_active": "هاب فعال باشد",
        }

    def __init__(self, *args, **kwargs):
        """محدودسازی پکیج‌ها و کانال‌ها به دارایی‌های فعال کاربر مالک هاب."""
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["preset"].queryset = ChannelPreset.objects.filter(
                user=self.user, is_active=True
            ).order_by("-created_at")
            self.fields["preset"].empty_label = "— بدون پکیج (استفاده از کانال‌های تکی) —"
            self.fields["channels"].queryset = (
                BroadcastChannel.objects.filter(
                    user=self.user, is_active=True, bot_is_admin=True
                )
                .select_related("platform")
                .order_by("platform__name", "title")
            )

    def clean(self):
        cleaned = super().clean()
        preset = cleaned.get("preset")
        channels = cleaned.get("channels")
        if not preset and not channels:
            raise forms.ValidationError("لطفاً حداقل یک پکیج ارسال یا یک کانال مقصد برای این هاب انتخاب کنید.")
        return cleaned
