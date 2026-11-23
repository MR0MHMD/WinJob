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

from .helpers import (
    _format_persian_date,
    _get_forward_platforms_map,
    _get_jobs_token_spend_map,
    _get_pricing_json,
    _get_token_balance_safe,
    _jalali_label,
    _to_gregorian_dt,
)


@login_required
def forward_dashboard(request):
    """داشبورد جامع وین فوروارد: خلاصه اشتراک، کارت‌های ۳ پلتفرم با لوگوی دیتابیس، نمودار ۳۰ روزه و آخرین ارسال‌ها."""
    from payment.models import Wallet
    from product.forward.messengers.models import BotUser
    from product.forward.messengers.services import generate_connect_link
    from product.forward.subscriptions.access import get_user_platform_access_map
    from product.forward.subscriptions.services import account_for

    nav_platforms = _get_forward_platforms_map()
    account = account_for(request.user)
    token_balance = int(getattr(account, "token_balance", 0) or 0)
    total_tokens_spent = int(getattr(account, "total_tokens_spent", 0) or 0)
    can_claim_gift = bool(getattr(account, "can_use_trial", False))
    subscription_days_left = token_balance
    active_plan_name = "کیف توکن وین‌فوروارد"
    access_map = get_user_platform_access_map(request.user)
    wallet = Wallet.objects.filter(user=request.user).first()
    wallet_balance = wallet.balance if wallet else 0

    bot_users = {
        bu.platform.slug: bu
        for bu in BotUser.objects.filter(user=request.user).select_related("platform")
    }

    active_channels = BroadcastChannel.objects.filter(
        user=request.user, is_active=True
    ).select_related("platform")

    channels_by_slug = {"bale": [], "eitaa": [], "rubika": [], "telegram": [], "soroush": []}
    for ch in active_channels:
        if ch.platform.slug in channels_by_slug:
            channels_by_slug[ch.platform.slug].append(ch)

    bale_connect_link = ""
    try:
        bale_connect_link = generate_connect_link(request.user, "bale")
    except Exception:
        bale_connect_link = "https://ble.ir/win_forward_bot"

    telegram_connect_link = ""
    try:
        from product.forward.messengers.adapters.registry import get_adapter
        tg_adapter = get_adapter("telegram")
        tg_bot_username = tg_adapter.get_bot_username() if tg_adapter else ""
        telegram_connect_link = generate_connect_link(request.user, "telegram", bot_username=tg_bot_username)
    except Exception:
        telegram_connect_link = "https://t.me/"

    platform_definitions = [
        {
            "slug": "bale",
            "name": "بله",
            "icon": "bi-send-check-fill",
            "connect_url_name": "broadcast:bale_connect",
            "channels_url_name": "broadcast:bale_channels",
            "is_connected": bool(bot_users.get("bale") and bot_users["bale"].is_verified),
            "account_identifier": (
                bot_users["bale"].username or bot_users["bale"].chat_id if bot_users.get("bale") else ""
            ),
            "summary": "هسته مرکزی دریافت پست از بازوبند ربات بله و انتشار خودکار به تمام کانال‌ها",
        },
        {
            "slug": "eitaa",
            "name": "ایتا",
            "icon": "bi-broadcast-pin",
            "connect_url_name": "broadcast:eitaa_connect_token",
            "channels_url_name": "broadcast:eitaa_channels",
            "is_connected": bool(bot_users.get("eitaa") and bot_users["eitaa"].api_token),
            "account_identifier": (
                "توکن ایتایار متصل" if (bot_users.get("eitaa") and bot_users["eitaa"].api_token) else ""
            ),
            "summary": "اتصال رسمی از طریق توکن ایتایار و انتشار بدون تگ فوروارد در کانال‌های ایتا",
        },
        {
            "slug": "rubika",
            "name": "روبیکا",
            "icon": "bi-phone-vibrate-fill",
            "connect_url_name": "broadcast:rubika_connect_phone",
            "channels_url_name": "broadcast:rubika_channels",
            "is_connected": bool(bot_users.get("rubika") and bot_users["rubika"].has_rubika_session),
            "account_identifier": (
                (bot_users["rubika"].session_data or {}).get("phone_number", "")
                if bot_users.get("rubika")
                else ""
            ),
            "summary": "ورود امن با کد تایید (OTP) و همگام‌سازی خودکار تمام کانال‌های روبیکا",
        },
        {
            "slug": "telegram",
            "name": "تلگرام",
            "icon": "bi-telegram",
            "connect_url_name": "broadcast:telegram_connect",
            "channels_url_name": "broadcast:telegram_channels",
            "is_connected": bool(bot_users.get("telegram") and bot_users["telegram"].is_verified),
            "account_identifier": (
                bot_users["telegram"].username or bot_users["telegram"].chat_id if bot_users.get("telegram") else ""
            ),
            "summary": "هسته دوم ارسال و دریافت پست از ربات تلگرام و انتشار هم‌زمان به ۵ پیام‌رسان",
        },
        {
            "slug": "soroush",
            "name": "سروش‌پلاس",
            "icon": "bi-chat-dots-fill",
            "connect_url_name": "broadcast:soroush_connect_phone",
            "channels_url_name": "broadcast:soroush_channels",
            "is_connected": bool(bot_users.get("soroush") and bot_users["soroush"].has_soroush_session),
            "account_identifier": (
                (bot_users["soroush"].session_data or {}).get("phone_number", "")
                if bot_users.get("soroush")
                else ""
            ),
            "summary": "ورود امن با شماره و کد تایید (OTP)، همگام‌سازی خودکار کانال‌ها و ارسال سریع متن و کپشن به سروش‌پلاس",
        },
    ]

    _order_map = {"bale": 0, "telegram": 1, "rubika": 2, "eitaa": 3, "soroush": 4}
    platform_definitions.sort(key=lambda item: _order_map.get(item["slug"], 99))

    platform_cards = []
    connected_platforms_count = 0
    for p in platform_definitions:
        slug = p["slug"]
        p_obj = nav_platforms.get(slug)
        logo_url = p_obj.logo.url if (p_obj and p_obj.logo) else ""
        acc = access_map.get(slug)
        has_sub = True
        if p["is_connected"]:
            connected_platforms_count += 1
        ch_list = channels_by_slug.get(slug, [])
        platform_cards.append(
            {
                **p,
                "platform_obj": p_obj,
                "logo_url": logo_url,
                "has_subscription": has_sub,
                "access": acc,
                "remaining_days": token_balance,
                "channels_count": len(ch_list),
                "channels": ch_list[:4],
            }
        )

    jobs_qs = (
        BroadcastJob.objects.filter(message__user=request.user)
        .select_related("message")
        .prefetch_related("targets__channel__platform")
        .order_by("-created_at")
    )
    total_jobs_count = jobs_qs.count()
    agg = jobs_qs.aggregate(
        total_sent=Sum("success_count"),
        total_failed=Sum("failed_count"),
    )
    recent_jobs = jobs_qs[:6]

    # داده‌های دقیق نمودار (فقط روزها و ساعت/دقیقه‌هایی که واقعاً ارسال داشته‌اند — به وقت تهران)
    tehran_tz = ZoneInfo("Asia/Tehran")
    now_tehran = timezone.now().astimezone(tehran_tz)
    today_tehran = now_tehran.date()
    start_30_date = today_tehran - timedelta(days=29)
    start_30_dt = timezone.datetime(
        start_30_date.year, start_30_date.month, start_30_date.day, 0, 0, 0, tzinfo=tehran_tz
    )
    cutoff_24h = now_tehran - timedelta(hours=24)

    recent_30_jobs = list(
        BroadcastJob.objects.filter(message__user=request.user, created_at__gte=start_30_dt)
        .values("id", "created_at", "success_count", "failed_count")
        .order_by("created_at")
    )
    recent_30_spend = _get_jobs_token_spend_map(request.user, [r["id"] for r in recent_30_jobs])

    def _build_day_series(days_count: int) -> dict:
        min_day = today_tehran - timedelta(days=days_count - 1)
        buckets = {}
        for row in recent_30_jobs:
            local_dt = _to_gregorian_dt(row["created_at"], tehran_tz)
            if not local_dt:
                continue
            d = local_dt.date()
            if d < min_day or d > today_tehran:
                continue
            s_val = int(row["success_count"] or 0)
            f_val = int(row["failed_count"] or 0)
            tok_val = int(recent_30_spend.get(row["id"], 0))
            if s_val == 0 and f_val == 0 and tok_val == 0:
                continue
            if d not in buckets:
                buckets[d] = {"sent": 0, "failed": 0, "jobs": 0, "tokens": 0}
            buckets[d]["sent"] += s_val
            buckets[d]["failed"] += f_val
            buckets[d]["jobs"] += 1
            buckets[d]["tokens"] += tok_val

        sorted_days = sorted(buckets.keys())
        labels, succ, fail, jobs_c, toks = [], [], [], [], []
        tot_s = tot_f = tot_tok = tot_jobs = peak_v = peak_tok_v = 0
        peak_l = peak_tok_l = "—"
        for d in sorted_days:
            b = buckets[d]
            lbl = _jalali_label(d, weekday_only=(days_count == 7))
            labels.append(lbl)
            succ.append(b["sent"])
            fail.append(b["failed"])
            jobs_c.append(b["jobs"])
            toks.append(b["tokens"])
            tot_s += b["sent"]
            tot_f += b["failed"]
            tot_tok += b["tokens"]
            tot_jobs += b["jobs"]
            if b["sent"] > peak_v:
                peak_v = b["sent"]
                peak_l = lbl
            if b["tokens"] > peak_tok_v:
                peak_tok_v = b["tokens"]
                peak_tok_l = lbl
        tot_all = tot_s + tot_f
        return {
            "labels": labels,
            "success": succ,
            "failed": fail,
            "jobs": jobs_c,
            "tokens": toks,
            "total_sent": tot_s,
            "total_failed": tot_f,
            "success_rate": int(round((tot_s / tot_all) * 100)) if tot_all > 0 else 100,
            "peak_val": peak_v,
            "peak_label": peak_l,
            "total_tokens": tot_tok,
            "total_toman": tot_tok * TOKEN_TOMAN_RATE,
            "avg_tokens_per_job": int(round(tot_tok / tot_jobs)) if tot_jobs > 0 else 0,
            "peak_token_val": peak_tok_v,
            "peak_token_label": peak_tok_l,
        }

    # سری ۲۴ ساعت گذشته: دقیقاً بر اساس ساعت:دقیقه (HH:MM) فقط زمان‌هایی که ارسال انجام شده
    h24_buckets = {}
    for row in recent_30_jobs:
        local_dt = _to_gregorian_dt(row["created_at"], tehran_tz)
        if not local_dt or local_dt < cutoff_24h:
            continue
        s_val = int(row["success_count"] or 0)
        f_val = int(row["failed_count"] or 0)
        tok_val = int(recent_30_spend.get(row["id"], 0))
        if s_val == 0 and f_val == 0 and tok_val == 0:
            continue
        slot_key = local_dt.replace(second=0, microsecond=0)
        if slot_key not in h24_buckets:
            h24_buckets[slot_key] = {"sent": 0, "failed": 0, "jobs": 0, "tokens": 0}
        h24_buckets[slot_key]["sent"] += s_val
        h24_buckets[slot_key]["failed"] += f_val
        h24_buckets[slot_key]["jobs"] += 1
        h24_buckets[slot_key]["tokens"] += tok_val

    h24_labels, h24_succ, h24_fail, h24_jobs, h24_toks = [], [], [], [], []
    h24_tot_s = h24_tot_f = h24_tot_tok = h24_tot_jobs = h24_peak_v = h24_peak_tok_v = 0
    h24_peak_l = h24_peak_tok_l = "—"
    for slot_dt in sorted(h24_buckets.keys()):
        b = h24_buckets[slot_dt]
        lbl = slot_dt.strftime("%H:%M")
        h24_labels.append(lbl)
        h24_succ.append(b["sent"])
        h24_fail.append(b["failed"])
        h24_jobs.append(b["jobs"])
        h24_toks.append(b["tokens"])
        h24_tot_s += b["sent"]
        h24_tot_f += b["failed"]
        h24_tot_tok += b["tokens"]
        h24_tot_jobs += b["jobs"]
        if b["sent"] > h24_peak_v:
            h24_peak_v = b["sent"]
            h24_peak_l = lbl
        if b["tokens"] > h24_peak_tok_v:
            h24_peak_tok_v = b["tokens"]
            h24_peak_tok_l = lbl

    h24_tot_all = h24_tot_s + h24_tot_f
    series_24h = {
        "labels": h24_labels,
        "success": h24_succ,
        "failed": h24_fail,
        "jobs": h24_jobs,
        "tokens": h24_toks,
        "total_sent": h24_tot_s,
        "total_failed": h24_tot_f,
        "success_rate": int(round((h24_tot_s / h24_tot_all) * 100)) if h24_tot_all > 0 else 100,
        "peak_val": h24_peak_v,
        "peak_label": h24_peak_l,
        "total_tokens": h24_tot_tok,
        "total_toman": h24_tot_tok * TOKEN_TOMAN_RATE,
        "avg_tokens_per_job": int(round(h24_tot_tok / h24_tot_jobs)) if h24_tot_jobs > 0 else 0,
        "peak_token_val": h24_peak_tok_v,
        "peak_token_label": h24_peak_tok_l,
    }
    series_7d = _build_day_series(7)
    series_14d = _build_day_series(14)
    series_30d = _build_day_series(30)

    chart_series_map = {
        "24h": series_24h,
        "7d": series_7d,
        "14d": series_14d,
        "30d": series_30d,
    }

    activity_labels = series_30d["labels"]
    activity_success_data = series_30d["success"]
    activity_failed_data = series_30d["failed"]
    activity_jobs_data = series_30d["jobs"]
    chart_total_sent = series_30d["total_sent"]
    chart_total_failed = series_30d["total_failed"]
    chart_success_rate = series_30d["success_rate"]
    chart_peak_val = series_30d["peak_val"]
    chart_peak_label = series_30d["peak_label"]
    chart_today_sent = h24_tot_s

    recent_jobs = list(recent_jobs)
    recent_spend_map = _get_jobs_token_spend_map(request.user, [rj.pk for rj in recent_jobs])
    for rj in recent_jobs:
        seen_p = {}
        for t in rj.targets.all():
            p = t.channel.platform
            if p.slug not in seen_p:
                seen_p[p.slug] = p
        rj.unique_platforms = list(seen_p.values())
        rj.tokens_spent = recent_spend_map.get(rj.pk, 0)
        rj.tokens_toman = rj.tokens_spent * TOKEN_TOMAN_RATE

    user_hubs = list(
        BroadcastHub.objects.filter(user=request.user)
        .select_related("platform", "preset")
        .prefetch_related("channels")
        .order_by("-created_at")
    )

    return render(
        request,
        "product/forward/broadcast/dashboard.html",
        {
            "account": account,
            "access_map": access_map,
            "nav_platforms": nav_platforms,
            "platform_cards": platform_cards,
            "user_presets": list(
                ChannelPreset.objects.filter(user=request.user, is_active=True)
                .prefetch_related("channels")
                .order_by("-created_at")
            ),
            "subscribed_platforms_count": len(access_map),
            "connected_platforms_count": connected_platforms_count,
            "total_channels_count": active_channels.count(),
            "total_jobs_count": total_jobs_count,
            "total_sent_count": agg["total_sent"] or 0,
            "total_failed_count": agg["total_failed"] or 0,
            "recent_jobs": recent_jobs,
            "bale_connect_link": bale_connect_link,
            "telegram_connect_link": telegram_connect_link,
            "token_balance": token_balance,
            "total_tokens_spent": total_tokens_spent,
            "can_claim_gift": can_claim_gift,
            "subscription_days_left": subscription_days_left,
            "active_plan_name": active_plan_name,
            "wallet_balance": wallet_balance,
            "persian_date": _format_persian_date(),
            "activity_labels_json": json.dumps(activity_labels, ensure_ascii=False),
            "activity_success_data_json": json.dumps(activity_success_data, ensure_ascii=False),
            "activity_failed_data_json": json.dumps(activity_failed_data, ensure_ascii=False),
            "activity_jobs_data_json": json.dumps(activity_jobs_data, ensure_ascii=False),
            "chart_series_json": json.dumps(chart_series_map, ensure_ascii=False),
            "chart_total_sent": chart_total_sent,
            "chart_total_failed": chart_total_failed,
            "chart_success_rate": chart_success_rate,
            "chart_peak_val": chart_peak_val,
            "chart_peak_label": chart_peak_label,
            "chart_today_sent": chart_today_sent,
            "user_hubs": user_hubs,
        },
    )

