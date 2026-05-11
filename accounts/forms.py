from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils.safestring import mark_safe
from .models import CustomUser
from django import forms


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


class ProfileUpdateForm(forms.ModelForm):
    """فرم ویرایش پروفایل کاربر (فقط ایمیل و نام مستعار)."""

    class Meta:
        model = CustomUser
        fields = ("nickname", "email", "avatar", 'sheba_code', "province",)
        labels = {
            "nickname": "نام کامل",
            "email": "پست الکترونیکی",
            "avatar": "تصویر پروفایل",
            'sheba_code': 'شماره شبا'
        }
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "placeholder": "example@mail.com",
                    "data-bs-binded-element": "#email-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "email-input",
                }
            ),
            "nickname": forms.TextInput(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "placeholder": "نام مستعار",
                    "data-bs-binded-element": "#name-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "name-input",
                }
            ),
            "province": forms.Select(
                attrs={
                    "class": "form-select form-select-light mt-3",
                    "data-bs-binded-element": "#province-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "id": "province-input",
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
            'sheba_code': forms.TextInput(
                attrs={
                    "class": "form-control form-control-light mt-3",
                    "placeholder": "شماره شبا بدون IR",
                    "id": "sheba-input",
                    "data-bs-binded-element": "#sheba-value",
                    "data-bs-unset-value": "مشخص نشده است",
                    "maxlength": "24",
                    "inputmode": "numeric",
                }
            ),
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
