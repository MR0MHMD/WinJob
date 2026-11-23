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
def send_broadcast(request):
    """صفحه استودیو ارسال پیام همگانی به کانال‌های متصل از طریق پنل وب."""
    nav_platforms = _get_forward_platforms_map()
    if request.method == "POST":
        form = BroadcastSendForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            message = form.save(commit=False)
            message.user = request.user
            message.save()

            selected_channels = list(form.cleaned_data["channels"])
            job = BroadcastJob.objects.create(
                message=message,
                total_targets=len(selected_channels),
                status=BroadcastJob.Status.PENDING,
            )

            for channel in selected_channels:
                BroadcastTarget.objects.create(job=job, channel=channel)

            enqueue_dispatch_job(job.pk)
            messages.info(
                request,
                f"🚀 پیام شما در صف ارسال پس‌زمینه قرار گرفت و در حال ارسال به {len(selected_channels)} کانال است.",
            )

            return redirect("broadcast:job_detail", job_id=job.pk)
    else:
        form = BroadcastSendForm(user=request.user)

    presets = (
        ChannelPreset.objects.filter(user=request.user, is_active=True)
        .prefetch_related("channels")
        .order_by("-created_at")
    )
    preset_items = [
        {
            "preset": p,
            "channel_ids": list(p.channels.filter(is_active=True, bot_is_admin=True).values_list("pk", flat=True)),
        }
        for p in presets
    ]

    platform_order = ["bale", "eitaa", "rubika", "telegram", "soroush"]
    grouped_map = {}
    for item in getattr(form, "channel_items", []):
        slug = item["channel"].platform.slug
        if slug not in grouped_map:
            p_obj = item["channel"].platform
            grouped_map[slug] = {
                "slug": slug,
                "name": p_obj.name,
                "logo_url": p_obj.logo.url if p_obj.logo else "",
                "items": [],
            }
        grouped_map[slug]["items"].append(item)

    channel_groups = [grouped_map[s] for s in platform_order if s in grouped_map]
    for s, g in grouped_map.items():
        if s not in platform_order:
            channel_groups.append(g)

    return render(
        request,
        "product/forward/broadcast/send.html",
        {
            "form": form,
            "nav_platforms": nav_platforms,
            "preset_items": preset_items,
            "channel_groups": channel_groups,
            "token_balance": _get_token_balance_safe(request.user),
            "pricing_json": _get_pricing_json(),
        },
    )

