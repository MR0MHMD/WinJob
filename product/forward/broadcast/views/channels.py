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
def connected_channels(request):
    """صفحه یکپارچه مدیریت تمامی کانال‌های متصل کاربر با فیلتر، جستجو، نمای کارتی/جدولی و صفحه‌بندی."""
    from product.forward.messengers.models import BotUser
    from product.forward.subscriptions.access import get_user_platform_access_map

    nav_platforms = _get_forward_platforms_map()
    access_map = get_user_platform_access_map(request.user)

    bot_users_qs = BotUser.objects.filter(user=request.user).select_related("platform")
    bot_users = {bu.platform.slug: bu for bu in bot_users_qs if bu.platform}

    base_qs = (
        BroadcastChannel.objects.filter(user=request.user, is_active=True)
        .select_related("platform")
        .order_by("-created_at")
    )

    counts_by_platform = {
        "all": base_qs.count(),
        "bale": base_qs.filter(platform__slug="bale").count(),
        "eitaa": base_qs.filter(platform__slug="eitaa").count(),
        "rubika": base_qs.filter(platform__slug="rubika").count(),
        "telegram": base_qs.filter(platform__slug="telegram").count(),
        "soroush": base_qs.filter(platform__slug="soroush").count(),
    }

    selected_platform = (request.GET.get("platform") or "all").strip().lower()
    if selected_platform not in ("all", "bale", "eitaa", "rubika", "telegram", "soroush"):
        selected_platform = "all"

    search_q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "all").strip().lower()
    view_mode = (request.GET.get("view") or "grid").strip().lower()
    if view_mode not in ("grid", "table"):
        view_mode = "grid"

    filtered_qs = base_qs
    if selected_platform != "all":
        filtered_qs = filtered_qs.filter(platform__slug=selected_platform)
    if search_q:
        filtered_qs = filtered_qs.filter(
            Q(title__icontains=search_q)
            | Q(username__icontains=search_q)
            | Q(chat_id__icontains=search_q)
        )
    if status_filter == "ready":
        filtered_qs = filtered_qs.filter(bot_is_admin=True)
    elif status_filter == "pending":
        filtered_qs = filtered_qs.filter(bot_is_admin=False)

    paginator = Paginator(filtered_qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    platform_tabs = [
        {"slug": "all", "name": "همه پلتفرم‌ها", "count": counts_by_platform["all"], "obj": None},
        {"slug": "bale", "name": "بله", "count": counts_by_platform["bale"], "obj": nav_platforms.get("bale")},
        {"slug": "eitaa", "name": "ایتا", "count": counts_by_platform["eitaa"], "obj": nav_platforms.get("eitaa")},
        {"slug": "rubika", "name": "روبیکا", "count": counts_by_platform["rubika"], "obj": nav_platforms.get("rubika")},
        {"slug": "telegram", "name": "تلگرام", "count": counts_by_platform["telegram"],
         "obj": nav_platforms.get("telegram")},
        {"slug": "soroush", "name": "سروش‌پلاس", "count": counts_by_platform["soroush"],
         "obj": nav_platforms.get("soroush")},
    ]

    return render(
        request,
        "product/forward/broadcast/channels/list.html",
        {
            "channels": page_obj.object_list,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "nav_platforms": nav_platforms,
            "platform_tabs": platform_tabs,
            "selected_platform": selected_platform,
            "search_q": search_q,
            "status_filter": status_filter,
            "view_mode": view_mode,
            "counts_by_platform": counts_by_platform,
            "bot_users": bot_users,
            "access_map": access_map,
        },
    )



@login_required
def channel_detail(request, channel_id):
    """صفحه جزئیات کامل کانال: آمار KPI، نمودارهای تحلیلی، تاریخچه و تنظیمات واترمارک هوش مصنوعی."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from django.db.models import Count, Q
    from product.forward.broadcast.models import BroadcastMessage
    from product.forward.constants import TOKEN_COST_AI_WATERMARK, TOKEN_TOMAN_RATE
    from product.forward.subscriptions.models import ForwardTokenTransaction

    channel = get_object_or_404(
        BroadcastChannel.objects.select_related("platform"),
        pk=channel_id,
        user=request.user,
    )

    if request.method == "POST":
        wm_mode = (request.POST.get("watermark_mode") or BroadcastChannel.WatermarkMode.OFF).strip()
        valid_modes = {c[0] for c in BroadcastChannel.WatermarkMode.choices}
        if wm_mode not in valid_modes:
            wm_mode = BroadcastChannel.WatermarkMode.OFF

        custom_sig = (request.POST.get("custom_signature") or "").strip()[:1500]
        display_id = (request.POST.get("watermark_display_id") or "").strip()[:160]

        channel.watermark_mode = wm_mode
        channel.custom_signature = custom_sig
        channel.watermark_display_id = display_id
        channel.save(update_fields=["watermark_mode", "custom_signature", "watermark_display_id"])
        messages.success(request, f"✅ تنظیمات امضای هوشمند برای کانال «{channel.title}» ذخیره شد.")
        return redirect("broadcast:channel_detail", channel_id=channel.pk)

    targets_qs = BroadcastTarget.objects.filter(channel=channel).select_related("job", "job__message")
    agg = targets_qs.aggregate(
        total=Count("id"),
        success=Count("id", filter=Q(status=BroadcastTarget.Status.SUCCESS)),
        failed=Count("id", filter=Q(status=BroadcastTarget.Status.FAILED)),
        skipped=Count("id", filter=Q(status=BroadcastTarget.Status.SKIPPED)),
    )
    total_deliveries = agg["total"] or 0
    success_count = agg["success"] or 0
    failed_count = agg["failed"] or 0
    skipped_count = agg["skipped"] or 0
    success_rate = int(round((success_count / total_deliveries) * 100)) if total_deliveries > 0 else 0

    last_target = targets_qs.filter(sent_at__isnull=False).order_by("-sent_at").first()
    last_sent_at = last_target.sent_at if last_target else channel.last_broadcast_at

    # محاسبه کل توکن مصرفی این کانال و نگاشت توکن هر جاب از دفترکل تراکنش‌ها
    channel_tx_rows = list(
        ForwardTokenTransaction.objects.filter(
            user=request.user,
            tx_type=ForwardTokenTransaction.TxType.SPEND,
            description__icontains=f"«{channel.title}»",
        ).values("broadcast_job_id", "amount", "created_at")
    )
    channel_tokens_spent = sum(abs(int(x["amount"])) for x in channel_tx_rows)
    channel_tokens_toman = channel_tokens_spent * TOKEN_TOMAN_RATE
    tx_by_job = {}
    for tx in channel_tx_rows:
        jid = tx.get("broadcast_job_id")
        if jid:
            tx_by_job[jid] = tx_by_job.get(jid, 0) + abs(int(tx["amount"]))

    # ساخت سری‌های زنده نمودار خطی کانال (۲۴ ساعت / ۷ روز با نام روز هفته / ۱۴ روز / ۳۰ روز شمسی) + تب توکن
    tehran_tz = ZoneInfo("Asia/Tehran")
    now_local = timezone.now().astimezone(tehran_tz)
    today_tehran = now_local.date()
    cutoff_30d = now_local - timedelta(days=30)
    cutoff_24h = now_local - timedelta(hours=24)

    recent_30_targets = list(
        targets_qs.filter(created_at__gte=cutoff_30d).values("job_id", "status", "created_at")
    )

    def _build_ch_day_series(days_n: int) -> dict:
        min_d = today_tehran - timedelta(days=days_n - 1)
        bmap = {}
        for row in recent_30_targets:
            ldt = _to_gregorian_dt(row["created_at"], tehran_tz)
            if not ldt:
                continue
            d = ldt.date()
            if d < min_d or d > today_tehran:
                continue
            if d not in bmap:
                bmap[d] = {"success": 0, "failed": 0, "tokens": 0}
            st = row["status"]
            if st == BroadcastTarget.Status.SUCCESS:
                bmap[d]["success"] += 1
                bmap[d]["tokens"] += int(tx_by_job.get(row["job_id"], 0))
            elif st in (BroadcastTarget.Status.FAILED, BroadcastTarget.Status.SKIPPED):
                bmap[d]["failed"] += 1
        sdays = sorted(bmap.keys())
        return {
            "labels": [_jalali_label(d, weekday_only=(days_n == 7)) for d in sdays],
            "success": [bmap[d]["success"] for d in sdays],
            "failed": [bmap[d]["failed"] for d in sdays],
            "tokens": [bmap[d]["tokens"] for d in sdays],
        }

    h24_map = {}
    for row in recent_30_targets:
        ldt = _to_gregorian_dt(row["created_at"], tehran_tz)
        if not ldt or ldt < cutoff_24h:
            continue
        slot = ldt.replace(second=0, microsecond=0)
        if slot not in h24_map:
            h24_map[slot] = {"success": 0, "failed": 0, "tokens": 0}
        st = row["status"]
        if st == BroadcastTarget.Status.SUCCESS:
            h24_map[slot]["success"] += 1
            h24_map[slot]["tokens"] += int(tx_by_job.get(row["job_id"], 0))
        elif st in (BroadcastTarget.Status.FAILED, BroadcastTarget.Status.SKIPPED):
            h24_map[slot]["failed"] += 1

    sslots = sorted(h24_map.keys())
    channel_chart_series = {
        "24h": {
            "labels": [s.strftime("%H:%M") for s in sslots],
            "success": [h24_map[s]["success"] for s in sslots],
            "failed": [h24_map[s]["failed"] for s in sslots],
            "tokens": [h24_map[s]["tokens"] for s in sslots],
        },
        "7d": _build_ch_day_series(7),
        "14d": _build_ch_day_series(14),
        "30d": _build_ch_day_series(30),
    }

    # نمودار دونات تفکیک نوع محتوا
    ctype_labels_map = dict(BroadcastMessage.ContentType.choices)
    type_counts = targets_qs.values("job__message__content_type").annotate(cnt=Count("id")).order_by("-cnt")
    type_chart = {
        "labels": [str(ctype_labels_map.get(r["job__message__content_type"], r["job__message__content_type"])) for r in
                   type_counts],
        "values": [int(r["cnt"]) for r in type_counts],
    }

    connected_presets = list(
        ChannelPreset.objects.filter(user=request.user, is_active=True, channels=channel).order_by("-created_at")
    )
    connected_hubs = list(
        BroadcastHub.objects.filter(
            user=request.user,
            is_active=True,
        ).filter(
            Q(channels=channel) | Q(preset__channels=channel)
        ).select_related("platform").distinct()
    )
    recent_targets = list(targets_qs.order_by("-created_at")[:10])
    show_eitaa_username_field = (channel.platform.slug == "eitaa") and not (channel.username or "").strip()

    return render(
        request,
        "product/forward/broadcast/channels/detail.html",
        {
            "channel": channel,
            "nav_platforms": _get_forward_platforms_map(),
            "ai_extra_cost": TOKEN_COST_AI_WATERMARK,
            "total_deliveries": total_deliveries,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "success_rate": success_rate,
            "last_sent_at": last_sent_at,
            "channel_tokens_spent": channel_tokens_spent,
            "channel_tokens_toman": channel_tokens_toman,
            "channel_chart_series_json": json.dumps(channel_chart_series, ensure_ascii=False),
            "type_chart_json": json.dumps(type_chart, ensure_ascii=False),
            "connected_presets": connected_presets,
            "connected_hubs": connected_hubs,
            "recent_targets": recent_targets,
            "show_eitaa_username_field": show_eitaa_username_field,
        },
    )



@login_required
def channel_test_watermark(request, channel_id):
    """اندپوینت AJAX برای تست زنده حذف/بازسازی واترمارک با AI روی متن نمونه در صفحه جزئیات کانال."""
    from types import SimpleNamespace
    from django.http import JsonResponse
    from product.forward.broadcast.services.ai_watermark import (
        analyze_text_watermark,
        apply_channel_watermark,
    )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    channel = get_object_or_404(BroadcastChannel.objects.select_related("platform"), pk=channel_id, user=request.user)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "درخواست JSON نامعتبر است."}, status=400)

    sample_text = (payload.get("sample_text") or "").strip()
    if not sample_text:
        return JsonResponse({"ok": False, "error": "متن نمونه خالی است."})

    wm_mode = (payload.get("watermark_mode") or channel.watermark_mode or "off").strip()
    if wm_mode == "off":
        return JsonResponse({
            "ok": True,
            "watermark_found": False,
            "output_text": sample_text,
            "note": "حالت واترمارک روی غیرفعال است؛ متن بدون تغییر نمایش داده شد.",
        })

    ai_res = analyze_text_watermark(sample_text)
    if not ai_res.get("ok"):
        return JsonResponse({"ok": False, "error": ai_res.get("error") or "خطا در پردازش هوش مصنوعی"})

    preview_channel = SimpleNamespace(
        title=channel.title,
        username=channel.username,
        platform=channel.platform,
        watermark_mode=wm_mode,
        custom_signature=(payload.get("custom_signature") or "").strip()[:1500],
        watermark_display_id=(payload.get("watermark_display_id") or "").strip()[:160],
    )
    output_text = apply_channel_watermark(sample_text, preview_channel, ai_res)
    return JsonResponse({
        "ok": True,
        "watermark_found": bool(ai_res.get("watermark_found")),
        "output_text": output_text,
        "model": ai_res.get("model", ""),
    })

