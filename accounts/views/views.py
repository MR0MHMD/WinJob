from ..forms import CustomUserForm, AdvertiserProfileForm, InfluencerProfileForm
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from influencers.forms import InfluencerProfileForm
from advertisers.forms import AdvertiserProfileForm
from django.shortcuts import render, redirect
from accounts.models import Transaction
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction


@login_required
def edit_profile(request):
    user = request.user

    user_form = CustomUserForm(instance=user)
    profile_form = None

    if user.is_advertiser:
        profile_form = AdvertiserProfileForm(instance=user.advertiser_profile)
    elif user.is_influencer:
        profile_form = InfluencerProfileForm(instance=user.influencer_profile)

    if request.method == 'POST':
        user_form = CustomUserForm(request.POST, request.FILES, instance=user)

        if user.is_advertiser:
            profile_form = AdvertiserProfileForm(request.POST, instance=user.advertiser_profile)
        elif user.is_influencer:
            profile_form = InfluencerProfileForm(request.POST, instance=user.influencer_profile)

        if user_form.is_valid() and (not profile_form or profile_form.is_valid()):
            user_form.save()
            if profile_form:
                profile_form.save()

            messages.success(request, 'اطلاعات پروفایل با موفقیت بروزرسانی شد!')
            return redirect('accounts:edit_profile')
        else:
            messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'accounts/forms/edit_profile.html', context)


@login_required
def wallet_dashboard(request):
    """
    صفحه اصلی کیف پول - نمایش موجودی و تراکنش‌ها
    """
    wallet = request.user.wallet

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]

    context = {
        'wallet': wallet,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'accounts/pages/wallet_dashboard.html', context)


@login_required
@require_GET
def load_more_transactions(request):
    """
    API برای لود تراکنش‌های بیشتر (Ajax)
    فقط 10 تای بعدی رو برمیگردونه
    """
    try:
        page = int(request.GET.get('page', 1))
        per_page = 5

        all_transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')

        paginator = Paginator(all_transactions, per_page)

        if page > paginator.num_pages:
            return JsonResponse({
                'transactions': [],
                'has_more': False,
                'error': False
            })

        current_page = paginator.page(page)

        transactions_data = []
        for transaction_ in current_page:
            trans_type = 'other'
            if transaction_.type == 'deposit':
                trans_type = 'deposit'
            elif transaction_.type == 'withdraw':
                trans_type = 'withdraw'
            elif transaction_.type == 'purchase':
                trans_type = 'purchase'

            transactions_data.append({
                'id': transaction_.id,
                'title': transaction_.get_type_display(),
                'type': trans_type,
                'amount': transaction_.amount,
                'is_income': transaction_.is_income,
                'description': transaction_.description if transaction_.description else '',
                'date': transaction_.created_at.strftime('%Y/%m/%d %H:%M'),
            })

        return JsonResponse({
            'transactions': transactions_data,
            'has_more': current_page.has_next(),
            'current_page': page,
            'error': False
        })

    except EmptyPage:
        return JsonResponse({
            'transactions': [],
            'has_more': False,
            'error': False
        })
    except Exception as e:
        print(f"Error in load_more_transactions: {e}")
        return JsonResponse({
            'transactions': [],
            'has_more': False,
            'error': True,
            'message': str(e)
        })


@login_required
def wallet_deposit(request):
    """
    صفحه شارژ کیف پول (تستی - بدون درگاه)
    """
    if request.method == 'POST':
        amount = request.POST.get('amount')

        try:
            amount = int(amount)
            if amount < 1000:
                messages.error(request, "حداقل مبلغ شارژ ۱,۰۰۰ تومان است.")
                return redirect('accounts:wallet_deposit')

            if amount > 50000000:
                messages.error(request, "حداکثر مبلغ شارژ ۵۰,۰۰۰,۰۰۰ تومان است.")
                return redirect('accounts:wallet_deposit')

        except (ValueError, TypeError):
            messages.error(request, "مبلغ وارد شده معتبر نیست.")
            return redirect('accounts:wallet_deposit')

        with transaction.atomic():
            wallet = request.user.wallet
            wallet.balance += amount
            wallet.save(update_fields=['balance'])

            Transaction.objects.create(
                user=request.user,
                amount=amount,
                type=Transaction.Type.DEPOSIT,
                status=Transaction.Status.SUCCESS,
                description=f"شارژ آزمایشی کیف پول - مبلغ {amount:,} تومان"
            )

        messages.success(request, f"کیف پول شما به مبلغ {amount:,} تومان شارژ شد.")
        return redirect('accounts:wallet_dashboard')

    return render(request, 'accounts/forms/wallet_deposit.html')
