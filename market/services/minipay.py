# market/services/__init__.py  →  خالی
# market/services/minipay.py
import logging
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class MinipayError(Exception):
    """خطای عمومی مینی‌پی"""
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


class MinipayClient:
    """
    کلاینت مینی‌پی — VPOS

    ⚠️ TODO: مسیرهای دقیق، هدرها و شکل payload را از مستندات رسمی مینی‌پی بگیر
    و این متدها را تکمیل کن. نام متدها هم‌راستا با API مستندات انتخاب شده‌اند.
    """

    def __init__(self):
        self.base_url = (settings.MINIPAY_BASE_URL or "").rstrip("/")
        self.branch_id = settings.MINIPAY_BRANCH_ID
        self.username = settings.MINIPAY_USERNAME
        self.password = settings.MINIPAY_PASSWORD
        self.api_key = settings.MINIPAY_API_KEY
        self.timeout = getattr(settings, "MINIPAY_TIMEOUT", 30)

        if not self.base_url or not self.branch_id:
            raise ImproperlyConfigured(
                "MINIPAY_BASE_URL و MINIPAY_BRANCH_ID باید در settings تعریف شوند."
            )

    # ---- ابزارهای داخلی ----
    def _headers(self):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, path, payload):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as e:
            logger.exception("Minipay request failed: %s", e)
            raise MinipayError("ارتباط با درگاه پرداخت برقرار نشد.", response=None)

        if resp.status_code >= 400:
            logger.warning("Minipay HTTP %s: %s", resp.status_code, resp.text)
            raise MinipayError(f"خطای درگاه (HTTP {resp.status_code})", response=resp)

        try:
            data = resp.json()
        except ValueError:
            raise MinipayError("پاسخ درگاه قابل خواندن نبود.", response=resp)

        return data

    # ---- API ----
    def get_inquiry(self, input_value, amount):
        """
        استعلام — ورودی: موبایل یا کد ملی، خروجی: inquiry_id
        TODO: شکل payload و مسیر دقیق را با مستندات تطبیق بده
        """
        payload = {
            "input": input_value,
            "branch_id": self.branch_id,
            "amount": int(amount),
        }
        data = self._post("/vpos/get_inquiry", payload)
        if not data.get("inquiry_id"):
            raise MinipayError("پاسخ استعلام نامعتبر بود.", response=None)
        return data["inquiry_id"]

    def pre_transaction(self, inquiry_id, credit_amount):
        """
        پیش‌تراکنش — رمز خرید پیامک می‌شود
        TODO: دقیق تطبیق بده
        """
        payload = {
            "branch_id": self.branch_id,
            "inquiry_id": inquiry_id,
            "credit_amount": int(credit_amount),
        }
        data = self._post("/vpos/pre_transaction", payload)
        if not data.get("pre_transaction_id"):
            raise MinipayError("پاسخ پیش‌تراکنش نامعتبر بود.", response=None)
        return data["pre_transaction_id"]

    def set_transaction(self, pre_transaction_id, purchase_password):
        """
        ثبت نهایی تراکنش با رمز خرید
        TODO: دقیق تطبیق بده
        """
        payload = {
            "branch_id": self.branch_id,
            "pre_transaction_id": pre_transaction_id,
            "purchase_password": purchase_password,
        }
        data = self._post("/vpos/set_transaction", payload)
        if not data.get("transaction_id"):
            raise MinipayError("پرداخت تأیید نشد. لطفاً دوباره تلاش کنید.", response=None)
        return data

    def check_invoice(self, transaction_id):
        """
        بررسی وضعیت فاکتور (اختیاری — برای callback / تأیید نهایی)
        TODO: دقیق تطبیق بده
        """
        payload = {
            "branch_id": self.branch_id,
            "transaction_id": transaction_id,
        }
        return self._post("/vpos/check_invoice", payload)