import random
import string
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class VerificationService:
    @staticmethod
    def generate_code():
        return ''.join(random.choices(string.digits, k=6))

    @staticmethod
    def set_verification_code(channel):
        code = VerificationService.generate_code()
        channel.verification_code = code
        channel.verification_code_created_at = timezone.now()
        channel.save(update_fields=['verification_code', 'verification_code_created_at'])
        return code

    @staticmethod
    def is_code_expired(channel):
        if not channel.verification_code_created_at:
            return True
        expiry_time = channel.verification_code_created_at + timedelta(minutes=10)
        return timezone.now() > expiry_time

    @staticmethod
    def clear_verification_code(channel):
        channel.verification_code = None
        channel.verification_code_created_at = None
        channel.save(update_fields=['verification_code', 'verification_code_created_at'])

    @staticmethod
    def start_verification(url, code, callback_url):
        if not settings.USE_N8N_VERIFICATION:
            return False, "سیستم تأیید خودکار غیرفعال است."
        if not settings.N8N_VERIFICATION_WEBHOOK_URL:
            return False, "آدرس Webhook n8n تنظیم نشده است."
        payload = {"url": url, "code": code, "callback_url": callback_url}
        try:
            resp = requests.post(settings.N8N_VERIFICATION_WEBHOOK_URL, json=payload, timeout=15)
            if resp.status_code == 200:
                return True, "درخواست تأیید به n8n ارسال شد."
            else:
                return False, f"خطا در ارتباط با n8n (کد {resp.status_code})"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def is_cooldown_active(channel):
        if channel.status != 'rejected' or not channel.rejected_at:
            return False
        cooldown_until = channel.rejected_at + timedelta(hours=72)
        return timezone.now() < cooldown_until

    @staticmethod
    def get_cooldown_remaining(channel):
        if not channel.rejected_at:
            return 0
        end = channel.rejected_at + timedelta(hours=72)
        remaining = (end - timezone.now()).total_seconds()
        return max(0, int(remaining // 3600))

    @staticmethod
    def reset_if_cooldown_expired(channel):
        """اگر کانال rejected است و قفل 72 ساعته تمام شده، آن را به pending برگردان"""
        if channel.status == 'rejected' and not VerificationService.is_cooldown_active(channel):
            channel.status = 'pending'
            channel.verification_failed_attempts = 0
            channel.rejected_at = None
            channel.verification_code = None
            channel.verification_code_created_at = None
            channel.save()
            return True
        return False

    @staticmethod
    def record_failed_attempt(channel):
        channel.verification_failed_attempts += 1
        if channel.verification_failed_attempts >= 3:
            channel.status = 'rejected'
            channel.rejected_at = timezone.now()
            channel.verification_code = None
            channel.verification_code_created_at = None
            channel.save()
            return True
        else:
            channel.save()
            return False

    @staticmethod
    def record_successful_verification(channel):
        channel.status = 'approved'
        channel.verification_code = None
        channel.verification_code_created_at = None
        channel.verification_failed_attempts = 0
        channel.rejected_at = None
        channel.save()
