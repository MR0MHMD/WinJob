from ..services.otp_service import OTPGhasedakService
from ..forms import LoginForm, RegistrationForm
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.utils import timezone
from ..models import OTPRequest
from ..utils.otp_utils import (
    handle_password_login,
    handle_ajax_login,
)


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

    request.session['register_data'] = {
        'phone_number': phone_number,
        'nickname': nickname,
        'password': form.cleaned_data["password"],
        'role': form.cleaned_data["role"],
        'create_new_team': form.cleaned_data.get("create_new_team"),
        'team_name': form.cleaned_data.get("team_name"),
        'team_slug': form.cleaned_data.get("team_slug"),
    }

    service = OTPGhasedakService()
    otp_obj, success, message, remaining_time = service.send_otp(
        phone_number=phone_number,
        otp_type=OTPRequest.OTPType.REGISTER,
        nickname=nickname
    )

    if not success:
        messages.error(request, message)
        return render(request, 'accounts/forms/register.html', {'register_form': form})

    request.session['otp_sent_at'] = timezone.now().isoformat()
    request.session['otp_remaining'] = remaining_time

    return redirect('accounts:verify_otp')


def login_view(request):
    """
    صفحه ورود یکپارچه با پشتیبانی از رمز عبور و OTP
    """
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'GET':
        form = LoginForm()
        return render(request, 'accounts/forms/login.html', {'login_form': form})

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if is_ajax:
        return handle_ajax_login(request)
    else:
        return handle_password_login(request)


def logout_view(request):
    """خروج از حساب کاربری"""
    logout(request)
    messages.success(request, 'با موفقیت از حساب خود خارج شدید. 👋')
    return redirect('core:home')


def verify_otp_view(request):
    """
    صفحه تایید کد OTP - هم برای ثبت ‌نامه و هم برای ورود
    """
    if request.user.is_authenticated:
        return redirect('core:home')

    login_data = request.session.get('login_otp_data')
    register_data = request.session.get('register_data')

    if not login_data and not register_data:
        messages.error(request, 'لطفاً ابتدا فرم مورد نظر را پر کنید')
        return redirect('accounts:login')

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
