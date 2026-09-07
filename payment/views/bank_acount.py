from payment.utils.bank_detector import detect_bank_from_sheba, get_bank_info
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from payment.forms import BankAccountForm
from payment.models import BankAccount
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction


@login_required
def bank_account_list(request):
    """لیست حساب‌های بانکی کاربر"""

    is_influencer = hasattr(request.user, 'influencer_profile') and request.user.influencer_profile.is_active
    is_team_member = hasattr(request.user, 'team_member') and request.user.team_member.is_active

    if not is_influencer and not is_team_member:
        raise PermissionDenied("شما اجازه دسترسی به این بخش را ندارید.")

    bank_accounts = BankAccount.objects.filter(
        user=request.user
    ).order_by('-is_default', '-created_at')

    form = BankAccountForm(user=request.user)

    context = {
        'bank_accounts': bank_accounts,
        'has_default': bank_accounts.filter(is_default=True).exists(),
        'form': form,
        'total_accounts': bank_accounts.count(),
    }
    return render(request, 'payment/bank_account/bank_account_list.html', context)


@require_POST
@login_required
def bank_account_create_modal(request):
    """ثبت حساب بانکی از طریق مودال (AJAX)"""

    form = BankAccountForm(request.POST, user=request.user)

    if form.is_valid():
        try:
            with transaction.atomic():
                bank_account = form.save(commit=False)
                bank_account.user = request.user

                # ✅ تشخیص و اتصال بانک (توسط فرم انجام شده ولی برای اطمینان دوباره چک میکنیم)
                if not bank_account.bank:
                    bank = detect_bank_from_sheba(bank_account.sheba_code)
                    if bank:
                        bank_account.bank = bank
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': 'بانک مربوط به این شماره شبا شناسایی نشد. لطفاً شماره شبا را بررسی کنید.'
                        }, status=400)

                # اگر این حساب پیش‌فرض است، بقیه را غیرپیش‌فرض کن
                if bank_account.is_default:
                    BankAccount.objects.filter(
                        user=request.user,
                        is_default=True
                    ).exclude(pk=bank_account.pk).update(is_default=False)

                bank_account.save()

                # ✅ برگرداندن اطلاعات با دسترسی درست به bank
                return JsonResponse({
                    'success': True,
                    'message': 'حساب بانکی با موفقیت ثبت شد.',
                    'bank_id': bank_account.id,
                    'bank_name': bank_account.bank.name if bank_account.bank else None,
                    'bank_code': bank_account.bank.code if bank_account.bank else None,
                    'sheba_code': bank_account.sheba_code,
                    'is_default': bank_account.is_default,
                })

        except Exception as e:
            import traceback
            print(traceback.format_exc())  # برای دیباگ
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

    # خطاهای فرم
    error_messages = []
    for field, errors in form.errors.items():
        for error in errors:
            error_messages.append(f"{field}: {error}")

    return JsonResponse({
        'success': False,
        'message': ' | '.join(error_messages) if error_messages else 'خطا در اعتبارسنجی فرم'
    }, status=400)


@login_required
def detect_bank_api(request):
    """API تشخیص بانک از شماره شبا - با لوگو"""

    sheba = request.GET.get('sheba', '')

    bank_info = get_bank_info(sheba)

    if bank_info:
        return JsonResponse({
            'found': True,
            'bank_id': bank_info['id'],
            'bank_name': bank_info['name'],
            'bank_code': bank_info['code'],
            'logo_url': bank_info['logo_url'],
        })

    return JsonResponse({'found': False})


@login_required
@require_POST
def bank_account_delete(request, account_id):
    """حذف حساب بانکی"""

    bank_account = get_object_or_404(BankAccount, id=account_id, user=request.user)

    # جلوگیری از حذف تنها حساب کاربر
    if BankAccount.objects.filter(user=request.user).count() <= 1:
        messages.error(request, _('شما حداقل باید یک حساب بانکی داشته باشید.'))
        return redirect('payment:bank_account_list')

    was_default = bank_account.is_default
    bank_account.delete()

    # اگر حساب پیش‌فرض حذف شد، اولین حساب باقی‌مانده را پیش‌فرض کن
    if was_default:
        first_account = BankAccount.objects.filter(user=request.user).first()
        if first_account:
            first_account.is_default = True
            first_account.save()

    messages.success(request, _('حساب بانکی با موفقیت حذف شد.'))
    return redirect('payment:bank_account_list')


@login_required
@require_POST
def bank_account_set_default(request, account_id):
    """تنظیم حساب به عنوان پیش‌فرض"""

    bank_account = get_object_or_404(BankAccount, id=account_id, user=request.user)

    if not bank_account.is_verified:
        messages.error(
            request,
            _('فقط حساب‌های تأیید‌شده می‌توانند به عنوان پیش‌فرض تنظیم شوند.')
        )
        return redirect('payment:bank_account_list')

    with transaction.atomic():
        BankAccount.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)

        bank_account.is_default = True
        bank_account.save()

    messages.success(
        request,
        _('حساب بانکی «{bank_name}» به عنوان حساب پیش‌فرض تنظیم شد.').format(
            bank_name=bank_account.bank.name if bank_account.bank else 'بانک'
        )
    )

    return redirect('payment:bank_account_list')
