from django.views.decorators.http import require_http_methods
from ..services.otp_service import OTPGhasedakService, logger
from django.views.decorators.csrf import csrf_exempt
from ..models import OTPRequest, CustomUser
from django.http import JsonResponse
from django.utils import timezone
from ..utils.otp_utils import (
    handle_register_verification,
    handle_login_verification,
)
import json


@require_http_methods(["POST"])
@csrf_exempt
def request_otp_api(request):
    """
    API یکپارچه درخواست OTP برای هر دو حالت لاگین و ثبت‌نام
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        otp_type = data.get('type', 'register')

        if not phone_number:
            return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

        if otp_type == 'login':
            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                nickname = user.nickname or f"کاربر {phone_number[-4:]}"
                request.session['login_otp_data'] = {
                    'phone_number': phone_number,
                    'user_id': user.id,
                }
            except CustomUser.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'کاربری با این شماره یافت نشد. لطفاً ثبت‌نام کنید.'
                }, status=400)
        else:
            register_data = request.session.get('register_data', {})
            nickname = register_data.get('nickname')

        service = OTPGhasedakService()
        otp_type_enum = OTPRequest.OTPType.LOGIN if otp_type == 'login' else OTPRequest.OTPType.REGISTER
        otp_obj, success, message, remaining_time = service.send_otp(
            phone_number=phone_number,
            otp_type=otp_type_enum,
            nickname=nickname
        )

        if not success:
            return JsonResponse({'success': False, 'error': message}, status=400)

        request.session['otp_sent_at'] = timezone.now().isoformat()

        return JsonResponse({
            'success': True,
            'message': 'کد تایید برای شما ارسال شد',
            'need_verify': True,
            'remaining_time': remaining_time,
            'otp_type': otp_type
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'داده ارسالی نامعتبر است'}, status=400)
    except Exception as e:
        logger.error(f"request_otp_api error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'خطای داخلی سرور'}, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def verify_otp_api(request):
    """
    API یکپارچه تایید OTP و تکمیل فرآیند (لاگین یا ثبت‌نام)
    """
    try:
        data = json.loads(request.body)
        code = data.get('code')

        if not code:
            return JsonResponse({'success': False, 'error': 'کد تایید الزامی است'}, status=400)

        login_data = request.session.get('login_otp_data')
        register_data = request.session.get('register_data')

        if login_data:
            return handle_login_verification(request, login_data, code)
        elif register_data:
            return handle_register_verification(request, register_data, code)
        else:
            return JsonResponse({
                'success': False,
                'error': 'اطلاعات جلسه یافت نشد. لطفاً دوباره تلاش کنید.'
            }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'داده ارسالی نامعتبر است'}, status=400)
    except Exception as e:
        logger.error(f"verify_otp_api error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'خطای داخلی سرور'}, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def resend_otp_api(request):
    """
    API یکپارچه ارسال مجدد OTP
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')

        if not phone_number:
            return JsonResponse({'success': False, 'error': 'شماره تلفن الزامی است'}, status=400)

        service = OTPGhasedakService()

        remaining_time = service.get_remaining_time(phone_number)
        if remaining_time > 0:
            return JsonResponse({
                'success': False,
                'error': f'لطفاً {remaining_time} ثانیه صبر کنید',
                'remaining_time': remaining_time
            }, status=400)

        login_data = request.session.get('login_otp_data')
        register_data = request.session.get('register_data')

        nickname = None
        otp_type = OTPRequest.OTPType.REGISTER

        if login_data:
            otp_type = OTPRequest.OTPType.LOGIN
            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                nickname = user.nickname
            except CustomUser.DoesNotExist:
                pass
        elif register_data:
            nickname = register_data.get('nickname')

        otp_obj, success, message, new_remaining = service.send_otp(
            phone_number=phone_number,
            otp_type=otp_type,
            nickname=nickname
        )

        if success:
            request.session['otp_sent_at'] = timezone.now().isoformat()
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

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'داده ارسالی نامعتبر است'}, status=400)
    except Exception as e:
        logger.error(f"resend_otp_api error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'خطای داخلی سرور'}, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def check_phone_api(request):
    """
    API یکپارچه بررسی وضعیت شماره (وجود کاربر + وضعیت OTP)
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        check_type = data.get('check_type', 'exists')

        if not phone_number:
            return JsonResponse({'error': 'شماره تلفن الزامی است'}, status=400)

        if check_type == 'status':
            service = OTPGhasedakService()
            remaining_time = service.get_remaining_time(phone_number)
            return JsonResponse({
                'remaining_time': remaining_time,
                'has_active': remaining_time > 0
            })
        else:
            exists = CustomUser.objects.filter(phone_number=phone_number).exists()
            return JsonResponse({'exists': exists})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'داده ارسالی نامعتبر است'}, status=400)
    except Exception as e:
        logger.error(f"check_phone_api error: {str(e)}")
        return JsonResponse({'error': 'خطای داخلی سرور'}, status=500)
