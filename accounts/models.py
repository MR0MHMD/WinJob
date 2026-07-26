from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from django_resized import ResizedImageField
from .managers import CustomUserManager
from django.utils import timezone
from datetime import timedelta
from django.db import models
import random


class CustomUser(AbstractBaseUser, PermissionsMixin):
    bale_chat_id = models.CharField(
        _('شناسه ربات بله'),
        max_length=50,
        blank=True,
        null=True,
        unique=True
    )

    phone_number = models.CharField(
        _('شماره تماس'),
        max_length=11,
        unique=True
    )

    email = models.EmailField(
        _('ایمیل'),
        max_length=110,
        blank=True,
        null=True
    )

    nickname = models.CharField(
        _('نام مستعار'),
        max_length=50,
        blank=True,
        null=True
    )

    avatar = ResizedImageField(
        _('تصویر پروفایل'),
        upload_to="avatars/",
        size=[500, 500],
        scale=1,
        crop=['middle', 'center'],
        null=True,
        blank=True
    )

    sheba_code = models.CharField(_('شماره شبا'), max_length=24, null=True, blank=True)

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )

    is_staff = models.BooleanField(
        _('کارمند'),
        default=False
    )

    province = models.ForeignKey("core.Province", on_delete=models.CASCADE,
                                 related_name='accounts', verbose_name=_('استان'), null=True, blank=True)

    is_regional_manager = models.BooleanField(
        'مدیر استانی',
        default=False,
        help_text='اگر فعال باشد، کاربر فقط دسترسی به استان خودش را دارد'
    )

    date_joined = jmodels.jDateTimeField(
        _('تاریخ عضویت'),
        default=timezone.now
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('کاربر')
        verbose_name_plural = _('کاربران')
        ordering = ['-created_at']

    def __str__(self):
        return self.phone_number

    def get_full_name(self):
        return self.nickname

    def display_sheba(self):
        if not self.sheba_code:
            return "-"

        raw = self.sheba_code.replace("IR", "").strip()

        first_two = raw[:2]
        rest = raw[2:]

        formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))

        return f"IR - {first_two} {formatted_rest}"

    @property
    def is_advertiser(self):
        return hasattr(self, "advertiser_profile")

    @property
    def is_influencer(self):
        return hasattr(self, "influencer_profile")

    @property
    def is_team_member(self):
        return hasattr(self, "team_member")


class OTPRequest(models.Model):
    class OTPType(models.TextChoices):
        LOGIN = 'login', 'ورود'
        REGISTER = 'register', 'ثبت‌نام'
        VERIFY = 'verify', 'تایید عمومی'

    class OTPStatus(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        VERIFIED = 'verified', 'تایید شده'
        EXPIRED = 'expired', 'منقضی شده'

    phone_number = models.CharField(max_length=11, db_index=True)
    code = models.CharField(max_length=6)
    type = models.CharField(max_length=10, choices=OTPType.choices, default=OTPType.VERIFY)
    status = models.CharField(max_length=10, choices=OTPStatus.choices, default=OTPStatus.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    request_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = jmodels.jDateTimeField(auto_now_add=True)
    expires_at = jmodels.jDateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    # لاگ کامل برای API
    api_response = models.JSONField(default=dict, blank=True)
    api_status_code = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _('رمز یکبار مصرف')
        verbose_name_plural = _('رمز های یکبار مصرف')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=2)  # ۲ دقیقه اعتبار
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_verified(self):
        return self.status == self.OTPStatus.VERIFIED

    def can_resend(self):
        # بعد از ۲ دقیقه از ایجاد قبلی
        return timezone.now() > self.created_at + timedelta(minutes=2)

    @classmethod
    def generate_code(cls):
        return f"{random.randint(100000, 999999)}"

    @classmethod
    def get_active_otp(cls, phone_number):
        """دریافت OTP فعال برای شماره تلفن"""
        return cls.objects.filter(
            phone_number=phone_number,
            status=cls.OTPStatus.PENDING,
            expires_at__gt=timezone.now()
        ).first()

    def get_remaining_seconds(self):
        """دریافت ثانیه‌های باقیمانده تا انقضا"""
        if self.expires_at > timezone.now():
            return int((self.expires_at - timezone.now()).total_seconds())
        return 0

    def __str__(self):
        return f"{self.phone_number} - {self.code} - {self.get_type_display()}"
