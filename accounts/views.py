from content_team.models import ContentTeam, ContentTeamMember, TeamJoinRequest
from .services.registration_service import RegistrationService
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from influencers.forms import InfluencerProfileForm
from advertisers.forms import AdvertiserProfileForm
from django.contrib.auth import authenticate, login
from .forms import LoginForm, RegistrationForm
from django.shortcuts import render, redirect
from core.utils import generate_random_slug
from accounts.models import CustomUser
from .forms import ProfileUpdateForm
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from .models import Transaction


def login_view(request):
    """
    صفحه ورود و پردازش فرم ورود - یک ویو برای همه چیز!
    """
    # اگه کاربر لاگین کرده ببرش خونه
    if request.user.is_authenticated:
        return redirect('core:home')

    # درخواست GET - نمایش فرم
    if request.method != 'POST':
        form = LoginForm()
        return render(request, 'accounts/forms/login.html', {'login_form': form})

    # درخواست POST - پردازش فرم
    form = LoginForm(request.POST)

    if not form.is_valid():
        return render(request, 'accounts/forms/login.html', {
            'login_form': form,
            'error': 'لطفاً اطلاعات را به درستی وارد کنید'
        })

    phone_number = form.cleaned_data['phone_number']
    password = form.cleaned_data['password']
    user = authenticate(request, phone_number=phone_number, password=password)

    if user is None:
        return render(request, 'accounts/forms/login.html', {
            'login_form': form,
            'error': 'نام کاربری یا رمز عبور اشتباه است'
        })

    # لاگین موفق
    login(request, user)
    next_url = request.session.pop('next_url', None) or '/'

    # اگه درخواست AJAX بود
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "redirect_url": next_url})

    messages.success(request, f'خوش آمدید {user.nickname} 🙌')
    return redirect(next_url)


def register_view(request):
    """
    صفحه ثبت‌نام و پردازش فرم ثبت‌نام - یک ویو برای همه چیز!
    """
    # اگه کاربر لاگین کرده ببرش خونه
    if request.user.is_authenticated:
        return redirect('core:home')

    # درخواست GET - نمایش فرم
    if request.method != 'POST':
        form = RegistrationForm()
        return render(request, 'accounts/forms/register.html', {'register_form': form})

    # درخواست POST - پردازش فرم
    form = RegistrationForm(request.POST)

    if not form.is_valid():
        # نمایش خطاهای فرم
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return render(request, 'accounts/forms/register.html', {'register_form': form})

    # گرفتن اطلاعات از فرم
    phone = form.cleaned_data["phone_number"]
    nickname = form.cleaned_data["nickname"]
    password = form.cleaned_data["password"]
    role = form.cleaned_data["role"]

    try:
        with transaction.atomic():
            user = None

            if role == "advertiser":
                user, profile = RegistrationService.register_advertiser(
                    phone_number=phone,
                    password=password,
                    nickname=nickname
                )

            elif role == "influencer":
                user, profile = RegistrationService.register_influencer(
                    phone_number=phone,
                    password=password,
                    nickname=nickname
                )

            elif role == "team_member":
                create_new_team = form.cleaned_data.get("create_new_team")

                if create_new_team:
                    team_name = form.cleaned_data.get("team_name")
                    if not team_name:
                        messages.error(request, "لطفاً نام تیم را وارد کنید")
                        return render(request, 'accounts/forms/register.html', {'register_form': form})

                    new_team = ContentTeam.objects.create(
                        name=team_name,
                        slug=generate_random_slug(),
                        is_active=True
                    )
                    user, team_member = RegistrationService.register_team_member(
                        phone_number=phone,
                        password=password,
                        nickname=nickname,
                        team=new_team,
                        is_manager=True
                    )

                else:
                    team_slug = form.cleaned_data.get("team_slug")
                    if not team_slug:
                        messages.error(request, "لطفاً شناسه تیم را وارد کنید")
                        return render(request, 'accounts/forms/register.html', {'register_form': form})

                    # بررسی وجود تیم
                    try:
                        team = ContentTeam.objects.get(slug=team_slug, is_active=True)
                    except ContentTeam.DoesNotExist:
                        messages.error(request, "تیم مورد نظر یافت نشد. لطفاً شناسه تیم را بررسی کنید.")
                        return render(request, 'accounts/forms/register.html', {'register_form': form})

                    user = CustomUser.objects.create_user(
                        phone_number=phone,
                        password=password,
                        nickname=nickname
                    )

                    if ContentTeamMember.objects.filter(team=team, user=user).exists():
                        messages.error(request, "شما قبلاً عضو این تیم هستید.")
                        return render(request, 'accounts/forms/register.html', {'register_form': form})

                    existing_request = TeamJoinRequest.objects.filter(team=team, user=user).first()

                    if existing_request and existing_request.status == TeamJoinRequest.Status.PENDING:
                        messages.error(request, "شما قبلاً درخواست عضویت ثبت کرده‌اید. در انتظار تایید مدیر.")
                        return render(request, 'accounts/forms/register.html', {'register_form': form})

                    if existing_request and existing_request.status == TeamJoinRequest.Status.APPROVED:
                        messages.error(request, "شما قبلاً عضو این تیم شده‌اید.")
                        return render(request, 'accounts/forms/register.html', {'register_form': form})

                    TeamJoinRequest.objects.create(
                        team=team,
                        user=user,
                        status=TeamJoinRequest.Status.PENDING
                    )

                    messages.success(request,
                                     f"درخواست عضویت شما برای تیم {team.name} ثبت شد. پس از تایید مدیر می‌توانید وارد شوید.")

            # لاگین کاربر
            login(request, user)

            messages.success(request, f'خوش آمدید {user.nickname}! ثبت‌نام شما با موفقیت انجام شد. 🙌')
            return redirect('core:home')

    except Exception as e:
        messages.error(request, f"خطایی رخ داده است: {str(e)}")
        return render(request, 'accounts/forms/register.html', {'register_form': form})



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
        for transaction in current_page:
            # تعیین نوع آیکون
            trans_type = 'other'
            if transaction.type == 'deposit':
                trans_type = 'deposit'
            elif transaction.type == 'withdraw':
                trans_type = 'withdraw'
            elif transaction.type == 'purchase':
                trans_type = 'purchase'

            transactions_data.append({
                'id': transaction.id,
                'title': transaction.get_type_display(),
                'type': trans_type,
                'amount': transaction.amount,
                'is_income': transaction.is_income,
                'description': transaction.description if transaction.description else '',
                'date': transaction.created_at.strftime('%Y/%m/%d %H:%M'),
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
