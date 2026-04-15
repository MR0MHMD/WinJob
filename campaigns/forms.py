from content_team.models import ContentServiceType, ContentServiceRate, ContentOrderDescription
from .utils import jalali_str_to_datetime, validate_start_date, validate_end_date
from .models import ContentType, AdType, CampaignContent
from urllib.parse import urlparse, urlencode, urlunparse
from influencers.models import InfluencerProfile
from location.models import Province, City
from plat_form.models import Platform
from core.models import Category
from django import forms
import json


class CampaignStep1Form(forms.Form):
    platform = forms.ModelChoiceField(
        queryset=Platform.objects.all(),
        label='پلتفرم',
        empty_label='پلتفرم خود را انتخاب کنید',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-light',
            'id': 'id_platform',
        })
    )

    content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.none(),
        label='نوع محتوا',
        empty_label='ابتدا پلتفرم را انتخاب کنید',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-light',
            'id': 'id_content_type',
            'disabled': 'disabled',
        })
    )

    ad_type = forms.ModelChoiceField(
        queryset=AdType.objects.none(),
        label='نوع تبلیغ',
        empty_label='ابتدا پلتفرم را انتخاب کنید',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-light',
            'id': 'id_ad_type',
            'disabled': 'disabled',
        })
    )

    name = forms.CharField(
        label='نام کمپین',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-light',
            'id': 'id_name',
            'placeholder': 'مثلاً: کمپین تابستانی ۱۴۰۴',
        })
    )

    start_date = forms.CharField(
        label="تاریخ شروع",
        widget=forms.HiddenInput()
    )

    end_date = forms.CharField(
        label="تاریخ پایان",
        widget=forms.HiddenInput()
    )
    content_service_type = forms.ModelChoiceField(
        queryset=ContentServiceType.objects.none(),
        required=False,
        label='نوع خدمت تولید محتوا',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-light',
            'id': 'id_content_service_type',
        })
    )

    minutes = forms.IntegerField(
        required=False,
        label='مدت (دقیقه)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-light',
            'id': 'id_minutes',
            'min': 1
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # پیشفرض
        self.fields['content_type'].queryset = ContentType.objects.none()
        self.fields['ad_type'].queryset = AdType.objects.none()

        data = self.data or None

        if data:
            platform_id = data.get('platform')

            if platform_id:
                self.fields['content_type'].queryset = ContentType.objects.filter(
                    platform=platform_id,
                    is_active=True
                )

                self.fields['ad_type'].queryset = AdType.objects.filter(
                    platform=platform_id,
                    is_active=True
                )

            ad_type_id = data.get("ad_type")

            if ad_type_id:
                self.fields['content_service_type'].queryset = ContentServiceType.objects.filter(
                    ad_type=ad_type_id,
                    is_active=True
                )

    def clean_start_date(self):
        """✅ تبدیل و اعتبارسنجی تاریخ شروع"""
        start_date_str = self.cleaned_data.get('start_date')

        if not start_date_str:
            raise forms.ValidationError('تاریخ شروع الزامی است.')

        try:
            start_date = jalali_str_to_datetime(start_date_str)
        except (ValueError, Exception):
            raise forms.ValidationError('فرمت تاریخ شروع صحیح نیست.')

        try:
            validate_start_date(start_date)
        except ValueError as e:
            raise forms.ValidationError(str(e))

        return start_date

    def clean_end_date(self):
        """✅ تبدیل تاریخ پایان (اعتبارسنجی رنج در clean کل فرم)"""
        end_date_str = self.cleaned_data.get('end_date')

        if not end_date_str:
            raise forms.ValidationError('تاریخ پایان الزامی است.')

        try:
            end_date = jalali_str_to_datetime(end_date_str)
        except (ValueError, Exception):
            raise forms.ValidationError('فرمت تاریخ پایان صحیح نیست.')

        return end_date

    def clean(self):
        cleaned_data = super().clean()
        platform = cleaned_data.get('platform')
        content_type = cleaned_data.get('content_type')
        ad_type = cleaned_data.get('ad_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        service_type = cleaned_data.get("content_service_type")
        minutes = cleaned_data.get("minutes")

        if start_date and end_date:
            try:
                validate_end_date(start_date, end_date)
            except forms.ValidationError as e:
                raise forms.ValidationError(str(e))

        if platform and content_type:
            if not content_type.platform.filter(id=platform.id).exists():
                raise forms.ValidationError(
                    'نوع محتوای انتخاب شده برای این پلتفرم معتبر نیست.'
                )

        if platform and ad_type:
            if ad_type.platform != platform:
                raise forms.ValidationError(
                    'نوع تبلیغ انتخاب شده برای این پلتفرم معتبر نیست.'
                )

        if content_type and content_type.slug == "content-production-team":

            if not service_type:
                raise forms.ValidationError("انتخاب نوع خدمت الزامی است.")

            if service_type.unit == "minute" and not minutes:
                raise forms.ValidationError("برای این خدمت وارد کردن دقیقه الزامی است.")

        else:
            cleaned_data["content_service_type"] = None
            cleaned_data["minutes"] = None

        return cleaned_data

    def get_platforms_json(self):
        result = {
            str(p.id): p.slug
            for p in Platform.objects.filter(is_active=True)
        }
        return json.dumps(result, ensure_ascii=False)

    def get_content_types_json(self):
        result = {}
        platforms = Platform.objects.filter(
            is_active=True
        ).prefetch_related('content_types')

        for platform in platforms:
            pid = str(platform.id)
            result[pid] = [
                {'id': ct.id, 'name': ct.name}
                for ct in platform.content_types.filter(is_active=True)
            ]

        return json.dumps(result, ensure_ascii=False)

    def get_ad_types_json(self):
        result = {}
        ad_types = AdType.objects.filter(
            is_active=True
        ).select_related('platform')

        for at in ad_types:
            pid = str(at.platform_id)
            if pid not in result:
                result[pid] = []
            result[pid].append({
                'id': at.id,
                'name': at.name,
            })

        return json.dumps(result, ensure_ascii=False)

    def get_service_types_json(self):
        result = {}

        services = ContentServiceType.objects.filter(
            is_active=True
        ).prefetch_related("ad_type")

        for service in services:
            for ad in service.ad_type.all():
                aid = str(ad.id)

                if aid not in result:
                    result[aid] = []

                result[aid].append({
                    "id": service.id,
                    "name": service.name,
                    "unit": service.unit
                })

        return json.dumps(result, ensure_ascii=False)

    def get_platforms_meta_json(self):
        result = {}

        platforms = Platform.objects.filter(is_active=True)

        for p in platforms:
            result[str(p.id)] = {
                "logo": p.logo.url if p.logo else "",
                "description": p.description or ""
            }

        return json.dumps(result, ensure_ascii=False)

    def get_content_types_meta_json(self):
        result = {}

        items = ContentType.objects.filter(is_active=True)

        for ct in items:
            result[str(ct.id)] = {
                "description": ct.description or "",
                "icon": ct.icon or "",
                "slug": ct.slug
            }

        return json.dumps(result, ensure_ascii=False)

    def get_ad_types_meta_json(self):
        result = {}

        items = AdType.objects.filter(is_active=True)

        for item in items:
            result[str(item.id)] = {
                "description": item.description or "",
                "icon": item.icon or "",
                "slug": item.slug
            }

        return json.dumps(result, ensure_ascii=False)

    def get_service_types_meta_json(self):
        result = {}

        items = ContentServiceType.objects.filter(is_active=True)

        for item in items:
            result[str(item.id)] = {
                "description": item.description or "",
                "icon": item.icon or "",
                "unit": item.unit,
                "unit_label": "قیمت این خدمت بر اساس دقیقه محاسبه می‌شود" if item.unit == "minute" else ""
            }

        return json.dumps(result, ensure_ascii=False)


class CampaignStep2Form(forms.Form):
    influencers = forms.ModelMultipleChoiceField(
        queryset=InfluencerProfile.objects.none(),
        label='اینفلوئنسرها',
        required=True,
        widget=forms.CheckboxSelectMultiple()
    )

    def __init__(self, *args, platform=None, **kwargs):
        super().__init__(*args, **kwargs)

        if platform:
            self.fields['influencers'].queryset = InfluencerProfile.objects.filter(
                platform=platform,
                is_active=True
            ).select_related('platform', 'category', 'province')

    def clean_influencers(self):
        influencers = self.cleaned_data.get('influencers')
        if not influencers:
            raise forms.ValidationError('حداقل یک اینفلوئنسر انتخاب کنید.')
        return influencers


class CampaignStep3TeamForm(forms.Form):
    """
    فرم انتخاب تیم تولید محتوا
    فقط مسئول انتخاب یک تیم (service rate) است
    """
    selected_rate = forms.ModelChoiceField(
        queryset=ContentServiceRate.objects.none(),
        label="انتخاب تیم",
        required=True,
        widget=forms.RadioSelect(),
        error_messages={
            'required': 'لطفاً یک تیم تولید محتوا انتخاب کنید.',
            'invalid_choice': 'تیم انتخاب‌شده معتبر نیست.',
        }
    )

    def __init__(self, *args, service_type=None, **kwargs):
        super().__init__(*args, **kwargs)

        if service_type:
            self.fields['selected_rate'].queryset = (
                ContentServiceRate.objects
                .filter(
                    service_type=service_type,
                    is_available=True,
                    team__is_active=True
                )
                .select_related("team", "service_type")
            )

    def clean_selected_rate(self):
        rate = self.cleaned_data.get("selected_rate")
        if not rate:
            raise forms.ValidationError("انتخاب تیم الزامی است.")
        return rate


class CampaignStep3BriefForm(forms.ModelForm):
    """
    فرم بریف ساختارمند سفارش تولید محتوا
    """

    ad_caption = forms.CharField(
        label="متن تبلیغ",
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-light',
            'rows': 5,
            'placeholder': 'متن تبلیغی که قرار است در پست اینفلوئنسر منتشر شود...',
            'id': 'id_ad_caption',
        }),
        error_messages={
            'required': 'لطفاً متن تبلیغ را وارد کنید.',
        }
    )

    ad_link = forms.URLField(
        label="لینک مقصد",
        required=True,
        widget=forms.URLInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': 'https://example.com/product',
            'id': 'id_ad_link',
        }),
        error_messages={
            'required': 'لطفاً لینک مقصد را وارد کنید.',
            'invalid': 'لطفاً یک آدرس معتبر وارد کنید.',
        }
    )

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

    def clean_description(self):
        description = self.cleaned_data.get("description", "").strip()
        if len(description) < 20:
            raise forms.ValidationError("توضیحات باید حداقل ۲۰ کاراکتر باشد.")
        return description

    def clean_goal_description(self):
        """
        اگر هدف 'سایر' انتخاب شد، توضیح الزامی است
        """
        goal = self.cleaned_data.get("goal")
        goal_description = self.cleaned_data.get("goal_description") or ""

        if goal == ContentOrderDescription.ContentGoal.OTHER and not goal_description.strip():
            raise forms.ValidationError(
                "چون «سایر» انتخاب کردید، لطفاً توضیح بدهید."
            )

        return goal_description

    def clean_ad_caption(self):
        caption = self.cleaned_data.get("ad_caption", "").strip()
        if len(caption) < 10:
            raise forms.ValidationError("متن تبلیغ باید حداقل ۱۰ کاراکتر باشد.")
        return caption

    def clean_ad_link(self):
        link = self.cleaned_data.get("ad_link", "").strip()
        if not link:
            raise forms.ValidationError("لطفاً لینک مقصد را وارد کنید.")
        return link


class CampaignStep3ReadyForm(forms.ModelForm):
    class Meta:
        model = CampaignContent
        fields = [
            "media",
            "caption",
            "link",
            "notes",
            "utm_enabled",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
        ]
        widgets = {
            "media": forms.FileInput(attrs={
                "class": "form-control form-control-light",
                "id": "id_media",
                "accept": "image/*,video/*",
                "style": "display: block;"
            }),
            "caption": forms.Textarea(attrs={
                "class": "form-control form-control-light",
                "id": "id_caption",
                "rows": 4,
                "placeholder": "متن کامل پست تبلیغاتی را وارد کنید"
            }),
            "link": forms.URLInput(attrs={
                "class": "form-control form-control-light",
                "id": "id_link",
                "placeholder": "https://example.com"
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control form-control-light",
                "id": "id_notes",
                "rows": 3,
                "placeholder": "توضیحات اضافی برای اینفلوئنسر"
            }),
            "utm_enabled": forms.CheckboxInput(attrs={
                "class": "form-check-input",
                "id": "id_utm_enabled",
            }),
            "utm_source": forms.TextInput(attrs={
                "class": "form-control form-control-light",
                "id": "id_utm_source",
                "placeholder": "instagram"
            }),
            "utm_medium": forms.TextInput(attrs={
                "class": "form-control form-control-light",
                "id": "id_utm_medium",
                "placeholder": "influencer"
            }),
            "utm_campaign": forms.TextInput(attrs={
                "class": "form-control form-control-light",
                "id": "id_utm_campaign",
                "placeholder": "summer_campaign"
            }),
            "utm_content": forms.TextInput(attrs={
                "class": "form-control form-control-light",
                "id": "id_utm_content",
                "placeholder": "story_ad"
            }),
            "utm_term": forms.TextInput(attrs={
                "class": "form-control form-control-light",
                "id": "id_utm_term",
                "placeholder": "optional"
            }),
        }
        labels = {
            "media": "فایل تبلیغ (عکس یا ویدیو)",
            "caption": "متن تبلیغ (Caption)",
            "link": "لینک مقصد",
            "notes": "توضیحات برای اینفلوئنسر",
            "utm_enabled": "فعال سازی UTM",
            "utm_source": "UTM Source",
            "utm_medium": "UTM Medium",
            "utm_campaign": "UTM Campaign",
            "utm_content": "UTM Content",
            "utm_term": "UTM Term",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # اینا رو غیر required می‌کنیم، خودمون هندلش می‌کنیم
        self.fields['utm_source'].required = False
        self.fields['utm_medium'].required = False
        self.fields['utm_campaign'].required = False
        self.fields['utm_content'].required = False
        self.fields['utm_term'].required = False

    def clean_media(self):
        media = self.cleaned_data.get("media")
        if not media:
            raise forms.ValidationError("آپلود فایل تبلیغ الزامی است.")
        if media.size > 50 * 1024 * 1024:
            raise forms.ValidationError("حجم فایل نباید بیشتر از 50 مگابایت باشد.")
        return media

    def clean(self):
        cleaned_data = super().clean()
        utm_enabled = cleaned_data.get("utm_enabled")
        link = cleaned_data.get("link")

        # 1. validation لینک
        if link and not link.startswith(("http://", "https://")):
            self.add_error("link", "لینک باید با http یا https شروع شود.")

        # 2. اگه utm فعال بود، فیلدها رو چک کن
        if utm_enabled:
            utm_source = cleaned_data.get("utm_source")
            utm_medium = cleaned_data.get("utm_medium")
            utm_campaign = cleaned_data.get("utm_campaign")
            utm_content = cleaned_data.get("utm_content")

            if not utm_source:
                self.add_error("utm_source", "وارد کردن UTM Source الزامی است.")
            if not utm_medium:
                self.add_error("utm_medium", "وارد کردن UTM Medium الزامی است.")
            if not utm_campaign:
                self.add_error("utm_campaign", "وارد کردن UTM Campaign الزامی است.")
            if not utm_content:
                self.add_error("utm_content", "وارد کردن UTM Content الزامی است.")

            # 3. اگه لینک داریم و utm فعاله، لینک رو تبدیل کن
            if link and not self.errors.get("link"):
                utm_params = {}
                if utm_source:
                    utm_params["utm_source"] = utm_source
                if utm_medium:
                    utm_params["utm_medium"] = utm_medium
                if utm_campaign:
                    utm_params["utm_campaign"] = utm_campaign
                if utm_content:
                    utm_params["utm_content"] = utm_content
                if cleaned_data.get("utm_term"):
                    utm_params["utm_term"] = cleaned_data.get("utm_term")

                if utm_params:
                    # ساخت لینک جدید با UTM
                    parsed = urlparse(link)
                    existing_query = parsed.query

                    # ترکیب query‌های موجود با UTM جدید (اولویت با UTM جدید)
                    from urllib.parse import parse_qs
                    existing_params = parse_qs(existing_query)

                    # تبدیل به flat dict (اولین مقدار هر کلید)
                    flat_existing = {k: v[0] for k, v in existing_params.items()}

                    # ادغام (UTM جدید override میکنه)
                    flat_existing.update(utm_params)

                    new_query = urlencode(flat_existing)
                    new_parsed = parsed._replace(query=new_query)
                    final_link = urlunparse(new_parsed)

                    cleaned_data["link"] = final_link

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance


class InfluencerFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'نام یا آیدی کانال',
        })
    )

    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label='همه دسته‌ها',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        })
    )

    province = forms.ModelChoiceField(
        queryset=Province.objects.all(),
        required=False,
        empty_label='همه استان‌ها',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        })
    )

    city = forms.ModelChoiceField(
        queryset=City.objects.none(),
        required=False,
        empty_label='همه شهرها',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        })
    )

    followers_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'فالوور از',
            'min': 0,
        })
    )

    followers_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'تا',
            'min': 0,
        })
    )

    price_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'قیمت از (تومان)',
            'min': 0,
        })
    )

    price_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'تا (تومان)',
            'min': 0,
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'province' in self.data and self.data['province']:
            try:
                province_id = int(self.data['province'])
                self.fields['city'].queryset = City.objects.filter(
                    province_id=province_id
                )
            except (ValueError, TypeError):
                pass
