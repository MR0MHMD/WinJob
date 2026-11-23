"""ماژول ویوهای اپلیکیشن broadcast (وین‌فوروارد)."""

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from product.forward.broadcast.forms import BroadcastSendForm
from product.forward.broadcast.models import (
    BroadcastChannel,
    BroadcastHub,
    BroadcastJob,
    BroadcastMessage,
    BroadcastTarget,
    ChannelPreset,
)
from product.forward.broadcast.services.dispatcher import enqueue_dispatch_job
from product.forward.constants import TOKEN_TOMAN_RATE

logger = logging.getLogger(__name__)

_PERSIAN_WEEKDAYS = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه")


def _to_gregorian_dt(dt_val, tz):
    """تبدیل ایمن datetime یا jdatetime.datetime (از django_jalali) به datetime میلادی با timezone تهران."""
    if dt_val is None:
        return None
    if isinstance(dt_val, jdatetime.datetime):
        dt_val = dt_val.togregorian()
    elif isinstance(dt_val, jdatetime.date) and not hasattr(dt_val, "hour"):
        g = dt_val.togregorian()
        from datetime import datetime as _dt
        dt_val = _dt(g.year, g.month, g.day)
    if timezone.is_naive(dt_val):
        dt_val = timezone.make_aware(dt_val, tz)
    return dt_val.astimezone(tz)



def _jalali_label(g_date, weekday_only: bool = False) -> str:
    """تبدیل ایمن تاریخ به برچسب شمسی (MM/DD) یا نام روز هفته فارسی."""
    jd = g_date if isinstance(g_date, jdatetime.date) else jdatetime.date.fromgregorian(date=g_date)
    if weekday_only:
        return _PERSIAN_WEEKDAYS[jd.weekday()]
    return jd.strftime("%m/%d")



def _get_token_balance_safe(user) -> int:
    """دریافت ایمن موجودی توکن کاربر."""
    from product.forward.subscriptions.access import get_user_token_balance
    return get_user_token_balance(user)



def _get_jobs_token_spend_map(user, job_ids: list) -> dict:
    """محاسبه تجمیعی توکن مصرف‌شده هر عملیات ارسال در یک کوئری واحد."""
    if not job_ids:
        return {}
    from product.forward.subscriptions.models import ForwardTokenTransaction

    rows = (
        ForwardTokenTransaction.objects.filter(
            user=user,
            tx_type=ForwardTokenTransaction.TxType.SPEND,
            broadcast_job_id__in=job_ids,
        )
        .values("broadcast_job_id")
        .annotate(total=Sum("amount"))
    )
    return {r["broadcast_job_id"]: abs(int(r["total"] or 0)) for r in rows}



def _get_pricing_json() -> str:
    """سریال‌سازی جدول نرخ مصرف توکن برای محاسبه‌گر زنده در استدیو ارسال."""
    from product.forward.subscriptions.services import get_pricing_config
    cfg = get_pricing_config()
    return json.dumps(
        {
            "text": cfg.text_cost,
            "photo": cfg.photo_cost,
            "caption_extra": cfg.caption_extra_cost,
            "sticker_gif": cfg.sticker_gif_cost,
            "under_5": cfg.media_under_5mb_cost,
            "from_5_10": cfg.media_5_to_10mb_cost,
            "from_10_20": cfg.media_10_to_20mb_cost,
            "max_mb": cfg.max_file_size_mb,
            "hub_extra": cfg.hub_extra_cost,
            "ai_extra": cfg.ai_watermark_extra_cost,
        },
        ensure_ascii=False,
    )



def _get_forward_platforms_map() -> dict:
    """واکشی دیکشنری پلتفرم‌های وین‌فوروارد از دیتابیس (شامل فیلد logo) بر اساس اسلاگ."""
    from core.models import Platform

    qs = Platform.objects.filter(slug__in=["bale", "eitaa", "rubika", "telegram", "soroush"])
    return {p.slug: p for p in qs}



def _format_persian_date() -> str:
    """تولید رشته تاریخ شمسی خوانا مشابه داشبورد وین‌دایرکت و تبلیغ‌دهندگان."""
    now_tehran = timezone.now().astimezone(ZoneInfo("Asia/Tehran"))
    today = jdatetime.date.fromgregorian(date=now_tehran.date())
    persian_date = today.strftime("%A %d %B %Y")
    weekdays = {
        "Saturday": "شنبه",
        "Sunday": "یکشنبه",
        "Monday": "دوشنبه",
        "Tuesday": "سه‌شنبه",
        "Wednesday": "چهارشنبه",
        "Thursday": "پنجشنبه",
        "Friday": "جمعه",
    }
    months = {
        "Farvardin": "فروردین",
        "Ordibehesht": "اردیبهشت",
        "Khordad": "خرداد",
        "Tir": "تیر",
        "Mordad": "مرداد",
        "Shahrivar": "شهریور",
        "Mehr": "مهر",
        "Aban": "آبان",
        "Azar": "آذر",
        "Dey": "دی",
        "Bahman": "بهمن",
        "Esfand": "اسفند",
    }
    for en, fa in weekdays.items():
        persian_date = persian_date.replace(en, fa)
    for en, fa in months.items():
        persian_date = persian_date.replace(en, fa)
    return persian_date

