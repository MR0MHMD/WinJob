"""
سرویس واریز سهم کمیسیون به کیف پول کاربران

طراحی:
- ورودی اصلی: Invoice (چون هم کمپین و هم سفارش محتوا به Invoice وصلن)
- جلوگیری از دوبار واریز با commission_paid_at
- خطا در نبود کاربران اصلی (CEO, Dev, Managers)
- skip در نبود مدیر استانی (سهم به هزینه سایت اضافه می‌شه)
"""

from dataclasses import dataclass, field
from typing import Optional

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import CustomUser
from payment.models import Transaction, Wallet, Invoice, CommissionSplit
from payment.services.commission import (
    calculate_commission_breakdown,
    CommissionCalculationError,
)


# ==================== Exceptions ====================

class PayoutError(Exception):
    """خطا در واریز کمیسیون"""
    pass


# ==================== Data Classes ====================

@dataclass
class PayoutResult:
    """نتیجه واریز"""
    success: bool = False
    message: str = ''
    transactions: list = field(default_factory=list)
    skipped_roles: list = field(default_factory=list)
    total_paid: int = 0
    site_maintenance_final: int = 0

    def add_transaction(self, tx: Transaction, role: str):
        self.transactions.append({
            'role': role,
            'transaction_id': tx.id,
            'user_id': tx.user_id,
            'amount': tx.amount,
        })
        self.total_paid += tx.amount

    def add_skipped(self, role: str, reason: str):
        self.skipped_roles.append({
            'role': role,
            'reason': reason,
        })

    def __str__(self):
        return (
            f"PayoutResult(success={self.success}, "
            f"transactions={len(self.transactions)}, "
            f"total_paid={self.total_paid})"
        )


# ==================== Helper Functions ====================

def _find_user_by_role(role: str, province_id: Optional[int] = None) -> Optional[CustomUser]:
    """پیدا کردن کاربر بر اساس نقش"""
    queryset = CustomUser.objects.filter(role=role, is_active=True)

    if role == CustomUser.Role.REGIONAL_MANAGER:
        if not province_id:
            return None
        queryset = queryset.filter(province_id=province_id)

    users = list(queryset[:2])

    if len(users) > 1:
        raise PayoutError(
            f"بیش از یک کاربر با نقش {role} پیدا شد. لطفاً بررسی کنید."
        )

    return users[0] if users else None


def _require_user_by_role(role: str, role_label: str) -> CustomUser:
    """پیدا کردن کاربر با خطا در صورت نبود"""
    user = _find_user_by_role(role)
    if not user:
        raise PayoutError(
            f"کاربری با نقش «{role_label}» پیدا نشد. "
            f"لطفاً ابتدا این نقش را به یک کاربر اختصاص دهید."
        )
    return user


def _create_commission_transaction(
    user: CustomUser,
    amount: int,
    transaction_type: str,
    reference_id: str,
    description: str,
    campaign=None,
    invoice=None,
) -> Transaction:
    """ساخت Transaction و واریز به کیف پول"""
    if amount <= 0:
        raise PayoutError(f"مبلغ واریز باید مثبت باشد (دریافت‌شده: {amount})")

    tx = Transaction.objects.create(
        user=user,
        amount=amount,
        type=transaction_type,
        status=Transaction.Status.SUCCESS,
        campaign=campaign,
        invoice=invoice,
        reference_id=reference_id,
        description=description,
    )

    wallet, _ = Wallet.objects.get_or_create(user=user)
    wallet.balance += amount
    wallet.save(update_fields=['balance', 'updated_at'])

    return tx


# ==================== Main Service ====================

# noinspection PyTypeChecker
@transaction.atomic
def payout_commission(
    invoice: Invoice,
    campaign=None,
) -> PayoutResult:
    """
    واریز سهم کمیسیون به کیف پول کاربران

    Args:
        invoice: فاکتور مربوطه (کمپین یا سفارش محتوا)
        campaign: کمپین (اختیاری، برای لینک به Transaction)

    Returns:
        PayoutResult

    Raises:
        PayoutError: در صورت مشکل
    """
    result = PayoutResult()

    # ===== ۱. چک دوبار واریز =====
    if invoice.is_commission_paid:
        result.success = False
        result.message = f'کمیسیون فاکتور {invoice.invoice_number} قبلاً واریز شده است.'
        return result

    # ===== ۲. محاسبه breakdown =====
    try:
        # تشخیص نوع منبع
        if invoice.campaign_id:
            breakdown = calculate_commission_breakdown(
                source_id=invoice.campaign_id,
                source_type='campaign',
            )
        elif invoice.content_order_id:
            breakdown = calculate_commission_breakdown(
                source_id=invoice.content_order_id,
                source_type='content_order',
            )
        else:
            raise PayoutError(
                f'فاکتور {invoice.invoice_number} به هیچ کمپین یا سفارشی وصل نیست.'
            )
    except CommissionCalculationError as e:
        raise PayoutError(f'خطا در محاسبه کمیسیون: {e}')

    reference_base = f"COMMISSION-{invoice.invoice_number}"

    # ===== ۳. مدیرعامل (اجباری) =====
    if breakdown.ceo_amount > 0:
        ceo_user = _require_user_by_role(CustomUser.Role.CEO, 'مدیرعامل')
        tx = _create_commission_transaction(
            user=ceo_user,
            amount=breakdown.ceo_amount,
            transaction_type=Transaction.Type.COMMISSION_CEO,
            reference_id=f"{reference_base}-ceo",
            description=_(
                f"سهم مدیرعامل از کمیسیون فاکتور {invoice.invoice_number}"
            ),
            campaign=campaign,
            invoice=invoice,
        )
        result.add_transaction(tx, 'ceo')

    # ===== ۴. توسعه‌دهنده (اجباری) =====
    if breakdown.developer_amount > 0:
        dev_user = _require_user_by_role(CustomUser.Role.DEVELOPER, 'توسعه‌دهنده')
        tx = _create_commission_transaction(
            user=dev_user,
            amount=breakdown.developer_amount,
            transaction_type=Transaction.Type.COMMISSION_DEVELOPER,
            reference_id=f"{reference_base}-developer",
            description=_(
                f"سهم توسعه‌دهنده از کمیسیون فاکتور {invoice.invoice_number}"
            ),
            campaign=campaign,
            invoice=invoice,
        )
        result.add_transaction(tx, 'developer')

    # ===== ۵. مدیر نشر (اجباری - اگه سهم داشته باشه) =====
    if breakdown.publish_manager_amount > 0:
        publish_user = _require_user_by_role(CustomUser.Role.PUBLISH_MANAGER, 'مدیر نشر')
        tx = _create_commission_transaction(
            user=publish_user,
            amount=breakdown.publish_manager_amount,
            transaction_type=Transaction.Type.COMMISSION_PUBLISH_MANAGER,
            reference_id=f"{reference_base}-publish",
            description=_(
                f"سهم مدیر نشر از کمیسیون فاکتور {invoice.invoice_number}"
            ),
            campaign=campaign,
            invoice=invoice,
        )
        result.add_transaction(tx, 'publish_manager')

    # ===== ۶. مدیر محتوا (اجباری - اگه سهم داشته باشه) =====
    if breakdown.content_manager_amount > 0:
        content_user = _require_user_by_role(CustomUser.Role.CONTENT_MANAGER, 'مدیر تولید محتوا')
        tx = _create_commission_transaction(
            user=content_user,
            amount=breakdown.content_manager_amount,
            transaction_type=Transaction.Type.COMMISSION_CONTENT_MANAGER,
            reference_id=f"{reference_base}-content",
            description=_(
                f"سهم مدیر محتوا از کمیسیون فاکتور {invoice.invoice_number}"
            ),
            campaign=campaign,
            invoice=invoice,
        )
        result.add_transaction(tx, 'content_manager')

    # ===== ۷. مدیر استانی (اختیاری) =====
    site_maintenance_final = breakdown.site_maintenance_amount

    if breakdown.regional_manager_amount > 0:
        regional_user = _find_user_by_role(
            CustomUser.Role.REGIONAL_MANAGER,
            province_id=breakdown.advertiser_province_id,
        )

        if regional_user:
            tx = _create_commission_transaction(
                user=regional_user,
                amount=breakdown.regional_manager_amount,
                transaction_type=Transaction.Type.COMMISSION_REGIONAL_MANAGER,
                reference_id=f"{reference_base}-regional",
                description=_(
                    f"سهم مدیر استانی از کمیسیون فاکتور {invoice.invoice_number}"
                ),
                campaign=campaign,
                invoice=invoice,
            )
            result.add_transaction(tx, 'regional_manager')
        else:
            site_maintenance_final += breakdown.regional_manager_amount
            result.add_skipped(
                'regional_manager',
                f'مدیر استانی برای استان {breakdown.advertiser_province_id} پیدا نشد — '
                f'سهم به هزینه سایت اضافه شد'
            )

    # ===== ۸. ذخیره هزینه سایت نهایی =====
    result.site_maintenance_final = site_maintenance_final

    # ===== ۹. چک نهایی =====
    total_accounted = result.total_paid + site_maintenance_final
    if total_accounted != breakdown.total_commission:
        raise PayoutError(
            f"خطا در واریز: جمع واریز شده ({result.total_paid}) + "
            f"هزینه سایت ({site_maintenance_final}) = {total_accounted}، "
            f"ولی کل کمیسیون {breakdown.total_commission} است."
        )

    # ===== ۱۰. ذخیره تسهیم کمیسیون =====
    CommissionSplit.objects.create(
        invoice=invoice,
        ceo_amount=breakdown.ceo_amount,
        developer_amount=breakdown.developer_amount,
        publish_manager_amount=breakdown.publish_manager_amount,
        content_manager_amount=breakdown.content_manager_amount,
        regional_manager_amount=breakdown.regional_manager_amount,
        site_maintenance_amount=site_maintenance_final,
        snapshot=breakdown.setting_snapshot,
    )

    # ===== ۱۱. علامت‌گذاری فاکتور =====
    invoice.commission_paid_at = timezone.now()
    invoice.save(update_fields=['commission_paid_at'])

    # ===== ۱۱. نتیجه =====
    result.success = True
    result.message = (
        f'کمیسیون فاکتور {invoice.invoice_number} با موفقیت واریز شد. '
        f'(مجموع: {result.total_paid:,} تومان، هزینه سایت: {site_maintenance_final:,} تومان)'
    )

    return result
