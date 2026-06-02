from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from influencers.forms import InfluencerProfileForm
from advertisers.forms import AdvertiserProfileForm
from django.shortcuts import render, redirect
from accounts.forms import ProfileUpdateForm
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from accounts.models import Transaction


def advertiser_profile_edit_view(request):
    user = request.user
    user_form = ProfileUpdateForm(instance=user)

    profile_form = None
    profile = None

    if hasattr(user, "advertiser_profile"):
        profile = user.advertiser_profile
        profile_form = AdvertiserProfileForm(instance=profile)

    elif hasattr(user, "influencer_profile"):
        profile = user.influencer_profile
        profile_form = InfluencerProfileForm(instance=profile)

    user_fields_filled = 0
    total_user_fields = 3

    if user.nickname:
        user_fields_filled += 1

    if user.avatar:
        user_fields_filled += 1

    if user.email:
        user_fields_filled += 1

    profile_fields_filled = 0
    total_profile_fields = 0

    if profile:

        if hasattr(user, "advertiser_profile"):

            fields = [
                profile.business_name,
                profile.category,
                profile.description,
                profile.website
            ]

            total_profile_fields = len(fields)

            for f in fields:
                if f:
                    profile_fields_filled += 1

        elif hasattr(user, "influencer_profile"):

            fields = [
                profile.full_name,
                profile.description,
            ]

            total_profile_fields = len(fields)

            for f in fields:
                if f:
                    profile_fields_filled += 1

            # بررسی داشتن کانال
            if profile.channels.exists():
                profile_fields_filled += 1
            total_profile_fields += 1

            # بررسی داشتن نرخ
            if profile.channels.filter(service_rates__isnull=False).exists():
                profile_fields_filled += 1
            total_profile_fields += 1

    total_fields = total_user_fields + total_profile_fields
    filled_fields = user_fields_filled + profile_fields_filled

    completion_percentage = int((filled_fields / total_fields) * 100) if total_fields else 0

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
        "percentage": completion_percentage
    }

    return render(request, "accounts/forms/edit_profile.html", context)


@login_required
def wallet_dashboard(request):
    """
    صفحه اصلی کیف پول - نمایش موجودی و تراکنش‌ها
    """
    wallet = request.user.wallet

    # فقط 10 تراکنش اول رو نشون بده
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

        # گرفتن کل تراکنش‌ها
        all_transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')

        # ایجاد Paginator
        paginator = Paginator(all_transactions, per_page)

        # بررسی وجود صفحه
        if page > paginator.num_pages:
            return JsonResponse({
                'transactions': [],
                'has_more': False,
                'error': False
            })

        # گرفتن تراکنش‌های صفحه مورد نظر
        current_page = paginator.page(page)

        # ساخت دیتا برای JSON
        transactions_data = []
        for transaction_ in current_page:
            # تعیین نوع آیکون
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
