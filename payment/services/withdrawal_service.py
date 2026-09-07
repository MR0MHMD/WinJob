# payment/services/withdrawal_service.py

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from ..models import WithdrawalRequest, BankAccount, Transaction, Wallet


class WithdrawalService:
    """سرویس مدیریت تسویه حساب"""

    MIN_AMOUNT = 100_000  # حداقل مبلغ تسویه (تومان)

    @classmethod
    def _determine_withdrawal_type(cls, user):
        """
        تعیین نوع تسویه بر اساس نقش کاربر
        """
        if hasattr(user, 'influencer_profile') and user.influencer_profile.is_active:
            return WithdrawalRequest.Type.INFLUENCER

        if hasattr(user, 'team_member') and user.team_member.is_active:
            return WithdrawalRequest.Type.CONTENT_TEAM

        raise ValidationError(
            _('شما دسترسی به تسویه حساب ندارید. لطفاً ابتدا پروفایل خود را تکمیل کنید.')
        )

    @classmethod
    def create_withdrawal_request(cls, user, bank_account_id, amount, description=''):
        """
        ایجاد درخواست تسویه جدید
        - مبلغ فوراً از کیف پول کم می‌شود
        - تراکنش با وضعیت PENDING ایجاد می‌شود
        """
        from ..validators import validate_withdrawal_amount

        # اعتبارسنجی کامل (حداقل مبلغ + موجودی + تعداد pending + فاصله زمانی)
        validate_withdrawal_amount(amount, user)

        try:
            bank_account = BankAccount.objects.select_related('bank').get(
                id=bank_account_id,
                user=user,
                is_verified=True
            )
        except BankAccount.DoesNotExist:
            raise ValueError(_('حساب بانکی معتبر یافت نشد.'))

        withdrawal_type = cls._determine_withdrawal_type(user)

        with transaction.atomic():
            # قفل کیف پول برای جلوگیری از race condition
            wallet = Wallet.objects.select_for_update().get(user=user)

            # بررسی مجدد موجودی
            if wallet.balance < amount:
                raise ValidationError(
                    _('موجودی کیف پول کافی نیست. (موجودی فعلی: {balance:,} تومان)').format(
                        balance=wallet.balance
                    )
                )

            # کم کردن موجودی همین الان
            wallet.balance -= amount
            wallet.save(update_fields=['balance'])

            # ایجاد درخواست تسویه
            withdrawal = WithdrawalRequest.objects.create(
                user=user,
                bank_account=bank_account,
                withdrawal_type=withdrawal_type,
                amount=amount,
                description=description or '',
                status=WithdrawalRequest.Status.PENDING
            )

            # تعیین نوع تراکنش
            trx_type = (
                Transaction.Type.INFLUENCER_WITHDRAWAL
                if withdrawal_type == WithdrawalRequest.Type.INFLUENCER
                else Transaction.Type.CONTENT_TEAM_WITHDRAWAL
            )

            # ایجاد تراکنش
            trx = Transaction.objects.create(
                user=user,
                amount=amount,
                type=trx_type,
                status=Transaction.Status.PENDING,
                description=f'درخواست تسویه #{withdrawal.tracking_code}',
            )

            # اتصال تراکنش به درخواست
            withdrawal.transaction = trx
            withdrawal.save(update_fields=['transaction'])

        return withdrawal

    @classmethod
    def cancel_withdrawal(cls, withdrawal_id, user):
        """
        لغو درخواست توسط کاربر
        → مبلغ به کیف پول برگردانده می‌شود
        """
        try:
            withdrawal = WithdrawalRequest.objects.select_related('transaction').get(
                id=withdrawal_id,
                user=user,
                status=WithdrawalRequest.Status.PENDING
            )
        except WithdrawalRequest.DoesNotExist:
            raise ValueError(_('درخواست تسویه یافت نشد یا قابل لغو نیست.'))

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)

            # برگرداندن مبلغ
            wallet.balance += withdrawal.amount
            wallet.save(update_fields=['balance'])

            # تغییر وضعیت درخواست
            withdrawal.status = WithdrawalRequest.Status.CANCELLED
            withdrawal.save(update_fields=['status'])

            # تغییر وضعیت تراکنش
            if withdrawal.transaction:
                withdrawal.transaction.status = Transaction.Status.CANCELLED
                withdrawal.transaction.save(update_fields=['status'])

        return withdrawal

    @classmethod
    def approve_withdrawal(cls, withdrawal_id, admin_user, admin_note=''):
        """
        تأیید درخواست توسط ادمین
        → فقط وضعیت تغییر می‌کند (مبلغ قبلاً کم شده)
        """
        try:
            withdrawal = WithdrawalRequest.objects.select_related(
                'user', 'transaction', 'bank_account'
            ).get(
                id=withdrawal_id,
                status=WithdrawalRequest.Status.PENDING
            )
        except WithdrawalRequest.DoesNotExist:
            raise ValueError(_('درخواست تسویه یافت نشد یا قبلاً پردازش شده است.'))

        with transaction.atomic():
            withdrawal.status = WithdrawalRequest.Status.COMPLETED
            withdrawal.processed_at = timezone.now()
            withdrawal.completed_at = timezone.now()
            withdrawal.admin_note = admin_note

            if withdrawal.transaction:
                withdrawal.transaction.status = Transaction.Status.SUCCESS
                withdrawal.transaction.reference_id = (
                    f"ADMIN-{admin_user.id}-{int(timezone.now().timestamp())}"
                )
                withdrawal.transaction.save()

            withdrawal.save()

            # TODO: ارسال نوتیفیکیشن به کاربر

        return withdrawal

    @classmethod
    def reject_withdrawal(cls, withdrawal_id, admin_note=''):
        """
        رد درخواست توسط ادمین
        → مبلغ به کیف پول برگردانده می‌شود
        """
        try:
            withdrawal = WithdrawalRequest.objects.select_related(
                'transaction', 'user'
            ).get(
                id=withdrawal_id,
                status=WithdrawalRequest.Status.PENDING
            )
        except WithdrawalRequest.DoesNotExist:
            raise ValueError(_('درخواست تسویه یافت نشد.'))

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)

            # برگرداندن مبلغ
            wallet.balance += withdrawal.amount
            wallet.save(update_fields=['balance'])

            withdrawal.status = WithdrawalRequest.Status.REJECTED
            withdrawal.admin_note = admin_note
            withdrawal.processed_at = timezone.now()

            if withdrawal.transaction:
                withdrawal.transaction.status = Transaction.Status.FAILED
                withdrawal.transaction.save(update_fields=['status'])

            withdrawal.save()

            # TODO: ارسال نوتیفیکیشن به کاربر

        return withdrawal
