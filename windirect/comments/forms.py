from django import forms

from windirect.connections.models import InstagramConnection
from windirect.comments.models import Automation


class AutomationForm(forms.ModelForm):
    """فرم اصلی ساخت/ویرایش کامنت هوشمند."""

    # ==================== فیلدهای جدید (فقط از POST میان) ====================
    direct_message_file_url = forms.URLField(
        required=False,
        widget=forms.HiddenInput(),
    )
    direct_message_file_boxapi_id = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.HiddenInput(),
    )
    direct_message_file_name = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.HiddenInput(),
    )
    direct_message_file_size = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Automation
        fields = (
            "connection",
            "name",
            "target_type",
            "post_media_id",
            "post_is_simulated",
            "match_type",
            "reply_channel",
            "require_follow",
            "follow_prompt_text",
            "follow_prompt_button",
            "direct_message_kind",
            "direct_message_text",
            # ⚠️ direct_message_file رو حذف کردیم (دیگه توی فرم نیست)
        )
        widgets = {
            "connection": forms.Select(
                attrs={"class": "form-select wd-select"}
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control wd-control",
                    "placeholder": "مثلاً پاسخ به پرسش قیمت",
                }
            ),
            "target_type": forms.HiddenInput(),
            "post_media_id": forms.HiddenInput(),
            "post_is_simulated": forms.HiddenInput(),
            "match_type": forms.Select(
                attrs={"class": "form-select wd-select"}
            ),
            "reply_channel": forms.HiddenInput(),
            "require_follow": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "follow_prompt_text": forms.Textarea(
                attrs={
                    "class": "form-control wd-control",
                    "rows": 2,
                    "placeholder": "مثلاً: باید اول پیجم رو فالو کنی رفیق 🙃",
                    "maxlength": 500,
                }
            ),
            "follow_prompt_button": forms.TextInput(
                attrs={
                    "class": "form-control wd-control",
                    "placeholder": "مثلاً: فالو کردم",
                    "maxlength": 50,
                }
            ),
            "direct_message_kind": forms.HiddenInput(),
            "direct_message_text": forms.Textarea(
                attrs={
                    "class": "form-control wd-control",
                    "rows": 4,
                    "placeholder": "متن پیامی که در دایرکت ارسال می‌شود",
                    "maxlength": 2000,
                }
            ),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["connection"].queryset = InstagramConnection.objects.filter(
            owner=owner,
            status__in=[
                InstagramConnection.Status.SIMULATED,
                InstagramConnection.Status.CONNECTED,
            ],
        )
        # در ویرایش، اگه حساب قطع شده باشه، به لیست اضافه‌ش کن
        if self.instance and self.instance.pk and self.instance.connection_id:
            if not self.fields["connection"].queryset.filter(
                    pk=self.instance.connection_id
            ).exists():
                self.fields["connection"].queryset = (
                        self.fields["connection"].queryset
                        | InstagramConnection.objects.filter(pk=self.instance.connection_id)
                )

    def clean_name(self):
        """نام خالی یا فقط فاصله را رد می‌کند."""
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("نام کامنت هوشمند را وارد کنید.")
        return name

    def clean_match_type(self):
        match_type = self.cleaned_data.get("match_type")
        if match_type not in (Automation.MatchType.CONTAINS, Automation.MatchType.EXACT):
            raise forms.ValidationError("نوع تطبیق نامعتبر است.")
        return match_type

    def clean_target_type(self):
        target_type = self.cleaned_data.get("target_type")
        if target_type not in (Automation.TargetType.POST, Automation.TargetType.LIVE):
            raise forms.ValidationError("نوع هدف نامعتبر است.")
        return target_type

    def clean_reply_channel(self):
        channel = self.cleaned_data.get("reply_channel")
        if channel not in (Automation.ReplyChannel.COMMENT, Automation.ReplyChannel.DIRECT):
            raise forms.ValidationError("کانال پاسخ نامعتبر است.")
        return channel

    def clean(self):
        cleaned = super().clean()
        target_type = cleaned.get("target_type")
        reply_channel = cleaned.get("reply_channel")
        require_follow = cleaned.get("require_follow")
        direct_kind = cleaned.get("direct_message_kind")
        direct_text = cleaned.get("direct_message_text", "").strip()
        file_url = cleaned.get("direct_message_file_url", "").strip()

        # لایو
        if target_type == Automation.TargetType.LIVE and cleaned.get("post_media_id"):
            cleaned["post_media_id"] = ""

        # فالو اجباری
        if require_follow and reply_channel != Automation.ReplyChannel.DIRECT:
            self.add_error(
                "require_follow",
                "فالو اجباری فقط برای پاسخ در دایرکت مجاز است.",
            )

        if require_follow:
            if not cleaned.get("follow_prompt_text", "").strip():
                self.add_error("follow_prompt_text", "متن پیام فالو را وارد کنید.")
            if not cleaned.get("follow_prompt_button", "").strip():
                self.add_error("follow_prompt_button", "متن دکمه فالو را وارد کنید.")

        # محتوای دایرکت — فقط اگه دایرکت باشه
        if reply_channel == Automation.ReplyChannel.DIRECT:
            # ==================== متن ====================
            if direct_kind == Automation.DirectKind.TEXT:
                if not direct_text:
                    self.add_error("direct_message_text", "متن دایرکت را وارد کنید.")

            # ==================== صوت/تصویر/ویدیو ====================
            elif direct_kind in (
                    Automation.DirectKind.AUDIO,
                    Automation.DirectKind.IMAGE,
                    Automation.DirectKind.VIDEO,
            ):
                # چک کن یا URL جدید داره یا فایل قدیمی
                instance_url = ""
                if self.instance.pk and self.instance.media_upload:
                    instance_url = self.instance.media_upload.boxapi_url

                has_url = bool(file_url) or bool(instance_url)

                if not has_url:
                    self.add_error(
                        "direct_message_file_url",
                        "فایل مدیای دایرکت را انتخاب کنید.",
                    )

            # ==================== هیچ‌کدوم ====================
            else:
                self.add_error(
                    "direct_message_kind", "نوع محتوای دایرکت نامعتبر است."
                )

        return cleaned


class SimulationForm(forms.Form):
    """یک کامنت نمونه را بدون ارسال پیام واقعی برای قوانین اجرا می‌کند."""

    connection = forms.ModelChoiceField(
        label="حساب آزمایشی",
        queryset=InstagramConnection.objects.none(),
        widget=forms.Select(
            attrs={"class": "form-select-light wd-form-select"}
        ),
    )
    media_id = forms.CharField(
        label="شناسهٔ پست نمونه",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control-light wd-form-control",
                "placeholder": "مثلاً post-1",
                "dir": "ltr",
            }
        ),
    )
    text = forms.CharField(
        label="متن کامنت نمونه",
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "class": "form-control-light wd-form-control",
                "rows": 3,
                "placeholder": "مثلاً قیمت این محصول چنده؟",
            }
        ),
    )
    assume_followed = forms.BooleanField(
        label="فرض کن مخاطب پیج را فالو کرده است",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="در حالت آزمایش، این گزینه برای رد شدن از مرحلهٔ فالو استفاده می‌شود.",
    )

    def __init__(self, *args, owner, **kwargs):
        """فقط حساب‌های همین کاربر را برای اجرا نمایش می‌دهد."""
        super().__init__(*args, **kwargs)
        self.fields["connection"].queryset = InstagramConnection.objects.filter(
            owner=owner,
            status__in=[
                InstagramConnection.Status.SIMULATED,
                InstagramConnection.Status.CONNECTED,
            ],
        )

    def clean_media_id(self):
        value = self.cleaned_data.get("media_id", "").strip()
        if not value:
            raise forms.ValidationError("شناسهٔ پست نمونه را وارد کنید.")
        return value

    def clean_text(self):
        value = self.cleaned_data.get("text", "").strip()
        if not value:
            raise forms.ValidationError("متن کامنت نمونه را وارد کنید.")
        return value
