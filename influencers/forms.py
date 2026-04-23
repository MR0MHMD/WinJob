from django import forms
from django.utils.safestring import mark_safe
from influencers.models import InfluencerProfile, InfluencerChannel


class InfluencerProfileForm(forms.ModelForm):
    class Meta:
        model = InfluencerProfile

        fields = (
            "full_name",
            "description",
        )

        widgets = {

            "full_name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "placeholder": "نام کامل کانال یا پیج",
                    "data-bs-binded-element": "#full-name-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "full-name-input",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "rows": 4,
                    "placeholder": "درباره خودت و محتوای پیج بنویس",
                }
            ),
        }

    def clean_full_name(self):
        return (self.cleaned_data.get("full_name") or "").strip()

    def clean_description(self):
        return ((self.cleaned_data.get("description") or "").strip()) or ""


class InfluencerChannelForm(forms.ModelForm):
    class Meta:
        model = InfluencerChannel

        fields = (
            "platform",
            "channel_id",
            "province",
            "city",
            "category",
            "channel_name",
            "url",
            "followers_count",
            "avatar"
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

            "city": forms.Select(
                attrs={
                    "class": "form-select bg-dark text-light border-light",
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
                    "placeholder": "@example",
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

            "followers_count": forms.NumberInput(
                attrs={
                    "class": "form-control bg-dark text-light border-light",
                }
            ),

            "avatar": forms.FileInput(
                attrs={
                    "class": "file-uploader border-light bg-faded-light",
                    "name": "image",
                    "accept": "image/png, image/jpeg",
                    "data-label-idle": mark_safe(
                        "<i class='d-inline-block fi-camera-plus fs-2 text-light text-muted mb-2'></i>"
                        "<br><span class='text-light opacity-70'>تغییر تصویر</span>"
                    ),
                    "data-style-panel-layout": "compact",
                    "data-image-preview-height": "160",
                    "data-image-crop-aspect-ratio": "1:1",
                    "data-image-resize-target-width": "200",
                    "data-image-resize-target-height": "200",
                }
            ),
        }

    def clean_channel_id(self):
        return (self.cleaned_data.get("channel_id") or "").strip()

    def clean_channel_name(self):
        return (self.cleaned_data.get("channel_name") or "").strip()
