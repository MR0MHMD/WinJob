from django.views.decorators.http import require_POST
from payment.services.withdrawal_service import WithdrawalService
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from payment.models import WithdrawalRequest, BankAccount
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError, PermissionDenied
from payment.forms import WithdrawalRequestForm
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


def _check_access(user):
    is_influencer = hasattr(user, 'influencer_profile') and user.influencer_profile.is_active
    is_team_member = hasattr(user, 'team_member') and user.team_member.is_active
    return is_influencer or is_team_member


@login_required
def withdrawal_list(request):
    if not _check_access(request.user):
        raise PermissionDenied("شما اجازه دسترسی به این بخش را ندارید.")

    qs = WithdrawalRequest.objects.filter(
        user=request.user
    ).select_related('bank_account', 'bank_account__bank', 'transaction').order_by('-requested_at')

    # فیلترها
    status = request.GET.get('status')
    wtype = request.GET.get('type')
    search = request.GET.get('q', '').strip()

    if status:
        qs = qs.filter(status=status)
    if wtype:
        qs = qs.filter(withdrawal_type=wtype)
    if search:
        qs = qs.filter(
            Q(tracking_code__icontains=search) |
            Q(amount__icontains=search.replace(',', ''))
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # آمار (از کل درخواست‌های کاربر)
    all_withdrawals = WithdrawalRequest.objects.filter(user=request.user)
    total_pending = all_withdrawals.filter(
        status__in=[WithdrawalRequest.Status.PENDING, WithdrawalRequest.Status.PROCESSING]
    ).count()
    total_completed = all_withdrawals.filter(status=WithdrawalRequest.Status.COMPLETED).count()
    total_rejected = all_withdrawals.filter(status=WithdrawalRequest.Status.REJECTED).count()

    context = {
        'page_obj': page_obj,
        'total_pending': total_pending,
        'total_completed': total_completed,
        'total_rejected': total_rejected,
        'wallet_balance': request.user.wallet.balance,
        'current_status': status or '',
        'current_type': wtype or '',
        'search_query': search,
    }
    return render(request, 'payment/withdrawal/withdrawal_list.html', context)


@login_required
def withdrawal_create(request):
    if not _check_access(request.user):
        raise PermissionDenied("شما اجازه دسترسی به این بخش را ندارید.")

    bank_accounts = BankAccount.objects.filter(
        user=request.user,
        is_verified=True
    ).select_related('bank').order_by('-is_default', '-created_at')

    if not bank_accounts.exists():
        messages.warning(request, _('لطفاً ابتدا یک حساب بانکی تأیید شده ثبت کنید.'))
        return redirect('payment:bank_account_list')

    if request.method == 'POST':
        form = WithdrawalRequestForm(request.POST)
        bank_account_id = request.POST.get('bank_account')

        if form.is_valid():
            try:
                if not bank_account_id:
                    raise ValueError(_('لطفاً یک حساب بانکی انتخاب کنید.'))

                withdrawal = WithdrawalService.create_withdrawal_request(
                    user=request.user,
                    bank_account_id=bank_account_id,
                    amount=form.cleaned_data['amount'],
                    description=form.cleaned_data.get('description', '')
                )

                messages.success(
                    request,
                    _('درخواست تسویه شما با موفقیت ثبت شد. کد پیگیری: {code}').format(
                        code=withdrawal.tracking_code
                    )
                )
                return redirect('payment:withdrawal_detail', withdrawal_id=withdrawal.id)

            except (ValueError, ValidationError) as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Unexpected error in withdrawal_create: {e}", exc_info=True)
                messages.error(request, _('خطا در ثبت درخواست. لطفاً دوباره تلاش کنید.'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = WithdrawalRequestForm()

    is_influencer = hasattr(request.user, 'influencer_profile') and request.user.influencer_profile.is_active

    context = {
        'form': form,
        'bank_accounts': bank_accounts,
        'wallet_balance': request.user.wallet.balance,
        'user_type': 'influencer' if is_influencer else 'team_member',
        'min_amount': WithdrawalService.MIN_AMOUNT,
    }
    return render(request, 'payment/withdrawal/withdrawal_create.html', context)


@login_required
def withdrawal_detail(request, withdrawal_id):
    withdrawal = get_object_or_404(
        WithdrawalRequest.objects.select_related(
            'bank_account', 'bank_account__bank', 'transaction'
        ),
        id=withdrawal_id,
        user=request.user
    )
    context = {
        'withdrawal': withdrawal,
    }
    return render(request, 'payment/withdrawal/withdrawal_detail.html', context)


@require_POST
@login_required
def withdrawal_cancel(request, withdrawal_id):
    try:
        WithdrawalService.cancel_withdrawal(withdrawal_id, request.user)
        messages.success(request, _('درخواست تسویه با موفقیت لغو شد.'))
    except (ValueError, ValidationError) as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Error cancelling withdrawal: {e}", exc_info=True)
        messages.error(request, _('خطا در لغو درخواست.'))

    return redirect('payment:withdrawal_detail', withdrawal_id=withdrawal_id)
