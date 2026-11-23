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
def hub_list(request):
    """صفحه مدیریت هاب‌های تیمی با فیلترهای پیشرفته، سوییچ نمای کارتی (پیش‌فرض) و جدولی و صفحه‌بندی."""
    nav_platforms = _get_forward_platforms_map()
    base_qs = (
        BroadcastHub.objects.filter(user=request.user)
        .select_related("platform", "preset")
        .prefetch_related("channels__platform", "preset__channels")
        .order_by("-created_at")
    )

    search_q = (request.GET.get("q") or "").strip()
    plat_filter = (request.GET.get("platform") or "all").strip().lower()
    mode_filter = (request.GET.get("mode") or "all").strip().lower()
    status_filter = (request.GET.get("status") or "all").strip().lower()
    view_mode = (request.GET.get("view") or "grid").strip().lower()
    if view_mode not in ("grid", "table"):
        view_mode = "grid"

    filtered_qs = base_qs
    if search_q:
        filtered_qs = filtered_qs.filter(Q(title__icontains=search_q) | Q(group_chat_id__icontains=search_q))
    if plat_filter in ("bale", "telegram"):
        filtered_qs = filtered_qs.filter(platform__slug=plat_filter)
    if mode_filter in ("all_msg", "hashtag"):
        filtered_qs = filtered_qs.filter(publish_mode=("all" if mode_filter == "all_msg" else "hashtag"))
    if status_filter == "active":
        filtered_qs = filtered_qs.filter(is_active=True)
    elif status_filter == "inactive":
        filtered_qs = filtered_qs.filter(is_active=False)

    paginator = Paginator(filtered_qs, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "product/forward/broadcast/hubs/list.html",
        {
            "hubs": page_obj.object_list,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "total_hubs_count": base_qs.count(),
            "active_hubs_count": base_qs.filter(is_active=True).count(),
            "search_q": search_q,
            "platform_filter": plat_filter,
            "mode_filter": mode_filter,
            "status_filter": status_filter,
            "view_mode": view_mode,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def hub_edit(request, hub_id):
    """تنظیم پکیج ارسال، کانال‌های مقصد و شرط انتشار (#ارسال / همه پیام‌ها) برای یک هاب."""
    from product.forward.broadcast.forms import BroadcastHubForm

    nav_platforms = _get_forward_platforms_map()
    hub = get_object_or_404(BroadcastHub, pk=hub_id, user=request.user)

    if request.method == "POST":
        form = BroadcastHubForm(request.POST, instance=hub, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ تنظیمات هاب «{hub.title}» با موفقیت ذخیره شد.")
            return redirect("broadcast:hub_list")
    else:
        form = BroadcastHubForm(instance=hub, user=request.user)

    available_presets = ChannelPreset.objects.filter(user=request.user, is_active=True).order_by("-created_at")
    available_channels = (
        BroadcastChannel.objects.filter(user=request.user, is_active=True, bot_is_admin=True)
        .select_related("platform")
        .order_by("platform__name", "title")
    )

    return render(
        request,
        "product/forward/broadcast/hubs/edit.html",
        {
            "form": form,
            "hub": hub,
            "available_presets": available_presets,
            "available_channels": available_channels,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def hub_delete(request, hub_id):
    """حذف کامل یک هاب از پنل کاربر (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:hub_list")
    hub = get_object_or_404(BroadcastHub, pk=hub_id, user=request.user)
    title = hub.title
    hub.delete()
    messages.success(request, f"هاب «{title}» با موفقیت حذف شد.")
    return redirect("broadcast:hub_list")

