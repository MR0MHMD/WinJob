from django.contrib.auth.forms import ReadOnlyPasswordHashField
from advertisers.models import AdvertiserProfile
from influencers.models import InfluencerProfile
from .models import CustomUser
from django import forms


COMMON_WIDGETS = {
    'class': 'form-control bg-transparent text-light',
}

class LoginForm(forms.Form):
    phone_number = forms.CharField(
        label='تلفن همراه',
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': '09123456789',
            'required': True
        })
    )
    password = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': 'پسوورد خود را وارد کنید',
            'required': True
        })
    )


class RegistrationForm(forms.Form):
    ROLE_CHOICES = (
        ("advertiser", "تبلیغ دهنده"),
        ("influencer", "ناشر"),
        ("team_member", "تیم تولید محتوا"),
    )

    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': '09123456789',
        })
    )

    nickname = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': 'نام مستعار',
        })
    )

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-light',
            'id': 'role-select'
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-light'
        })
    )

    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-light'
        })
    )

    team_slug = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': 'شناسه تیم را وارد کنید',
            'id': 'id_team_slug'
        })
    )

    create_new_team = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'create-new-team'
        })
    )

    team_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-light',
            'placeholder': 'نام تیم جدید',
            'id': 'id_team_name'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("password_confirm")
        role = cleaned_data.get("role")
        team_slug = cleaned_data.get("team_slug")
        create_new_team = cleaned_data.get("create_new_team")
        team_name = cleaned_data.get("team_name")

        if password != confirm:
            raise forms.ValidationError("رمز عبور و تایید آن یکسان نیست")

        # اعتبارسنجی برای نقش عضو تیم
        if role == "team_member":
            if not create_new_team and not team_slug:
                raise forms.ValidationError("لطفاً شناسه تیم را وارد کنید یا گزینه ساخت تیم جدید را انتخاب کنید")

            if create_new_team and not team_name:
                raise forms.ValidationError("لطفاً نام تیم جدید را وارد کنید")

            if not create_new_team and team_slug:
                # بررسی وجود تیم
                from content_team.models import ContentTeam
                if not ContentTeam.objects.filter(slug=team_slug, is_active=True).exists():
                    raise forms.ValidationError("تیم مورد نظر یافت نشد")

        return cleaned_data

    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        if not phone:
            raise forms.ValidationError("شماره تلفن الزامی است")
        if CustomUser.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("این شماره قبلاً ثبت شده است")
        return phone


class CustomUserCreationForm(forms.ModelForm):
    """فرم ساخت کاربر در ادمین"""

    password1 = forms.CharField(label="رمز عبور", widget=forms.PasswordInput)
    password2 = forms.CharField(label="تکرار رمز عبور", widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ("phone_number",)

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("رمزها یکسان نیستند")

        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

        return user


class CustomUserChangeForm(forms.ModelForm):
    """فرم ویرایش کاربر در ادمین"""

    password = ReadOnlyPasswordHashField(label="رمز عبور")

    class Meta:
        model = CustomUser
        fields = "__all__"

    def clean_password(self):
        return self.initial["password"]


class CustomUserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['nickname', 'email', 'avatar', 'sheba_code', 'province']
        widgets = {
            'nickname': forms.TextInput(attrs=COMMON_WIDGETS),
            'email': forms.EmailInput(attrs=COMMON_WIDGETS),
            'sheba_code': forms.TextInput(attrs={**COMMON_WIDGETS, 'dir': 'ltr', 'placeholder': 'شماره شبا بدون IR'}),
            'province': forms.Select(attrs={'class': 'form-select form-select-dark text-light border-secondary'}),
            'avatar': forms.FileInput(attrs={'class': 'd-none', 'id': 'avatar-upload', 'accept': 'image/*'}),
        }

    def clean_nickname(self):
        nickname = (self.cleaned_data.get("nickname") or "").strip()
        return nickname or None

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        return email or None

    def clean_sheba_code(self):
        sheba = self.cleaned_data.get("sheba_code", "")

        if not sheba:
            return None

        sheba = sheba.replace(" ", "").replace("-", "").replace("_", "").strip()

        sheba = sheba.upper()

        if sheba.startswith("IR"):
            sheba = sheba[2:]

        import re
        sheba = re.sub(r"[^0-9]", "", sheba)

        if len(sheba) != 24:
            raise forms.ValidationError("شماره شبا باید دقیقاً 24 رقم باشد.")

        return sheba


class AdvertiserProfileForm(forms.ModelForm):
    class Meta:
        model = AdvertiserProfile
        fields = ['business_name', 'category', 'description', 'website']
        widgets = {
            'business_name': forms.TextInput(attrs=COMMON_WIDGETS),
            'category': forms.Select(attrs={'class': 'form-select form-select-dark text-light border-secondary'}),
            'description': forms.Textarea(attrs={**COMMON_WIDGETS, 'rows': 4}),
            'website': forms.URLInput(attrs={**COMMON_WIDGETS, 'dir': 'ltr'}),
        }


class InfluencerProfileForm(forms.ModelForm):
    class Meta:
        model = InfluencerProfile
        fields = ['full_name', 'description']
        widgets = {
            'full_name': forms.TextInput(attrs=COMMON_WIDGETS),
            'description': forms.Textarea(attrs={**COMMON_WIDGETS, 'rows': 4}),
        }
