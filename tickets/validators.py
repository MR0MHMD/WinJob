from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_ticket_attachment_size(value):
    """
    اعتبارسنجی حجم فایل پیوست (حداکثر ۱۰ مگابایت)
    """
    max_size = 10 * 1024 * 1024  # 10MB

    if value.size > max_size:
        raise ValidationError(
            _('حجم فایل نمی‌تواند بیشتر از ۱۰ مگابایت باشد.')
        )
