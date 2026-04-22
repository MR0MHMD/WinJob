from django import forms
from django.utils.safestring import mark_safe
from .models import AdvertiserProfile


class AdvertiserProfileForm(forms.ModelForm):
    """فرم ساخت/ویرایش پروفایل تبلیغ‌دهنده."""

    class Meta:
        model = AdvertiserProfile
        fields = (
            "business_name",
            "city",
            "category",
            "description",
            "website",
        )

        widgets = {
            "business_name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "placeholder": "نام کسب‌وکار",
                    "data-bs-binded-element": "#business-name-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "business-name-input",
                }
            ),

            "category": forms.Select(
                attrs={
                    "class": "form-select form-select-light mt-3",
                    "data-bs-binded-element": "#category-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "category-input",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "rows": 4,
                    "placeholder": "توضیحات کسب‌وکار",
                    "data-bs-binded-element": "#description-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "description-input",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "placeholder": "https://example.com",
                    "data-bs-binded-element": "#website-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "website-input",
                }
            ),
        }

    def clean_business_name(self):
        return (self.cleaned_data.get("business_name") or "").strip()

    def clean_description(self):
        return ((self.cleaned_data.get("description") or "").strip()) or ""

    def clean_website(self):
        return ((self.cleaned_data.get("website") or "").strip()) or ""
