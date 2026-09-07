from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from payment.models import WithdrawalRequest


def validate_withdrawal_amount(amount, user):
    """اعتبارسنجی مبلغ تسویه"""

    # ۱. حداقل مبلغ (مثلاً ۱0۰,۰۰۰ تومان)
    min_amount = 100000
    if amount < min_amount:
        raise ValidationError(
            _('حداقل مبلغ قابل تسویه {min_amount:,} تومان است.').format(
                min_amount=min_amount
            )
        )

    # ۲. بررسی موجودی کیف پول
    wallet = user.wallet
    if amount > wallet.balance:
        raise ValidationError(
            _('موجودی کیف پول شما کافی نیست. موجودی فعلی: {balance:,} تومان').format(
                balance=wallet.balance
            )
        )

    # ۳. بررسی درخواست‌های تسویه‌ی در انتظار
    pending_count = WithdrawalRequest.objects.filter(
        user=user,
        status__in=[WithdrawalRequest.Status.PENDING, WithdrawalRequest.Status.PROCESSING]
    ).count()

    if pending_count >= 3:
        raise ValidationError(
            _('شما بیش از ۳ درخواست تسویه در انتظار دارید. لطفاً ابتدا آنها را پیگیری کنید.')
        )

    # ۴. بررسی فاصله زمانی بین درخواست‌ها (مثلاً ۲۴ ساعت)
    last_request = WithdrawalRequest.objects.filter(
        user=user,
        status=WithdrawalRequest.Status.COMPLETED
    ).order_by('-completed_at').first()

    if last_request and (timezone.now() - last_request.completed_at) < timedelta(hours=24):
        raise ValidationError(
            _('شما فقط هر ۲۴ ساعت یک بار می‌توانید درخواست تسویه ثبت کنید.')
        )
