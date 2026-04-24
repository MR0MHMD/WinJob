from django.views.decorators.http import require_GET, require_http_methods
from .services.registration_service import RegistrationService
from content_team.models import ContentTeam, TeamJoinRequest
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.csrf import csrf_exempt
from .services.otp_service import OTPGhasedakService
from influencers.forms import InfluencerProfileForm
from advertisers.forms import AdvertiserProfileForm
from django.contrib.auth import authenticate, login
from .forms import LoginForm, RegistrationForm
from django.shortcuts import render, redirect
from core.utils import generate_random_slug
from .models import OTPRequest, CustomUser
from .forms import ProfileUpdateForm
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import Transaction


def register_view(request):
    """
    صفحه ثبت‌نام - ابتدا اطلاعات رو گرفتن، بعد ریدایرکت به OTP
    """
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method != 'POST':
        form = RegistrationForm()
        return render(request, 'accounts/forms/register.html', {'register_form': form})

    form = RegistrationForm(request.POST)

    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return render(request, 'accounts/forms/register.html', {'register_form': form})

    phone_number = form.cleaned_data["phone_number"]
    nickname = form.cleaned_data["nickname"]

    # ذخیره اطلاعات فرم در session
    request.session['register_data'] = {
        'phone_number': phone_number,
        'nickname': nickname,
        'password': form.cleaned_data["password"],
        'role': form.cleaned_data["role"],
        'create_new_team': form.cleaned_data.get("create_new_team"),
        'team_name': form.cleaned_data.get("team_name"),
        'team_slug': form.cleaned_data.get("team_slug"),
    }

    # ارسال کد OTP با نام مستعار
    service = OTPGhasedakService()
    otp_obj, success, message, remaining_time = service.send_otp(
        phone_number=phone_number,
        otp_type=OTPRequest.OTPType.REGISTER,
        nickname=nickname
    )

    if not success:
        messages.error(request, message)
        return render(request, 'accounts/forms/register.html', {'register_form': form})

    # ذخیره زمان در session برای مواقعی که رفرش میشه
    request.session['otp_sent_at'] = timezone.now().isoformat()
    request.session['otp_remaining'] = remaining_time

    return redirect('accounts:verify_otp')


def login_view(request):
    """
    صفحه ورود با دو روش:
    1. شماره موبایل + رمز عبور (POST معمولی)
    2. شماره موبایل + کد OTP (AJAX)
    """
    global json
    if request.user.is_authenticated:
        return redirect('core:home')

    # درخواست GET - نمایش فرم
    if request.method == 'GET':
        form = LoginForm()
        return render(request, 'accounts/forms/login.html', {'login_form': form})

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not is_ajax:
        print("رمز عبور با موفقیت داره اجزا میشه")
        form = LoginForm(request.POST)

        if not form.is_valid():
            return render(request, 'accounts/forms/login.html', {
                'login_form': form,
                'error': 'لطفاً اطلاعات را به درستی وارد کنید'
            })

        phone_number = form.cleaned_data['phone_number']
        password = form.cleaned_data.get('password', '')

        if not password:
            return render(request, 'accounts/forms/login.html', {
                'login_form': form,
                'error': 'رمز عبور را وارد کنید'
            })

        user = authenticate(request, phone_number=phone_number, password=password)

        if user is not None:
            login(request, user)
            next_url = request.session.pop('next_url', None) or '/'
            messages.success(request, f'خوش آمدید {user.nickname} 🙌')
            return redirect(next_url)
        else:
            return render(request, 'accounts/forms/login.html', {
                'login_form': form,
                'error': 'شماره تلفن یا رمز عبور اشتباه است'
            })

    # ====== درخواست AJAX (ورود با OTP) ======
    try:
        if not request.body:
            return JsonResponse({'success': False, 'error': 'داده ارسالی خالی است'}, status=400)

        import json
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'داده ارسالی نامعتبر است'}, status=400)

    login_type = data.get('login_type', 'otp')
    phone_number = data.get('phone_number')

    if not phone_number:
        return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

    # ====== ورود با OTP ======
    if login_type == 'otp':
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            print(f"🔥 کاربر پیدا شد: {phone_number} | nickname: '{user.nickname}'")

            nickname_to_send = user.nickname if user.nickname else f"کاربر {phone_number[-4:]}"
            print(f"📤 nickname ارسالی: '{nickname_to_send}'")

        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'کاربری با این شماره یافت نشد. لطفاً ثبت‌نام کنید.'},
                                status=400)

        service = OTPGhasedakService()
        otp_obj, success, message, remaining_time = service.send_otp(
            phone_number=phone_number,
            otp_type=OTPRequest.OTPType.LOGIN,
            nickname=nickname_to_send
        )

        print(f"✅ نتیجه ارسال: success={success}, message={message}")

        if success:
            request.session['login_otp_data'] = {
                'phone_number': phone_number,
                'user_id': user.id,
            }
            return JsonResponse({
                'success': True,
                'message': 'کد تایید برای شما ارسال شد',
                'need_verify': True,
                'remaining_time': remaining_time
            })
        else:
            return JsonResponse({'success': False, 'error': message}, status=400)

    return JsonResponse({'success': False, 'error': 'درخواست نامعتبر'}, status=400)


@require_http_methods(["POST"])
@csrf_exempt
def login_otp_request_api(request):
    """API درخواست OTP برای لاگین"""
    import json

    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')

        if not phone_number:
            return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

        # بررسی وجود کاربر
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'کاربری با این شماره یافت نشد. لطفاً ثبت‌نام کنید.'
            }, status=400)

        # ارسال OTP
        nickname_to_send = user.nickname if user.nickname else f"کاربر {phone_number[-4:]}"
        service = OTPGhasedakService()
        otp_obj, success, message, remaining_time = service.send_otp(
            phone_number=phone_number,
            otp_type=OTPRequest.OTPType.LOGIN,
            nickname=nickname_to_send
        )

        if success:
            request.session['login_otp_data'] = {
                'phone_number': phone_number,
                'user_id': user.id,
            }
            return JsonResponse({
                'success': True,
                'message': 'کد تایید برای شما ارسال شد',
                'need_verify': True,
                'remaining_time': remaining_time
            })
        else:
            return JsonResponse({'success': False, 'error': message}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'داده ارسالی نامعتبر است'}, status=400)
    except Exception as e:
        print(f"خطا در login_otp_request_api: {str(e)}")
        return JsonResponse({'success': False, 'error': 'خطای داخلی سرور'}, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def check_user_exists_api(request):
    """API بررسی وجود کاربر با شماره تلفن"""
    import json
    data = json.loads(request.body)
    phone_number = data.get('phone_number')

    if not phone_number:
        return JsonResponse({'exists': False, 'error': 'شماره تلفن الزامی است'}, status=400)

    exists = CustomUser.objects.filter(phone_number=phone_number).exists()
    return JsonResponse({'exists': exists})


@require_http_methods(["POST"])
@csrf_exempt
def set_login_phone_api(request):
    """API ذخیره شماره تلفن برای لاگین با OTP"""
    import json
    data = json.loads(request.body)
    phone_number = data.get('phone_number')

    if not phone_number:
        return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

    # بررسی وجود کاربر
    try:
        user = CustomUser.objects.get(phone_number=phone_number)
        request.session['login_otp_data'] = {
            'phone_number': phone_number,
            'user_id': user.id,
        }
        return JsonResponse({'success': True})
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'کاربری با این شماره یافت نشد'}, status=400)


@require_http_methods(["POST"])
@csrf_exempt
def verify_login_otp_api(request):
    """API تایید کد OTP برای ورود"""
    import json
    data = json.loads(request.body)
    code = data.get('code')

    login_data = request.session.get('login_otp_data')
    if not login_data:
        return JsonResponse({'success': False, 'error': 'اطلاعات ورود یافت نشد'}, status=400)

    phone_number = login_data.get('phone_number')
    user_id = login_data.get('user_id')

    service = OTPGhasedakService()
    otp_obj, success, message = service.verify_otp(phone_number, code)

    if not success:
        return JsonResponse({'success': False, 'error': message})

    try:
        user = CustomUser.objects.get(id=user_id, phone_number=phone_number)
        login(request, user)

        del request.session['login_otp_data']
        if 'verified_phone' in request.session:
            del request.session['verified_phone']

        next_url = request.session.pop('next_url', None) or '/'
        return JsonResponse({
            'success': True,
            'message': f'خوش آمدید {user.nickname} 🙌',
            'redirect_url': next_url
        })
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'کاربر یافت نشد'}, status=400)


@require_http_methods(["POST"])
@csrf_exempt
def resend_login_otp_api(request):
    """API ارسال مجدد کد OTP برای ورود"""
    import json
    data = json.loads(request.body)
    phone_number = data.get('phone_number')

    if not phone_number:
        return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

    service = OTPGhasedakService()

    # بررسی زمان باقیمانده
    remaining_time = service.get_remaining_time(phone_number)
    if remaining_time > 0:
        return JsonResponse({
            'success': False,
            'error': f'لطفاً {remaining_time} ثانیه صبر کنید',
            'remaining_time': remaining_time
        }, status=400)

    try:
        user = CustomUser.objects.get(phone_number=phone_number)
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'کاربری با این شماره یافت نشد'}, status=400)

    otp_obj, success, message, new_remaining = service.send_otp(
        phone_number=phone_number,
        otp_type=OTPRequest.OTPType.LOGIN,
        nickname=user.nickname
    )

    if success:
        return JsonResponse({
            'success': True,
            'message': message,
            'remaining_time': new_remaining
        })
    else:
        return JsonResponse({
            'success': False,
            'error': message,
            'remaining_time': 0
        }, status=400)


def send_otp_api(request):
    """API ارسال کد OTP"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    import json
    data = json.loads(request.body)
    phone_number = data.get('phone_number')
    otp_type = data.get('type', OTPRequest.OTPType.VERIFY)

    if not phone_number:
        return JsonResponse({'error': 'شماره تلفن الزامی است'}, status=400)

    service = OTPGhasedakService()
    otp_obj, success, message, remaining_time = service.send_otp(phone_number, otp_type)

    return JsonResponse({
        'success': success,
        'message': message,
        'remaining_time': remaining_time if success else None
    })


def verify_otp_api(request):
    """API تایید کد OTP"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    import json
    data = json.loads(request.body)
    phone_number = data.get('phone_number')
    code = data.get('code')

    service = OTPGhasedakService()
    otp_obj, success, message = service.verify_otp(phone_number, code)

    if success:
        # ذخیره در session که شماره تایید شده
        request.session['verified_phone'] = phone_number
        request.session['verified_at'] = str(timezone.now())

    return JsonResponse({
        'success': success,
        'message': message
    })


# accounts/views.py - اصلاح verify_otp_view

def verify_otp_view(request):
    """
    صفحه تایید کد OTP - هم برای ثبت‌نامه و هم برای ورود
    """
    if request.user.is_authenticated:
        return redirect('core:home')

    # اول چک کن برای لاگین است
    login_data = request.session.get('login_otp_data')
    register_data = request.session.get('register_data')

    if not login_data and not register_data:
        messages.error(request, 'لطفاً ابتدا فرم مورد نظر را پر کنید')
        return redirect('accounts:login')

    # اگر برای لاگین است
    if login_data:
        phone_number = login_data.get('phone_number')
    else:
        phone_number = register_data.get('phone_number')

    service = OTPGhasedakService()
    remaining_time = service.get_remaining_time(phone_number)
    has_active = service.has_active_otp(phone_number)

    return render(request, 'accounts/forms/verify_otp.html', {
        'phone_number': phone_number,
        'remaining_time': remaining_time,
        'has_active_otp': has_active
    })

@require_http_methods(["POST"])
@csrf_exempt
def resend_otp_api(request):
    """API ارسال مجدد کد OTP"""
    import json
    data = json.loads(request.body)
    phone_number = data.get('phone_number')

    if not phone_number:
        return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

    service = OTPGhasedakService()

    # بررسی زمان باقیمانده از دیتابیس
    remaining_time = service.get_remaining_time(phone_number)
    if remaining_time > 0:
        return JsonResponse({
            'success': False,
            'error': f'لطفاً {remaining_time} ثانیه صبر کنید',
            'remaining_time': remaining_time
        }, status=400)

    # دریافت نام مستعار از session برای ارسال مجدد
    register_data = request.session.get('register_data', {})
    nickname = register_data.get('nickname')

    otp_obj, success, message, new_remaining = service.send_otp(
        phone_number=phone_number,
        otp_type=OTPRequest.OTPType.REGISTER,
        nickname=nickname
    )

    if success:
        return JsonResponse({
            'success': True,
            'message': message,
            'remaining_time': new_remaining
        })
    else:
        return JsonResponse({
            'success': False,
            'error': message,
            'remaining_time': 0
        }, status=400)


@require_http_methods(["POST"])
@csrf_exempt
def get_otp_status_api(request):
    """API دریافت وضعیت OTP (زمان باقیمانده)"""
    import json
    data = json.loads(request.body)
    phone_number = data.get('phone_number')

    if not phone_number:
        return JsonResponse({'error': 'شماره تلفن الزامی است'}, status=400)

    service = OTPGhasedakService()
    remaining_time = service.get_remaining_time(phone_number)

    return JsonResponse({
        'remaining_time': remaining_time,
        'has_active': remaining_time > 0
    })


@require_http_methods(["POST"])
@csrf_exempt
def complete_registration_api(request):
    """API تکمیل ثبت‌نامه بعد از تایید OTP"""
    import json
    data = json.loads(request.body)
    code = data.get('code')

    login_data = request.session.get('login_otp_data')
    register_data = request.session.get('register_data')

    if not login_data and not register_data:
        return JsonResponse({'success': False, 'error': 'اطلاعات یافت نشد'}, status=400)

    if login_data:
        phone = login_data.get('phone_number')
        user_id = login_data.get('user_id')

        service = OTPGhasedakService()
        otp_obj, success, message = service.verify_otp(phone, code)

        if not success:
            return JsonResponse({'success': False, 'error': message})

        try:
            user = CustomUser.objects.get(id=user_id, phone_number=phone)
            login(request, user)

            del request.session['login_otp_data']

            next_url = request.session.pop('next_url', None) or '/'
            return JsonResponse({
                'success': True,
                'message': f'خوش آمدید {user.nickname} 🙌',
                'redirect_url': next_url
            })
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'کاربر یافت نشد'}, status=400)
    else:
        register_data = request.session.get('register_data')
        if not register_data:
            return JsonResponse({'success': False, 'error': 'اطلاعات ثبت‌نامه یافت نشد'}, status=400)

        phone = register_data.get('phone_number')

        service = OTPGhasedakService()
        otp_obj, success, message = service.verify_otp(phone, code)

        if not success:
            return JsonResponse({'success': False, 'error': message})

        try:
            with transaction.atomic():
                nickname = register_data.get('nickname')
                password = register_data.get('password')
                role = register_data.get('role')

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
                    create_new_team = register_data.get('create_new_team')

                    if create_new_team:
                        team_name = register_data.get('team_name')
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
                        team_slug = register_data.get('team_slug')
                        team = ContentTeam.objects.get(slug=team_slug, is_active=True)

                        user = CustomUser.objects.create_user(
                            phone_number=phone,
                            password=password,
                            nickname=nickname
                        )

                        existing_request = TeamJoinRequest.objects.filter(team=team, user=user).first()

                        if not existing_request or existing_request.status != TeamJoinRequest.Status.PENDING:
                            TeamJoinRequest.objects.create(
                                team=team,
                                user=user,
                                status=TeamJoinRequest.Status.PENDING
                            )

                login(request, user)

                # پاک کردن session
                del request.session['register_data']
                if 'otp_sent_at' in request.session:
                    del request.session['otp_sent_at']
                if 'otp_remaining' in request.session:
                    del request.session['otp_remaining']

                return JsonResponse({
                    'success': True,
                    'message': 'ثبت‌نام با موفقیت انجام شد',
                    'redirect_url': '/'
                })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
