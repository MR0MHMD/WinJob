# accounts/managers.py
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    مدیر سفارشی برای مدل User که از phone_number به جای username استفاده می‌کند.
    """

    def _create_user(self, phone_number, password, **extra_fields):
        """
        ایجاد و ذخیره کاربر با شماره تلفن و رمز عبور.
        """
        if not phone_number:
            raise ValueError(_('شماره تلفن باید وارد شود'))

        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        """
        ایجاد کاربر عادی.
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('سوپرکاربر باید is_staff=True داشته باشد'))

        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('سوپرکاربر باید is_superuser=True داشته باشد'))

        return self._create_user(phone_number, password, **extra_fields)
