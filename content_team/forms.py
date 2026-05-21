# content/forms.py
from django import forms
from .models import ContentServicePlan, ContentServiceType

class ContentServicePlanForm(forms.ModelForm):
    features = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'هر ویژگی در یک خط یا به صورت لیست JSON'}),
        required=False,
        help_text='مثال: ["کیفیت 4K", "تحویل ۲ روزه"] یا هر خط یک ویژگی'
    )

    class Meta:
        model = ContentServicePlan
        fields = ['service_type', 'name', 'description', 'features', 'price_per_unit',
                  'estimated_delivery_days', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'price-input'}),
            'estimated_delivery_days': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        self.team = kwargs.pop('team', None)
        super().__init__(*args, **kwargs)
        if self.team:
            self.fields['service_type'].queryset = ContentServiceType.objects.filter(is_active=True)

    def clean_features(self):
        data = self.cleaned_data['features']
        if not data:
            return []
        import json
        if data.strip().startswith('['):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                raise forms.ValidationError('فرمت JSON معتبر نیست.')
        else:
            return [line.strip() for line in data.split('\n') if line.strip()]

    def clean(self):
        cleaned_data = super().clean()
        service_type = cleaned_data.get('service_type')
        is_active = cleaned_data.get('is_active')
        if self.team and service_type and is_active:
            active_plans = ContentServicePlan.objects.filter(
                team=self.team,
                service_type=service_type,
                is_active=True
            )
            if self.instance.pk:
                active_plans = active_plans.exclude(pk=self.instance.pk)
            if active_plans.count() >= 3:
                raise forms.ValidationError('هر تیم برای هر خدمت حداکثر ۳ پلن فعال می‌تواند داشته باشد.')
        return cleaned_data


from django import forms
from django.utils.text import slugify
from .models import ContentTeam


class TeamManageForm(forms.ModelForm):
    class Meta:
        model = ContentTeam
        fields = ['name', 'description', 'logo', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if not slug:
            slug = slugify(self.cleaned_data.get('name', ''))
        # بررسی یکتا نبودن به جز خود تیم
        if ContentTeam.objects.exclude(pk=self.instance.pk).filter(slug=slug).exists():
            raise forms.ValidationError("این اسلاگ قبلاً استفاده شده است.")
        return slug