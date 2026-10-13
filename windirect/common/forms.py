from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from windirect.connections.models import InstagramConnection


def style_fields(form):
    """کلاس‌های مشترک تم سایت را به ورودی‌ها اضافه می‌کند."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = "form-check-input"
        elif isinstance(widget, forms.Select):
            widget.attrs["class"] = "form-select bg-dark text-light border-light"
        else:
            widget.attrs["class"] = "form-control bg-dark text-light border-light"
        if isinstance(widget, forms.Textarea):
            widget.attrs["rows"] = 3


class AssetForm(forms.ModelForm):
    """فقط حساب‌های آزمایشی مالک را در دسترس فرم قرار می‌دهد."""

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["connection"].queryset = InstagramConnection.objects.filter(
            owner=owner, status="simulated"
        )
        if self.instance.pk:
            self.fields["connection"].disabled = True
        style_fields(self)


class StyledChildForm(forms.ModelForm):
    """ورودی‌های کارت و سؤال را با تم سایت هماهنگ می‌کند."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class OrderedChildren(BaseInlineFormSet):
    """ترتیب‌های تکراری را رد می‌کند تا جریان سؤال و کارت روشن باشد."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        allowed_ids = set(self.get_queryset().values_list("pk", flat=True))
        for form in self.forms:
            child = form.cleaned_data.get("id")
            if child is not None and child.pk not in allowed_ids:
                raise ValidationError(
                    "یکی از موارد ارسالی متعلق به این ابزار نیست. صفحه را دوباره باز کنید."
                )
        positions = [
            f.cleaned_data.get("position")
            for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE")
        ]
        if len(set(positions)) != len(positions):
            raise ValidationError("ترتیب‌ها باید غیرتکراری باشند.")
