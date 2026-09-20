from ghasedak_sms import SendOtpInput, SendOtpReceptorDto
from accounts.models import OTPRequest
from django.utils import timezone
from ghasedak_sms import Ghasedak
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class OTPGhasedakService:
    def __init__(self):
        self.api_key = settings.GHASEDAK_OTP_API
        self.client = Ghasedak(self.api_key)

    def send_otp(self, phone_number, otp_type=OTPRequest.OTPType.VERIFY, nickname=None):
        """
        ارسال OTP جدید و ذخیره در دیتابیس
        فقط در صورت موفقیت آمیز بودن ارسال، تایمر شروع میشه
        """

        # انتخاب قالب بر اساس نوع OTP
        if otp_type == OTPRequest.OTPType.RESET_PASSWORD:
            template = settings.GHASEDAK_RESET_PASSWORD_TEMPLATE
        else:
            template = settings.GHASEDAK_OTP_TEMPLATE

        pending_otp = OTPRequest.objects.filter(
            phone_number=phone_number,
            status=OTPRequest.OTPStatus.PENDING,
            expires_at__gt=timezone.now(),
            api_status_code=200
        ).first()

        if pending_otp and not pending_otp.can_resend():
            remaining = int((pending_otp.created_at + timedelta(minutes=2) - timezone.now()).total_seconds())
            return pending_otp, False, f"لطفاً {remaining} ثانیه صبر کنید تا دوباره درخواست دهید", remaining

        OTPRequest.objects.filter(
            phone_number=phone_number,
            status=OTPRequest.OTPStatus.PENDING,
            api_status_code=200
        ).update(status=OTPRequest.OTPStatus.EXPIRED)

        code = OTPRequest.generate_code()
        otp_obj = OTPRequest.objects.create(
            phone_number=phone_number,
            code=code,
            type=otp_type,
            status=OTPRequest.OTPStatus.PENDING
        )
        error_message = None

        try:
            receptor_dto = SendOtpReceptorDto(mobile=phone_number)

            inputs = [
                SendOtpInput.OtpInput(param='Code', value=code),
            ]

            if nickname:
                inputs.append(SendOtpInput.OtpInput(param='Name', value=nickname))

            otp_input = SendOtpInput(
                send_date=None,
                receptors=[receptor_dto],
                template_name=template,
                inputs=inputs,
            )

            response = self.client.send_otp_sms(otp_input)

            if hasattr(response, '__dict__'):
                response_dict = response.__dict__
            elif isinstance(response, dict):
                response_dict = response
            else:
                response_dict = {'raw': str(response)}

            is_success = response_dict.get('isSuccess', False)
            status_code = response_dict.get('statusCode', None)

            if not is_success:
                error_message = response_dict.get('message', 'خطا در ارسال پیامک')

            otp_obj.api_response = response_dict
            otp_obj.api_status_code = status_code if status_code else (200 if is_success else 500)
            otp_obj.request_id = ''

            try:
                items = response_dict.get('data', {}).get('items', [])
                if items and len(items) > 0:
                    otp_obj.request_id = items[0].get('messageId', '')
            except (AttributeError, KeyError, IndexError, TypeError):
                pass

            if not is_success:
                otp_obj.status = OTPRequest.OTPStatus.EXPIRED

            otp_obj.save()

            self._print_log(phone_number, code, nickname, response_dict, is_success, status_code)

            if is_success:
                return otp_obj, True, "کد تایید ارسال شد", 120
            else:
                return otp_obj, False, error_message or "خطا در ارسال پیامک", 0

        except Exception as e:
            logger.error(f"Ghasedak OTP error: {str(e)}")
            error_dict = {'error': str(e), 'isSuccess': False}
            otp_obj.api_response = error_dict
            otp_obj.api_status_code = 500
            otp_obj.status = OTPRequest.OTPStatus.EXPIRED
            otp_obj.save()

            # پرینت خطا
            print("\n" + "=" * 60)
            print(f"❌ خطا در ارسال OTP به شماره: {phone_number}")
            print(f"🔢 کد ارسالی: {code}")
            if nickname:
                print(f"👤 نام مستعار: {nickname}")
            print(f"⏱️ زمان: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📡 خطا: {str(e)}")
            print("=" * 60 + "\n")

            return otp_obj, False, f"خطا در ارسال: {str(e)}", 0

    @staticmethod
    def verify_otp(phone_number, code):
        """بررسی صحت کد OTP"""
        now = timezone.now()
        otp_obj = OTPRequest.objects.filter(
            phone_number=phone_number,
            code=code,
            status=OTPRequest.OTPStatus.PENDING,
            expires_at__gt=now,
            api_status_code=200
        ).first()

        if not otp_obj:
            return None, False, "کد نامعتبر یا منقضی شده"

        # افزایش تعداد تلاش
        otp_obj.attempts += 1
        if otp_obj.attempts >= 3:
            otp_obj.status = OTPRequest.OTPStatus.EXPIRED
            otp_obj.save()
            return None, False, "تعداد دفعات تلاش بیش از حد مجاز"

        otp_obj.status = OTPRequest.OTPStatus.VERIFIED
        otp_obj.verified_at = now
        otp_obj.save()

        return otp_obj, True, "کد با موفقیت تایید شد"

    @staticmethod
    def get_remaining_time(phone_number):
        """دریافت زمان باقیمانده برای درخواست مجدد OTP - فقط برای درخواست‌های موفق"""
        pending_otp = OTPRequest.objects.filter(
            phone_number=phone_number,
            status=OTPRequest.OTPStatus.PENDING,
            expires_at__gt=timezone.now(),
            api_status_code=200
        ).first()

        if pending_otp:
            remaining = int((pending_otp.created_at + timedelta(minutes=2) - timezone.now()).total_seconds())
            return max(0, remaining)
        return 0

    def has_active_otp(self, phone_number):
        """بررسی وجود OTP فعال موفق"""
        return self.get_remaining_time(phone_number) > 0

    @staticmethod
    def _print_log(phone, code, nickname, response_dict, success, status_code):
        """نمایش لاگ زیبا در ترمینال"""
        status = "✅ موفق" if success else "❌ ناموفق"
        print("\n" + "=" * 60)
        print(f"{status} - ارسال OTP به شماره: {phone}")
        print(f"🔢 کد ارسالی: {code}")
        if nickname:
            print(f"👤 نام مستعار: {nickname}")
        print(f"📧 قالب: WinJobOTP")
        print(f"⏱️ زمان ارسال: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📡 وضعیت API: {status_code if status_code else 'unknown'}")

        if success and response_dict.get('data') and response_dict['data'].get('items'):
            items = response_dict['data']['items']
            if items and len(items) > 0:
                message_body = items[0].get('messageBody', '')
                print(f"💬 متن پیام: {message_body}")
                print(f"💰 هزینه: {items[0].get('cost', 0)} تومان")
                print(f"🆔 شناسه پیام: {items[0].get('messageId', '')}")

        print("=" * 60 + "\n")
