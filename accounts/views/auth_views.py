from ..utils.otp_utils import handle_password_login, handle_ajax_login
from ..services.otp_service import OTPGhasedakService
from ..forms import LoginForm, RegistrationForm
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.utils import timezone
from ..models import OTPRequest



def register_view(request):
    """
    صفحه ثبت‌نام - ابتدا اطلاعات رو گرفتن، بعد ریدایرکت به OTP
    """
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method != 'POST':
        form = RegistrationForm()
        return render(request, 'accounts/forms/register.html', {'register_form': form , "noindex": True})

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
        return render(request, 'accounts/forms/login.html', {'login_form': form, "noindex": True})

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if is_ajax:
        return handle_ajax_login(request)
    else:
        return handle_password_login(request)


def logout_view(request):
    """خروج از حساب کاربری"""
    logout(request)
    messages.success(request, 'با موفقیت از حساب خود خارج شدید. ')
    return redirect('core:home')


def verify_otp_view(request):
    """
    نمایش صفحه‌ی تایید OTP - پشتیبانی از سه حالت: login / register / reset_password
    """
    login_data = request.session.get('login_otp_data')
    register_data = request.session.get('register_data')
    reset_data = request.session.get('password_reset_data')

    if login_data:
        phone_number = login_data['phone_number']
        otp_purpose = 'login'
    elif register_data:
        phone_number = register_data['phone_number']
        otp_purpose = 'register'
    elif reset_data:
        phone_number = reset_data['phone_number']
        otp_purpose = 'reset_password'
    else:
        messages.error(request, 'اطلاعات جلسه یافت نشد. لطفاً دوباره تلاش کنید.')
        return redirect('accounts:login')

    return render(request, 'accounts/forms/verify_otp.html', {
        'phone_number': phone_number,
        'otp_purpose': otp_purpose,
    })

from django.shortcuts import render, redirect
from django.contrib import messages
from ..forms import ForgotPasswordForm, ResetPasswordForm


def forgot_password_view(request):
    """
    صفحه‌ی ورود شماره موبایل برای بازیابی رمز
    """
    form = ForgotPasswordForm()

    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            # 👈 فقط اطلاعات رو توی session می‌ذاریم؛
            # خودِ ارسال OTP از طریق AJAX به request_otp_api انجام می‌شه
            request.session['forgot_password_phone'] = phone_number

    return render(request, 'accounts/forms/forgot_password.html', {
        'form': form,
    })


def reset_password_view(request):
    """
    صفحه‌ی وارد کردن رمز جدید (بعد از تایید OTP)
    """
    # فقط کاربری که OTP رو تایید کرده اجازه داره
    if not request.session.get('password_reset_verified'):
        messages.error(request, 'لطفاً ابتدا کد تایید را وارد کنید')
        return redirect('accounts:forgot_password')

    form = ResetPasswordForm()

    return render(request, 'accounts/forms/reset_password.html', {
        'form': form,
    })