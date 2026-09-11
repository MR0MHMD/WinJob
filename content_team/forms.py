from .models import ContentServicePlan, ContentTeam
from core.models import ContentServiceType
from django.utils.text import slugify
from django import forms


class ContentServicePlanForm(forms.ModelForm):
    """
    فرم ایجاد و ویرایش پلن‌های تولید محتوا - نسخه جدید با واحدهای پیشرفته
    """

    features = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'هر ویژگی در یک خط یا به صورت لیست JSON'}),
        required=False,
        help_text='مثال: ["کیفیت 4K", "تحویل ۲ روزه"] یا هر خط یک ویژگی'
    )

    class Meta:
        model = ContentServicePlan
        fields = [
            'service_type',
            'name',
            'description',
            'features',
            'pricing_unit',
            'base_quantity',
            'min_quantity',
            'max_quantity',
            'price',
            'delivery_type',
            'delivery_options_count',
            'estimated_delivery_days',
            'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'pricing_unit': forms.Select(attrs={'class': 'form-select'}),
            'delivery_type': forms.Select(attrs={'class': 'form-select'}),
            'base_quantity': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
            'min_quantity': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
            'max_quantity': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'min': 0, 'class': 'form-control price-input'}),
            'estimated_delivery_days': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
            'delivery_options_count': forms.NumberInput(attrs={'min': 2, 'class': 'form-control'}),
        }
        labels = {
            'pricing_unit': 'واحد قیمت‌گذاری',
            'base_quantity': 'مقدار پایه',
            'min_quantity': 'حداقل مقدار',
            'max_quantity': 'حداکثر مقدار',
            'price': 'قیمت نهایی (تومان)',
            'delivery_type': 'نوع تحویل',
            'delivery_options_count': 'تعداد گزینه‌های تحویلی',
        }
        help_texts = {
            'pricing_unit': 'واحد اندازه‌گیری برای این پلن (ثانیه، دقیقه، یا تعدادی)',
            'base_quantity': 'مقدار پایه این پلن. مثلاً ۲۰ برای ۲۰ ثانیه، یا ۳ برای ۳ عدد پوستر',
            'min_quantity': 'حداقل مقداری که این پلن پوشش میدهد',
            'max_quantity': 'حداکثر مقداری که این پلن پوشش میدهد (اختیاری)',
            'price': 'قیمت کاملاً مشخص این پلن. مثلاً ۲۵۰,۰۰۰ تومان',
            'delivery_type': 'نحوه تحویل فایل‌ها به کاربر',
            'delivery_options_count': 'برای نوع تحویل MULTI_CHOICE: چند گزینه به کاربر داده میشه؟',
        }

    def __init__(self, *args, **kwargs):
        self.team = kwargs.pop('team', None)
        super().__init__(*args, **kwargs)

        if self.team:
            self.fields['service_type'].queryset = ContentServiceType.objects.filter(is_active=True)

        # ========== محدود کردن واحدها بر اساس service_type ==========
        if self.instance and self.instance.pk and self.instance.service_type:
            allowed_units = self.instance.service_type.allowed_units
            if allowed_units:
                self.fields['pricing_unit'].choices = [
                    (unit, label) for unit, label in ContentServicePlan.PricingUnit.choices
                    if unit in allowed_units
                ]

                # ========== اگر فقط یک واحد مجاز است ==========
                if len(allowed_units) == 1:
                    single_unit = allowed_units[0]
                    self.fields['pricing_unit'].initial = single_unit
                    self.fields['pricing_unit'].widget.attrs['disabled'] = True
                    unit_labels = dict(ContentServicePlan.PricingUnit.choices)
                    self.fields['pricing_unit'].help_text = (
                        f'این سرویس فقط از واحد "{unit_labels.get(single_unit, single_unit)}" پشتیبانی میکند.'
                    )

        # ========== محدود کردن delivery_type بر اساس pricing_unit ==========
        if self.instance and self.instance.pk and self.instance.pricing_unit:
            if self.instance.pricing_unit in ['second', 'minute']:
                self.fields['delivery_type'].choices = [('single', '📤 تحویل یک فایل')]
                self.fields['delivery_type'].widget.attrs['disabled'] = True
                self.fields['delivery_type'].help_text = 'برای این واحد فقط "تحویل یک فایل" مجاز است.'
                self.fields['delivery_options_count'].widget = forms.HiddenInput()
                self.fields['delivery_options_count'].required = False

        # ========== مخفی کردن delivery_options_count در صورت عدم نیاز ==========
        if self.instance and self.instance.pk:
            if self.instance.delivery_type != ContentServicePlan.DeliveryType.MULTI_CHOICE:
                self.fields['delivery_options_count'].widget = forms.HiddenInput()
                self.fields['delivery_options_count'].required = False
        else:
            self.fields['delivery_options_count'].widget = forms.HiddenInput()
            self.fields['delivery_options_count'].required = False

        self.fields['price'].widget.attrs['placeholder'] = 'مثلاً ۲۵۰,۰۰۰'

    def clean_features(self):
        data = self.cleaned_data.get('features')
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
        pricing_unit = cleaned_data.get('pricing_unit')
        delivery_type = cleaned_data.get('delivery_type')
        delivery_options_count = cleaned_data.get('delivery_options_count')
        base_quantity = cleaned_data.get('base_quantity')
        min_quantity = cleaned_data.get('min_quantity')
        max_quantity = cleaned_data.get('max_quantity')
        is_active = cleaned_data.get('is_active')

        # ========== ۱. اعتبارسنجی واحد ==========
        if service_type and pricing_unit:
            allowed_units = service_type.allowed_units
            if allowed_units and pricing_unit not in allowed_units:
                unit_labels = dict(ContentServicePlan.PricingUnit.choices)
                raise forms.ValidationError({
                    'pricing_unit': f'واحد "{unit_labels.get(pricing_unit, pricing_unit)}" '
                                    f'برای این سرویس مجاز نیست. '
                                    f'واحدهای مجاز: {service_type.get_allowed_units_display()}'
                })

        # ========== ۲. اعتبارسنجی delivery_type بر اساس pricing_unit ==========
        if pricing_unit in ['second', 'minute'] and delivery_type != 'single':
            raise forms.ValidationError({
                'delivery_type': 'برای واحد ثانیه و دقیقه، فقط "تحویل یک فایل" مجاز است.'
            })

        # ========== ۳. اعتبارسنجی delivery_options_count ==========
        if delivery_type == ContentServicePlan.DeliveryType.MULTI_CHOICE:
            if not delivery_options_count or delivery_options_count < 2:
                raise forms.ValidationError({
                    'delivery_options_count': 'برای تحویل چند گزینه‌ای، حداقل ۲ گزینه باید مشخص شود.'
                })
        else:
            if delivery_options_count is not None:
                self.cleaned_data['delivery_options_count'] = None

        # ========== ۴. اعتبارسنجی مقادیر عددی ==========
        if min_quantity and base_quantity and min_quantity > base_quantity:
            raise forms.ValidationError({
                'min_quantity': 'حداقل مقدار نمی‌تواند از مقدار پایه بیشتر باشد.'
            })

        if max_quantity and base_quantity and max_quantity < base_quantity:
            raise forms.ValidationError({
                'max_quantity': 'حداکثر مقدار نمی‌تواند از مقدار پایه کمتر باشد.'
            })

        if max_quantity and min_quantity and min_quantity > max_quantity:
            raise forms.ValidationError({
                'min_quantity': 'حداقل مقدار نمی‌تواند از حداکثر مقدار بیشتر باشد.'
            })

        # ========== ۵. تعداد پلن‌های فعال ==========
        if self.team and service_type and is_active:
            active_plans = ContentServicePlan.objects.filter(
                team=self.team,
                service_type=service_type,
                is_active=True
            )
            if self.instance.pk:
                active_plans = active_plans.exclude(pk=self.instance.pk)
            if active_plans.count() >= 3:
                raise forms.ValidationError(
                    'هر تیم برای هر خدمت حداکثر ۳ پلن فعال می‌تواند داشته باشد.'
                )

        return cleaned_data


class TeamManageForm(forms.ModelForm):
    """فرم مدیریت اطلاعات تیم"""

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
        if ContentTeam.objects.exclude(pk=self.instance.pk).filter(slug=slug).exists():
            raise forms.ValidationError("این اسلاگ قبلاً استفاده شده است.")
        return slug


# content_team/forms.py

from django import forms
from core.models import ContentServiceType
from .models import ContentTeam, ContentServicePlan


class StandaloneOrderStep1Form(forms.Form):
    """مرحله ۱: انتخاب نوع خدمت، تیم و پلن"""

    # ۱. انتخاب نوع خدمت
    service_type = forms.ModelChoiceField(
        queryset=ContentServiceType.objects.filter(is_active=True),
        label='نوع خدمت تولید محتوا',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'service-type-select'
        })
    )

    # ۲. انتخاب تیم (در ابتدا خالی)
    team = forms.ModelChoiceField(
        queryset=ContentTeam.objects.none(),
        label='تیم تولید محتوا',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'team-select'
        })
    )

    # ۳. انتخاب پلن (در ابتدا خالی)
    plan = forms.ModelChoiceField(
        queryset=ContentServicePlan.objects.none(),
        label='پلن انتخابی',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'plan-select'
        })
    )

    name = forms.CharField(
        label='نام سفارش',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': 'مثلاً: تیزر معرفی محصول جدید',
        }),
        error_messages={
            'required': 'لطفاً نام سفارش را وارد کنید.',
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ========== ۱. فیلتر تیم‌ها بر اساس سرویس انتخاب شده ==========
        service_type_id = self.data.get('service_type') or self.initial.get('service_type')

        if service_type_id:
            # تیم‌هایی که حداقل یک پلن فعال برای این سرویس دارن
            team_ids = ContentServicePlan.objects.filter(
                service_type_id=service_type_id,
                is_active=True
            ).values_list('team_id', flat=True).distinct()

            self.fields['team'].queryset = ContentTeam.objects.filter(
                id__in=team_ids,
                is_active=True
            )

        # ========== ۲. فیلتر پلن‌ها بر اساس تیم و سرویس ==========
        team_id = self.data.get('team') or self.initial.get('team')

        if service_type_id and team_id:
            self.fields['plan'].queryset = ContentServicePlan.objects.filter(
                service_type_id=service_type_id,
                team_id=team_id,
                is_active=True
            )


# content_team/forms.py

from django import forms
from .models import ContentOrderDescription, ContentOrder, ContentOrderFile
from core.models import ContentServiceType
from django.core.exceptions import ValidationError


class StandaloneOrderStep2Form(forms.ModelForm):
    """
    فرم بریف سفارش تولید محتوای مستقل - کاملاً مشابه CampaignStep3BriefForm
    """

    class Meta:
        model = ContentOrderDescription
        fields = [
            'goal',
            'goal_description',
            'tone',
            'brand_name',
            'hashtags',
            'reference_links',
            'target_audience',
            'description',
            'do_not_include',
        ]
        widgets = {
            'goal': forms.Select(attrs={
                'class': 'form-select form-select-light',
                'id': 'id_goal',
            }),
            'goal_description': forms.TextInput(attrs={
                'class': 'form-control form-control-light',
                'placeholder': 'توضیح بیشتر برای هدف انتخابی...',
                'id': 'id_goal_description',
            }),
            'tone': forms.Select(attrs={
                'class': 'form-select form-select-light',
                'id': 'id_tone',
            }),
            'brand_name': forms.TextInput(attrs={
                'class': 'form-control form-control-light',
                'placeholder': 'مثلاً: دیجی‌کالا، اسنپ...',
                'id': 'id_brand_name',
            }),
            'hashtags': forms.TextInput(attrs={
                'class': 'form-control form-control-light',
                'placeholder': 'مثلاً: #برند_من #تخفیف_ویژه',
                'id': 'id_hashtags',
            }),
            'reference_links': forms.Textarea(attrs={
                'class': 'form-control form-control-light',
                'rows': 3,
                'placeholder': 'هر لینک را در یک خط بنویسید...',
                'id': 'id_reference_links',
            }),
            'target_audience': forms.TextInput(attrs={
                'class': 'form-control form-control-light',
                'placeholder': 'مثلاً: زنان ۲۵-۳۵ ساله علاقه‌مند به مد',
                'id': 'id_target_audience',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control form-control-light',
                'rows': 5,
                'placeholder': 'هر اطلاعات دیگری که تیم باید بداند... (حداقل ۲۰ کاراکتر)',
                'id': 'id_description',
            }),
            'do_not_include': forms.Textarea(attrs={
                'class': 'form-control form-control-light',
                'rows': 3,
                'placeholder': 'مثلاً: رنگ قرمز، افکت‌های بصری خاص...',
                'id': 'id_do_not_include',
            }),
        }
        error_messages = {
            'description': {
                'required': 'لطفاً توضیحات را وارد کنید.',
            },
            'goal': {
                'required': 'لطفاً هدف محتوا را انتخاب کنید.',
            },
        }

    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)

    def clean_description(self):
        description = self.cleaned_data.get("description", "").strip()
        if len(description) < 20:
            raise forms.ValidationError("توضیحات باید حداقل ۲۰ کاراکتر باشد.")
        return description

    def clean_goal_description(self):
        """اگر هدف 'سایر' انتخاب شد، توضیح الزامی است"""
        goal = self.cleaned_data.get("goal")
        goal_description = self.cleaned_data.get("goal_description") or ""

        if goal == ContentOrderDescription.ContentGoal.OTHER and not goal_description.strip():
            raise forms.ValidationError(
                "چون «سایر» انتخاب کردید، لطفاً توضیح بدهید."
            )

        return goal_description

    def save(self, commit=True):
        """ذخیره بریف و اتصال به سفارش"""
        instance = super().save(commit=False)
        if self.order:
            instance.order = self.order
        if commit:
            instance.save()
        return instance
