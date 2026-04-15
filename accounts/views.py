from django.contrib.auth.decorators import login_required
from influencers.forms import InfluencerProfileForm
from advertisers.forms import AdvertiserProfileForm
from django.shortcuts import render, redirect
from .forms import ProfileUpdateForm
from django.contrib import messages
from django.db import transaction
from .models import Transaction


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
                profile.province,
                profile.city,
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

    # تراکنش‌های اخیر
    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]

    context = {
        'wallet': wallet,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'accounts/pages/wallet_dashboard.html', context)


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
