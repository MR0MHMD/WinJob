from django import forms
from django.utils.safestring import mark_safe
from influencers.models import InfluencerProfile, Channel


class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel

        fields = (
            "platform",
            "channel_id",
            "province",
            "category",
            "channel_name",
            "url",
            "followers_count",
            "avatar",
            "bio",
        )

        widgets = {

            "platform": forms.Select(
                attrs={
                    "class": "form-select bg-dark text-light border-light",
                }
            ),
            "province": forms.Select(
                attrs={
                    "class": "form-select bg-dark text-light border-light",
                    "required": False
                }
            ),

            "category": forms.Select(
                attrs={
                    "class": "form-select bg-dark text-light border-light",
                }
            ),

            "channel_id": forms.TextInput(
                attrs={
                    "class": "form-control bg-dark text-light border-light",
                    "placeholder": "آیدی کانال بدون @",
                }
            ),

            "channel_name": forms.TextInput(
                attrs={
                    "class": "form-control bg-dark text-light border-light",
                    "placeholder": "نام کانال",
                }
            ),

            "url": forms.URLInput(
                attrs={
                    "class": "form-control bg-dark text-light border-light",
                    "placeholder": "https://...",
                }
            ),

            "followers_count": forms.TextInput(
                attrs={
                    "class": "form-control bg-dark text-light border-light",
                }
            ),

            "avatar": forms.FileInput(
                attrs={
                    "accept": "image/webp, image/jpeg",
                    "style": "display: none;",
                }
            ),

            "bio": forms.Textarea(
                attrs={
                    "class": "form-control bg-dark text-light border-light",
                    "rows": 4,
                    "placeholder": "درباره کانال خود توضیح دهید...",
                    "maxlength": 800,
                }
            ),
        }

    def clean_channel_id(self):
        """
        پاک کردن @ از اول و آخر آیدی کانال
        """
        channel_id = self.cleaned_data.get("channel_id") or ""
        channel_id = channel_id.strip()

        # حذف @ از اول
        if channel_id.startswith('@'):
            channel_id = channel_id[1:]

        # حذف @ از آخر (اگر کسی اشتباهی آخرش @ گذاشته باشه)
        if channel_id.endswith('@'):
            channel_id = channel_id[:-1]

        # حذف @ های تکراری (اگه کسی @@@example رو وارد کرده باشه)
        while channel_id.startswith('@'):
            channel_id = channel_id[1:]

        return channel_id

    def clean_channel_name(self):
        """
        پاکسازی نام کانال
        """
        return (self.cleaned_data.get("channel_name") or "").strip()
