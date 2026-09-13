# accounts/models.py

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from django_resized import ResizedImageField
from .managers import CustomUserManager
from django.utils import timezone
from datetime import timedelta
from django.db import models
import random


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    مدل کاربر سفارشی
    - ورود با شماره تلفن
    - نقش‌های سازمانی از طریق فیلد role
    - امکان داشتن پروفایل تبلیغ‌دهنده/اینفلوئنسر/عضو تیم به صورت مستقل
    """

    # ==================== نقش‌های سازمانی ====================
    class Role(models.TextChoices):
        NONE = 'none', _('بدون نقش')
        CEO = 'ceo', _('مدیرعامل')
        DEVELOPER = 'developer', _('توسعه‌دهنده')
        CONTENT_MANAGER = 'content_manager', _('مدیر تولید محتوا')
        PUBLISH_MANAGER = 'publish_manager', _('مدیر نشر')
        REGIONAL_MANAGER = 'regional_manager', _('مدیر استانی')

    # ==================== فیلدهای اصلی ====================
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

    province = models.ForeignKey(
        "core.Province",
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name=_('استان'),
        null=True,
        blank=True
    )

    # ==================== فیلد نقش ====================
    role = models.CharField(
        _('نقش سازمانی'),
        max_length=30,
        choices=Role.choices,
        default=Role.NONE,
        db_index=True,
        help_text=_('نقش کاربر در پنل پشتیبانی و دسترسی‌ها')
    )

    # ==================== تاریخ‌ها ====================
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

    # ==================== Manager ====================
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

    # ==================== متدهای نمایشی ====================
    def display_sheba(self):
        if not self.sheba_code:
            return "-"

        raw = self.sheba_code.replace("IR", "").strip()

        first_two = raw[:2]
        rest = raw[2:]

        formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))

        return f"IR - {first_two} {formatted_rest}"

    # ==================== Properties: پروفایل‌ها ====================
    @property
    def is_advertiser(self):
        """آیا این کاربر پروفایل تبلیغ‌دهنده داره؟"""
        return hasattr(self, "advertiser_profile")

    @property
    def is_influencer(self):
        """آیا این کاربر پروفایل اینفلوئنسر داره؟"""
        return hasattr(self, "influencer_profile")

    @property
    def is_team_member(self):
        """آیا این کاربر عضو تیم تولید محتواست؟"""
        return hasattr(self, "team_member")

    # ==================== Properties: نقش‌های سازمانی ====================
    @property
    def is_ceo(self):
        """مدیرعامل"""
        return self.role == self.Role.CEO

    @property
    def is_developer(self):
        """توسعه‌دهنده"""
        return self.role == self.Role.DEVELOPER

    @property
    def is_content_manager(self):
        """مدیر تولید محتوا"""
        return self.role == self.Role.CONTENT_MANAGER

    @property
    def is_publish_manager(self):
        """مدیر نشر"""
        return self.role == self.Role.PUBLISH_MANAGER

    @property
    def is_regional_manager(self):
        """مدیر استانی (جایگزین فیلد قبلی)"""
        return self.role == self.Role.REGIONAL_MANAGER

    # ==================== Properties: دسترسی‌ها ====================
    @property
    def is_top_manager(self):
        """مدیرعامل یا توسعه‌دهنده - دسترسی کامل به همه چیز"""
        return self.role in [self.Role.CEO, self.Role.DEVELOPER]

    @property
    def has_support_access(self):
        """آیا به پنل پشتیبانی دسترسی داره؟"""
        return self.role in [
            self.Role.CEO,
            self.Role.DEVELOPER,
            self.Role.CONTENT_MANAGER,
            self.Role.PUBLISH_MANAGER,
            self.Role.REGIONAL_MANAGER,
        ]

    # ==================== Validation ====================
    def clean(self):
        """
        اعتبارسنجی‌های مدل:
        - مدیر استانی باید استان داشته باشد
        - هر استان فقط یک مدیر استانی
        """
        super().clean()

        if self.role == self.Role.REGIONAL_MANAGER:
            # چک ۱: داشتن استان
            if not self.province_id:
                raise ValidationError({
                    'province': _('مدیر استانی باید استان داشته باشد')
                })

            # چک ۲: یکتا بودن مدیر هر استان
            existing = CustomUser.objects.filter(
                role=self.Role.REGIONAL_MANAGER,
                province=self.province,
            ).exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'province': _(
                        f'استان «{self.province.name}» قبلاً یک مدیر استانی دارد'
                    )
                })

    def save(self, *args, **kwargs):
        # اجرای validation
        self.full_clean()
        super().save(*args, **kwargs)


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
