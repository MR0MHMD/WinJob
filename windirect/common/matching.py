import unicodedata


def _normalize(value):
    """حروف و شکل‌های رایج نوشتار فارسی را برای تطبیق یکسان می‌کند."""
    return (
        unicodedata.normalize("NFKC", value)
        .replace("ي", "ی")
        .replace("ك", "ک")
        .strip()
        .casefold()
    )


def _matches_keyword(automation, text):
    """بررسی می‌کند متن ورودی با حداقل یکی از فعال‌سازها مطابقت دارد."""
    keywords = automation.keywords.values_list("value", flat=True)
    if not keywords:
        return False
    comment = _normalize(text)
    for kw in keywords:
        kw_norm = _normalize(kw)
        if not kw_norm:
            continue
        if automation.match_type == "exact":
            if kw_norm == comment:
                return True
        else:
            if kw_norm in comment:
                return True
    return False


# ==================== سازگاری با کد قدیمی ====================
def _matches(automation, text):
    """نام قدیمی برای سازگاری؛ به _matches_keyword هدایت می‌شود."""
    return _matches_keyword(automation, text)