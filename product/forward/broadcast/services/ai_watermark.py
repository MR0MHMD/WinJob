"""سرویس حذف و بازسازی هوشمند واترمارک متنی کانال‌ها با هوش مصنوعی (گیت‌وی چابکان / DeepSeek).

معماری بهینه (یک درخواست AI برای کل جاب، سازگار با هر ۵ پلتفرم):
- متن/کپشن پیام فقط یک‌بار به مدل ارسال می‌شود تا با تگ‌های استاندارد زیر قالب‌بندی شود:
  `{{CHANNEL_NAME}}`، `{{CHANNEL_ID}}`، `{{CHANNEL_URL}}`، `{{PLATFORM_NAME}}`
- پایتون سپس برای هر کانال مقصد (بله، ایتا، تلگرام، روبیکا، سروش‌پلاس) دقیقاً نام، آیدی،
  لینک رسمی همان پلتفرم یا امضای اختصاصی همان کانال را جایگزین می‌کند.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests
from django.conf import settings

from product.forward.constants import (
    DEFAULT_WINFORWARD_AI_ENDPOINT,
    DEFAULT_WINFORWARD_AI_MODEL,
    DEFAULT_WINFORWARD_AI_TIMEOUT,
)

logger = logging.getLogger(__name__)

_PLATFORM_META: dict[str, tuple[str, str]] = {
    "bale": ("بله", "https://ble.ir/"),
    "eitaa": ("ایتا", "https://eitaa.com/"),
    "telegram": ("تلگرام", "https://t.me/"),
    "rubika": ("روبیکا", "https://rubika.ir/"),
    "soroush": ("سروش‌پلاس", "https://splus.ir/"),
}

_SYSTEM_PROMPT = """تو یک پردازشگر فوق‌دقیق، مکانیکی و بدون خلاقیت برای شناسایی، حذف و قالب‌بندی واترمارک و امضای کانال‌های پیام‌رسان‌های فارسی (بله، ایتا، تلگرام، روبیکا، سروش‌پلاس) هستی.

قوانین مطلق و غیرقابل نقض:
1. بدنه اصلی پیام (اطلاعیه، شعر، خبر، نام سخنران، زمان و مکان، نام فرستنده یا عکاس مثل «📸 ارسالی آقا ...») را تحت هیچ شرایطی بازنویسی، خلاصه، ویرایش نگارشی یا تغییر نده.
2. کل بلوک «واترمارک / امضا / لینک عضویت / تبلیغ کانال مبدا» را به طور کامل شناسایی کن؛ از جمله:
   - آیدی‌ها (`@channel_id`) و لینک‌های پیام‌رسان‌ها (`t.me/...`, `ble.ir/...`, `eitaa.com/...`, `rubika.ir/...`, `splus.ir/...`, `shad.ir/...`) چه به صورت ساده و چه به صورت لینک Markdown مانند `[کانال بله](https://ble.ir/...)`.
   - نام کانال مبدا (حتی اگر شامل نام شخص، شهید، مسجد، پایگاه، برند یا عبارت رسمی باشد) که کنار یا بالای آیدی/لینک آمده است.
   - جملات دعوت به عضویت («برای عضویت روی کانال‌ها کلیک کنید»، «در کانال ... با ما همراه باشید»، «عضویت در ...»، «منبع: ...») و خطوط تزئینی متصل به امضا (`➖➖➖`).
   - بلوک‌های چندکانالی یا چندپلتفرمی در انتهای پست (مثلاً وقتی امضای ۲ کانال همکار یا لینک بله + ایتا + تلگرام کنار هم آمده‌اند) و همچنین خطوط «سفارش تبلیغات / ادمین: @...» متعلق به کانال مبدا.
   - هدرهای کوتاه کانال مبدا در ابتدای پیام (فقط نام/آیدی کانال، نه تیتر خبر).
3. قوانین دقیق برای `cleaned_text`:
   - کل بلوک واترمارک (همه کانال‌های مبدا، همه لینک‌های پلتفرم‌ها، جملات دعوت به عضویت، خط تبلیغات ادمین مبدا و خطوط جداکننده متصل به آن) را کامل حذف کن و خطوط خالی اضافه ابتدا/انتها را پاک کن.
4. قوانین دقیق برای `templated_text` (بسیار مهم):
   - بدنه اصلی پیام را دست‌نخورده نگه دار.
   - در بخش واترمارک، به‌جای کل لینک‌ها و کانال‌های متعدد مبدا، **فقط یک بلوک واحد برای یک کانال مقصد** بساز و کانال‌های دوم/سوم مبدا و لینک‌های پلتفرم‌های اضافی (مثل `| [کانال ایتا](...)`) را حذف کن تا فقط یک لینک/آیدی برای پلتفرم کانال مقصد بماند!
   - از دقیقاً این ۴ تگ استاندارد استفاده کن:
     * `{{CHANNEL_NAME}}` : به جای نام کانال مبدا
     * `{{CHANNEL_ID}}` : به جای آیدی `@...` کانال مبدا (وقتی سبک امضا با `@id` است)
     * `{{CHANNEL_URL}}` : به جای آدرس `https://...` در لینک‌های Markdown یا لینک مستقیم
     * `{{PLATFORM_NAME}}` : به جای نام پیام‌رسان در متن لینک (مثلاً به جای «کانال بله» یا «کانال ایتا» بنویس `کانال {{PLATFORM_NAME}}`)
   - اگر جمله دعوت به عضویت جمع بود (مثل «روی کانال ها کلیک کنید»)، در `templated_text` به مفرد طبیعی («روی کانال کلیک کنید») تبدیل شود تا با تک‌کانال مقصد هماهنگ باشد.
   - اگر خط تبلیغات/ادمین کانال مبدا وجود داشت، آن را در `templated_text` نیز حذف کن تا آیدی ادمین کانال مبدا باقی نماند.
5. اگر در متن هیچ واترمارک یا امضای کانال مبدا نبود، `watermark_found` را `false` بگذار و هر دو فیلد `cleaned_text` و `templated_text` را دقیقاً برابر متن ورودی برگردان.
6. خروجی فقط و فقط یک آبجکت JSON معتبر (بدون هیچ متن اضافه) با دقیقاً همین ۳ کلید باشد:
{"watermark_found": true/false, "cleaned_text": "...", "templated_text": "..."}

مثال‌های آموزشی دقیق:

مثال ۱ (چندکانالی + چندپلتفرمی با لینک Markdown):
ورودی:
*تجمع مردم انقلابی محله افسریه
سخنران: سردار رسول سنائی راد
زمان: چهارشنبه ۲۷ آبانماه ساعت ۲۰:۳۰*

*برای عضویت *روی* کانال ها کلیک کنید*👇

*🇮🇷بسیج پایگاه مرصاد*(*شهیدشانهئی*)
🆔[کانال بله](https://ble.ir/14mersad)|[کانال ایتا](https://eitaa.com/razavimersad)
*🕌مسجد رضویه افسریه*
🆔[کانال بله](https://ble.ir/razaviyehinfo)|[کانال ایتا](https://eitaa.com/razaviyehinfo)

خروجی:
{"watermark_found": true, "cleaned_text": "*تجمع مردم انقلابی محله افسریه\nسخنران: سردار رسول سنائی راد\nزمان: چهارشنبه ۲۷ آبانماه ساعت ۲۰:۳۰*", "templated_text": "*تجمع مردم انقلابی محله افسریه\nسخنران: سردار رسول سنائی راد\nزمان: چهارشنبه ۲۷ آبانماه ساعت ۲۰:۳۰*\n\n*برای عضویت روی کانال کلیک کنید*👇\n\n*{{CHANNEL_NAME}}*\n🆔[کانال {{PLATFORM_NAME}}]({{CHANNEL_URL}})"}

مثال ۲ (امضای دوخطی با نام شهید/شخص + حفظ نام فرستنده):
ورودی:
کاش ما را بین غمها جا نمیانداختی
خاطراتت را به جان ما نمیانداختی ...

📸 ارسالی آقا سعید شانهئی

🌷 کانال سردار شهید مسعود شانهئی
🆔 @shanei_ir

خروجی:
{"watermark_found": true, "cleaned_text": "کاش ما را بین غمها جا نمیانداختی\nخاطراتت را به جان ما نمیانداختی ...\n\n📸 ارسالی آقا سعید شانهئی", "templated_text": "کاش ما را بین غمها جا نمیانداختی\nخاطراتت را به جان ما نمیانداختی ...\n\n📸 ارسالی آقا سعید شانهئی\n\n🌷 کانال {{CHANNEL_NAME}}\n🆔 {{CHANNEL_ID}}"}

مثال ۳ (جمله دعوت به عضویت با آیدی):
ورودی:
نکته مهم امروز برای رشد کسب‌وکارهای آنلاین، تمرکز روی محتوای مستمر است.

در کانال لذت دانایی با ما همراه باشید 👇
@lezat_danaei

خروجی:
{"watermark_found": true, "cleaned_text": "نکته مهم امروز برای رشد کسب‌وکارهای آنلاین، تمرکز روی محتوای مستمر است.", "templated_text": "نکته مهم امروز برای رشد کسب‌وکارهای آنلاین، تمرکز روی محتوای مستمر است.\n\nدر کانال {{CHANNEL_NAME}} با ما همراه باشید 👇\n{{CHANNEL_ID}}"}

مثال ۴ (چند لینک مستقیم پلتفرم‌ها + جداکننده + ادمین تبلیغات):
ورودی:
قیمت طلا امروز در بازار تهران با ثبات همراه بود.
➖➖➖➖➖
📡 رسانه خبری پارس
ایتا: https://eitaa.com/pars_news
تلگرام: https://t.me/pars_news
تبلیغات: @pars_ads

خروجی:
{"watermark_found": true, "cleaned_text": "قیمت طلا امروز در بازار تهران با ثبات همراه بود.", "templated_text": "قیمت طلا امروز در بازار تهران با ثبات همراه بود.\n➖➖➖➖➖\n📡 {{CHANNEL_NAME}}\n{{PLATFORM_NAME}}: {{CHANNEL_URL}}"}

مثال ۵ (واترمارک تکی انتهای متن):
ورودی:
جلسه هماهنگی فردا ساعت ۱۰ برگزار می‌شود.

@akhbar_rasmi

خروجی:
{"watermark_found": true, "cleaned_text": "جلسه هماهنگی فردا ساعت ۱۰ برگزار می‌شود.", "templated_text": "جلسه هماهنگی فردا ساعت ۱۰ برگزار می‌شود.\n\n{{CHANNEL_ID}}"}

مثال ۶ (متن بدون واترمارک):
ورودی:
سلام دوستان، فایل گزارش فروش در سامانه بارگذاری شد.

خروجی:
{"watermark_found": false, "cleaned_text": "سلام دوستان، فایل گزارش فروش در سامانه بارگذاری شد.", "templated_text": "سلام دوستان، فایل گزارش فروش در سامانه بارگذاری شد."}"""


def _get_ai_config() -> tuple[str, str, str]:
    api_key = (getattr(settings, "WINFORWARD_AI_API_KEY", "") or "").strip()
    endpoint = (getattr(settings, "WINFORWARD_AI_ENDPOINT", "") or DEFAULT_WINFORWARD_AI_ENDPOINT).strip()
    model = (getattr(settings, "WINFORWARD_AI_MODEL", "") or DEFAULT_WINFORWARD_AI_MODEL).strip()
    return api_key, endpoint, model


def _extract_json_object(raw_content: str) -> dict[str, Any]:
    """استخراج ایمن JSON حتی اگر مدل آن را در بلوک ```json قرار داده باشد."""
    text = (raw_content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("پاسخ هوش مصنوعی قالب JSON معتبر نداشت.")


def _resolve_channel_identity(channel) -> tuple[str, str, str, str]:
    """استخراج (نام کانال، آیدی نمایشی، لینک کامل پلتفرم، نام فارسی پلتفرم) برای جایگزینی دقیق."""
    target_name = (getattr(channel, "title", "") or "").strip()
    platform_obj = getattr(channel, "platform", None)
    slug = (getattr(platform_obj, "slug", "") or "").strip().lower()
    platform_name, base_url = _PLATFORM_META.get(
        slug,
        ((getattr(platform_obj, "name", "") or "کانال").strip(), ""),
    )

    display_raw = (getattr(channel, "watermark_display_id", "") or "").strip()
    uname = (getattr(channel, "username", "") or "").strip().lstrip("@")

    channel_id = ""
    channel_url = ""

    if display_raw:
        if display_raw.lower().startswith(("http://", "https://")):
            channel_url = display_raw
            channel_id = display_raw
        else:
            clean = display_raw.lstrip("@")
            channel_id = f"@{clean}"
            channel_url = f"{base_url}{clean}" if base_url else channel_id
    elif uname:
        channel_id = f"@{uname}"
        channel_url = f"{base_url}{uname}" if base_url else channel_id

    return target_name, channel_id, channel_url, platform_name


def analyze_text_watermark(raw_text: str) -> dict[str, Any]:
    """تحلیل یک‌باره متن پیام با API هوش مصنوعی چابکان و بازگرداندن cleaned_text و templated_text."""
    source_text = (raw_text or "").strip()
    if not source_text:
        return {
            "ok": False,
            "watermark_found": False,
            "cleaned_text": "",
            "templated_text": "",
            "error": "متن خالی است.",
        }

    api_key, endpoint, model = _get_ai_config()
    if not api_key:
        logger.warning("[WinForward AI] WINFORWARD_AI_API_KEY تنظیم نشده است.")
        return {
            "ok": False,
            "watermark_found": False,
            "cleaned_text": source_text,
            "templated_text": source_text,
            "error": "کلید WINFORWARD_AI_API_KEY در تنظیمات سرور ثبت نشده است.",
        }

    payload = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 2500,
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"متن پیام برای پردازش:\n\n{source_text}"},
        ],
    }

    try:
        resp = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(10, DEFAULT_WINFORWARD_AI_TIMEOUT),
            allow_redirects=False,
        )
        if resp.status_code >= 400:
            err_body = (resp.text or "")[:300]
            logger.error("[WinForward AI] HTTP %s: %s", resp.status_code, err_body)
            return {
                "ok": False,
                "watermark_found": False,
                "cleaned_text": source_text,
                "templated_text": source_text,
                "error": f"خطای سرویس هوش مصنوعی (کد {resp.status_code})",
            }

        body = resp.json()
        content = (((body.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
        parsed = _extract_json_object(content)

        cleaned = str(parsed.get("cleaned_text") if parsed.get("cleaned_text") is not None else source_text).strip()
        templated = str(parsed.get("templated_text") if parsed.get("templated_text") is not None else source_text).strip()
        wm_found = bool(parsed.get("watermark_found", False))

        # گاردریل ضد خالی شدن غیرمنتظره متن طولانی
        if len(source_text) > 35 and not cleaned:
            cleaned = source_text
        if len(source_text) > 35 and not templated:
            templated = source_text

        return {
            "ok": True,
            "watermark_found": wm_found,
            "cleaned_text": cleaned,
            "templated_text": templated,
            "model": model,
            "error": "",
        }
    except Exception as exc:
        logger.exception("[WinForward AI] Watermark analysis failed: %s", exc)
        return {
            "ok": False,
            "watermark_found": False,
            "cleaned_text": source_text,
            "templated_text": source_text,
            "error": str(exc),
        }


def apply_channel_watermark(
    raw_text: str,
    channel,
    ai_result: dict[str, Any],
    max_length: int = 4096,
) -> str:
    """اعمال سیاست واترمارک هر کانال (حذف+امضا یا بازسازی هوشمند بر اساس پلتفرم) روی خروجی AI."""
    mode = getattr(channel, "watermark_mode", "off") or "off"
    if mode == "off" or not ai_result or not ai_result.get("ok"):
        return raw_text

    if mode == "remove_append":
        cleaned = (ai_result.get("cleaned_text") or "").strip()
        sig = (getattr(channel, "custom_signature", "") or "").strip()
        if cleaned and sig:
            final_text = f"{cleaned}\n\n{sig}"
        else:
            final_text = cleaned or sig or raw_text
        return final_text[:max_length]

    if mode == "rewrite":
        templated = (ai_result.get("templated_text") or raw_text or "").strip()
        target_name, channel_id, channel_url, platform_name = _resolve_channel_identity(channel)

        result = templated.replace("{{CHANNEL_NAME}}", target_name)
        result = result.replace("{{PLATFORM_NAME}}", platform_name)
        # جلوگیری از تکرار «کانال کانال ...» اگر نام کانال مقصد خودش با کلمه کانال شروع شود
        result = re.sub(r"کانال\s+کانال\s+", "کانال ", result)

        if channel_url:
            result = result.replace("{{CHANNEL_URL}}", channel_url)
        else:
            # اگر لینک/آیدی وجود ندارد، لینک مارک‌داون خراب نسازیم
            result = re.sub(r"\[([^\]]+)\]\(\{\{CHANNEL_URL\}\}\)", "", result)
            result = result.replace("{{CHANNEL_URL}}", "")

        if channel_id:
            result = result.replace("{{CHANNEL_ID}}", channel_id)
        else:
            result = result.replace("{{CHANNEL_ID}}", "")

        # پاک‌سازی خطوطی که پس از حذف آیدی/لینک کانال خصوصی خالی یا فقط آیکون مانده‌اند
        cleaned_lines = []
        for line in result.splitlines():
            if not channel_id and not channel_url:
                stripped = line.strip(" \t|-:•👇🔗🆔📢✨")
                if not stripped and line.strip():
                    continue
            cleaned_lines.append(line)
        result = "\n".join(cleaned_lines).strip()
        result = re.sub(r"\n{3,}", "\n\n", result)

        return (result or raw_text)[:max_length]

    return raw_text
