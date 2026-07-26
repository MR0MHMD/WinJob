from ..services.registration_service import RegistrationService
from content_team.models import ContentTeam, TeamJoinRequest
from ..services.otp_service import OTPGhasedakService, logger
from django.contrib.auth import authenticate, login
from core.utils.utils import generate_random_slug
from django.shortcuts import render, redirect
from ..models import OTPRequest, CustomUser
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from ..forms import LoginForm
import json


def handle_password_login(request):
    """پردازش ورود با رمز عبور"""
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

    if user is None:
        return render(request, 'accounts/forms/login.html', {
            'login_form': form,
            'error': 'شماره تلفن یا رمز عبور اشتباه است'
        })

    login(request, user)
    next_url = request.session.pop('next_url', None) or '/'
    messages.success(request, f'خوش آمدید {user.nickname} 🙌')
    return redirect(next_url)


def handle_ajax_login(request):
    """پردازش درخواست OTP از طریق AJAX"""
    try:
        if not request.body:
            return JsonResponse({'success': False, 'error': 'داده ارسالی خالی است'}, status=400)

        data = json.loads(request.body)
        phone_number = data.get('phone_number')

        if not phone_number:
            return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'کاربری با این شماره یافت نشد. لطفاً ثبت‌نام کنید.'
            }, status=400)

        nickname = user.nickname or f"کاربر {phone_number[-4:]}"

        service = OTPGhasedakService()
        otp_obj, success, message, remaining_time = service.send_otp(
            phone_number=phone_number,
            otp_type=OTPRequest.OTPType.LOGIN,
            nickname=nickname
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


def handle_login_verification(request, login_data, code):
    """تایید OTP و ورود کاربر"""
    phone = login_data.get('phone_number')
    user_id = login_data.get('user_id')

    service = OTPGhasedakService()
    otp_obj, success, message = service.verify_otp(phone, code)

    if not success:
        return JsonResponse({'success': False, 'error': message})

    try:
        user = CustomUser.objects.get(id=user_id, phone_number=phone)
        login(request, user)

        # پاکسازی session
        cleanup_session(request)

        next_url = request.session.pop('next_url', None) or '/'
        return JsonResponse({
            'success': True,
            'message': f'خوش آمدید {user.nickname} 🙌',
            'redirect_url': next_url
        })
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'کاربر یافت نشد'}, status=400)


def handle_register_verification(request, register_data, code):
    """تایید OTP و تکمیل ثبت‌نام"""
    phone = register_data.get('phone_number')

    service = OTPGhasedakService()
    otp_obj, success, message = service.verify_otp(phone, code)

    if not success:
        return JsonResponse({'success': False, 'error': message})

    try:
        with transaction.atomic():

            user = create_user_by_role(register_data)

            login(request, user)
            cleanup_session(request)

            return JsonResponse({
                'success': True,
                'message': 'ثبت‌نام با موفقیت انجام شد',
                'redirect_url': '/'
            })

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'خطا در ثبت‌نام. لطفاً دوباره تلاش کنید.'}, status=500)


def create_user_by_role(register_data):
    """ایجاد کاربر بر اساس نقش"""
    phone = register_data.get('phone_number')
    password = register_data.get('password')
    nickname = register_data.get('nickname')
    role = register_data.get('role')

    if role == "advertiser":
        user, profile = RegistrationService.register_advertiser(
            phone_number=phone, password=password, nickname=nickname
        )
    elif role == "influencer":
        user, profile = RegistrationService.register_influencer(
            phone_number=phone, password=password, nickname=nickname
        )
    elif role == "team_member":
        user = create_team_member(register_data)
    else:
        raise ValueError(f"نقش نامعتبر: {role}")

    return user


def create_team_member(register_data):
    """ایجاد عضو تیم"""
    phone = register_data.get('phone_number')
    password = register_data.get('password')
    nickname = register_data.get('nickname')
    create_new_team = register_data.get('create_new_team')

    if create_new_team:
        team_name = register_data.get('team_name')
        new_team = ContentTeam.objects.create(
            name=team_name,
            slug=generate_random_slug(),
            is_active=True
        )
        user, team_member = RegistrationService.register_team_member(
            phone_number=phone, password=password, nickname=nickname,
            team=new_team, is_manager=True
        )
    else:
        team_slug = register_data.get('team_slug')
        team = ContentTeam.objects.get(slug=team_slug, is_active=True)
        user = CustomUser.objects.create_user(
            phone_number=phone, password=password, nickname=nickname
        )

        # ایجاد درخواست عضویت
        existing_request = TeamJoinRequest.objects.filter(team=team, user=user).first()
        if not existing_request or existing_request.status != TeamJoinRequest.Status.PENDING:
            TeamJoinRequest.objects.create(
                team=team, user=user, status=TeamJoinRequest.Status.PENDING
            )

    return user


def cleanup_session(request):
    """پاکسازی session بعد از تکمیل فرآیند"""
    keys_to_remove = ['register_data', 'login_otp_data', 'otp_sent_at',
                      'otp_remaining', 'verified_phone', 'verified_at']
    for key in keys_to_remove:
        if key in request.session:
            del request.session[key]
