from django import forms
from windirect.connections.models import InstagramConnection
from windirect.direct.models import DirectRule
from windirect.showcases.models import Showcase
from windirect.forms.models import ConversationForm
from windirect.common.forms import AssetForm, style_fields


class DirectRuleForm(AssetForm):
    """تعریف محرک و پاسخ با جلوگیری از انتخاب ابزار کاربر دیگر."""

    class Meta:
        model = DirectRule
        fields = [
            "connection",
            "name",
            "keyword",
            "match_type",
            "priority",
            "response_type",
            "reply_text",
            "showcase",
            "form",
            "is_active",
        ]

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, owner=owner, **kwargs)
        self.fields["showcase"].queryset = Showcase.objects.filter(
            connection__owner=owner, is_active=True
        )
        self.fields["form"].queryset = ConversationForm.objects.filter(
            connection__owner=owner, is_active=True
        )
        self.fields["reply_text"].help_text = (
            "برای پاسخ متنی تکمیل کنید. ویترین یا فرم را فقط برای همان نوع پاسخ انتخاب کنید."
        )

    def clean(self):
        """فقط ابزار مربوط به نوع پاسخ انتخاب‌شده را ذخیره می‌کند."""
        data = super().clean()
        if data.get("response_type") != "showcase":
            data["showcase"] = None
        if data.get("response_type") != "form":
            data["form"] = None
        if data.get("response_type") != "text":
            data["reply_text"] = ""
        from windirect.subscriptions.access import require_feature

        connection = data.get("connection")
        response_type = data.get("response_type")
        if connection and response_type in ("form", "showcase"):
            require_feature(
                connection.owner, "forms" if response_type == "form" else "showcases"
            )
        return data


class DirectSimulationForm(forms.Form):
    """پیام ورودی برای یک مخاطب ثابت در شبیه‌ساز مکالمه."""

    connection = forms.ModelChoiceField(
        label="حساب آزمایشی", queryset=InstagramConnection.objects.none()
    )
    sender_id = forms.CharField(
        label="شناسهٔ مخاطب آزمایشی",
        max_length=100,
        initial="visitor-1",
        help_text="برای ادامهٔ فرم، همین حساب و شناسه را نگه دارید.",
    )
    text = forms.CharField(label="پیام مخاطب", max_length=2000, widget=forms.Textarea)
    message_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["connection"].queryset = InstagramConnection.objects.filter(
            owner=owner, status="simulated"
        )
        style_fields(self)
