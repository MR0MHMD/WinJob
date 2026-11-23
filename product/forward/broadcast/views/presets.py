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
def preset_list(request):
    """صفحه مدیریت و ساخت پروفایل‌های ارسال (گروه‌بندی کانال‌ها برای وب و ربات بله)."""
    from product.forward.broadcast.forms import ChannelPresetForm

    nav_platforms = _get_forward_platforms_map()
    if request.method == "POST":
        form = ChannelPresetForm(request.POST, user=request.user)
        if form.is_valid():
            preset = form.save(commit=False)
            preset.user = request.user
            preset.save()
            form.save_m2m()
            messages.success(request, f"✅ پکیج ارسال «{preset.name}» با موفقیت ذخیره شد.")
            return redirect("broadcast:preset_list")
    else:
        form = ChannelPresetForm(user=request.user)

    presets = (
        ChannelPreset.objects.filter(user=request.user, is_active=True)
        .prefetch_related("channels__platform")
        .order_by("-created_at")
    )
    available_channels = (
        BroadcastChannel.objects.filter(user=request.user, is_active=True, bot_is_admin=True)
        .select_related("platform")
        .order_by("platform__name", "title")
    )

    return render(
        request,
        "product/forward/broadcast/presets/list.html",
        {
            "form": form,
            "presets": presets,
            "available_channels": available_channels,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def preset_edit(request, preset_id):
    """ویرایش نام یا کانال‌های عضو یک پکیج ارسال."""
    from product.forward.broadcast.forms import ChannelPresetForm

    nav_platforms = _get_forward_platforms_map()
    preset = get_object_or_404(ChannelPreset, pk=preset_id, user=request.user)

    if request.method == "POST":
        form = ChannelPresetForm(request.POST, instance=preset, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ تغییرات پکیج «{preset.name}» ذخیره شد.")
            return redirect("broadcast:preset_list")
    else:
        form = ChannelPresetForm(instance=preset, user=request.user)

    available_channels = (
        BroadcastChannel.objects.filter(user=request.user, is_active=True, bot_is_admin=True)
        .select_related("platform")
        .order_by("platform__name", "title")
    )

    return render(
        request,
        "product/forward/broadcast/presets/edit.html",
        {
            "form": form,
            "preset": preset,
            "available_channels": available_channels,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def preset_delete(request, preset_id):
    """حذف یک پکیج ارسال (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:preset_list")
    preset = get_object_or_404(ChannelPreset, pk=preset_id, user=request.user)
    name = preset.name
    preset.delete()
    messages.success(request, f"پکیج ارسال «{name}» حذف شد.")
    return redirect("broadcast:preset_list")

