# payment/utils/bank_detector.py

from core.models import Bank


def detect_bank_from_sheba(sheba_code):
    """
    تشخیص بانک از شماره شبا و برگرداندن آبجکت Bank

    Args:
        sheba_code: شماره شبا (با یا بدون IR و فاصله)

    Returns:
        Bank instance یا None
    """
    if not sheba_code:
        return None

    # تمیز کردن شماره شبا
    sheba_code = sheba_code.upper().replace("IR", "").strip()
    sheba_code = "".join(filter(str.isdigit, sheba_code))

    if len(sheba_code) < 24:
        return None

    bank_code = sheba_code[2:5]

    try:
        return Bank.objects.get(code=bank_code, is_active=True)
    except Bank.DoesNotExist:
        return None


def get_bank_info(sheba_code):
    """
    تشخیص بانک از شماره شبا و برگرداندن اطلاعات کامل

    Args:
        sheba_code: شماره شبا (با یا بدون IR و فاصله)

    Returns:
        dict: شامل name, code, logo_url یا None
    """
    bank = detect_bank_from_sheba(sheba_code)

    if bank:
        return {
            'id': bank.id,
            'name': bank.name,
            'code': bank.code,
            'logo_url': bank.logo.url if bank.logo else None,
        }

    return None
