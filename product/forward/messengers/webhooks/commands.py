"""ماژول وب‌هوک ربات‌های بله و تلگرام (وین‌فوروارد)."""

import html
import json
import logging
import re

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import Platform
from product.forward.broadcast.models import (
    BroadcastChannel,
    BroadcastHub,
    BroadcastJob,
    BroadcastMessage,
    BroadcastTarget,
    ChannelPreset,
)
from product.forward.broadcast.services.channel_sync import finalize_verification, sync_channel_avatar
from product.forward.broadcast.services.dispatcher import enqueue_dispatch_job
from product.forward.messengers.adapters.registry import get_adapter
from product.forward.messengers.models import BotUser, ConnectToken

logger = logging.getLogger(__name__)

from .common import (
    _CANCEL_SEND_KEYBOARD, _GUEST_KEYBOARD, _PLATFORM_NAMES_FA, _USER_KEYBOARD,
    _WINJOB_FORWARD_URL, _WINJOB_PLANS_URL, _WINJOB_PRESETS_URL,
    _bot_send, _set_awaiting_broadcast,
)


def _send_guest_welcome(adapter, chat_id, platform_slug: str = "bale") -> None:
    """ارسال پیام خوش‌آمدگویی کامل و راهنمای اتصال برای کاربران متصل‌نشده."""
    p_name = _PLATFORM_NAMES_FA.get(platform_slug, platform_slug)
    welcome_text = (
        "سلام! به ربات هوشمند **وین فوروارد** خوش آمدید ✨\n\n"
        "با وین فوروارد می‌توانید پست‌های خود را هم‌زمان در کانال‌های **بله، ایتا، روبیکا، تلگرام و سروش‌پلاس** منتشر کنید.\n\n"
        "📌 **برای شروع، این ۳ قدم ساده را انجام دهید:**\n"
        "۱️⃣ روی دکمه زیر بزنید و وارد سایت **وینجاب** شوید (اگر حساب ندارید در چند ثانیه ثبت‌نام کنید).\n"
        f"۲️⃣ پس از ورود، مستقیماً به پنل وین فوروارد هدایت می‌شوید؛ همان‌جا روی **«اتصال حساب {p_name}»** بزنید تا ربات به حسابتان وصل شود.\n"
        "۳️⃣ **۳۵۰ توکن رایگان** شروع را از بخش توکن‌ها دریافت کنید و ربات را در کانال‌هایتان ادمین نمایید.\n\n"
        "👇 برای شروع روی دکمه زیر بزنید:"
    )
    _bot_send(
        adapter,
        chat_id,
        welcome_text,
        reply_markup={
            "inline_keyboard": [
                [{"text": "🌐 ورود به پنل وینجاب و شروع", "url": _WINJOB_FORWARD_URL}],
            ]
        },
        platform_slug=platform_slug,
    )
    _bot_send(
        adapter,
        chat_id,
        "از دکمه پایین هم همیشه می‌توانید وارد پنل وینجاب شوید 👇",
        reply_markup=_GUEST_KEYBOARD,
        platform_slug=platform_slug,
    )



def _send_user_home(adapter, chat_id, bot_user: BotUser, platform_slug: str = "bale") -> None:
    """ارسال پیام خوش‌آمدگویی و منوی اصلی همراه با کیبورد ثابت برای کاربر متصل."""
    from product.forward.subscriptions.access import get_user_token_balance

    _set_awaiting_broadcast(bot_user, False)
    token_balance = get_user_token_balance(bot_user.user)
    channels_count = BroadcastChannel.objects.filter(
        user=bot_user.user, is_active=True, bot_is_admin=True
    ).count()
    presets_count = ChannelPreset.objects.filter(user=bot_user.user, is_active=True).count()

    text = (
        "سلام رفیق! به **وین فوروارد** خوش برگشتی 👋\n\n"
        f"📊 **وضعیت فعلی شما:**\n"
        f"• موجودی توکن: **{token_balance:,} توکن** (بدون انقضا)\n"
        f"• کانال‌های آماده ارسال: **{channels_count} کانال**\n"
        f"• پکیج‌های ارسال: **{presets_count} پکیج**\n\n"
        "برای ارسال پیام جدید، از منوی پایین دکمه **«📤 ارسال پیام»** را بزن 👇"
    )
    _bot_send(adapter, chat_id, text, reply_markup=_USER_KEYBOARD, platform_slug=platform_slug)



def _handle_status_command(chat_id, platform_slug: str = "bale"):
    """نمایش وضعیت حساب کاربری، موجودی توکن و تعداد کانال‌ها."""
    from product.forward.subscriptions.services import account_for

    adapter = get_adapter(platform_slug)
    bot_user = BotUser.objects.filter(
        platform__slug=platform_slug, chat_id=str(chat_id)
    ).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "not connected"})

    acc = account_for(bot_user.user)
    channels = BroadcastChannel.objects.filter(user=bot_user.user, is_active=True, bot_is_admin=True)
    bale_cnt = channels.filter(platform__slug="bale").count()
    eitaa_cnt = channels.filter(platform__slug="eitaa").count()
    rubika_cnt = channels.filter(platform__slug="rubika").count()
    telegram_cnt = channels.filter(platform__slug="telegram").count()
    soroush_cnt = channels.filter(platform__slug="soroush").count()

    p_name = _PLATFORM_NAMES_FA.get(platform_slug, platform_slug)
    gift_hint = "\n🎁 **هدیه ۳۵۰ توکن رایگان شما هنوز دریافت نشده!** از لینک زیر دریافت کنید." if acc.can_use_trial else ""
    msg = (
        f"🪙 **وضعیت حساب و کیف توکن شما**\n\n"
        f"📱 شماره موبایل: `{bot_user.user.phone_number}`\n"
        f"📅 تاریخ اتصال {p_name}: {bot_user.linked_at.strftime('%Y/%m/%d') if bot_user.linked_at else 'نامشخص'}\n\n"
        f"💎 **موجودی فعلی:** `{acc.token_balance:,} توکن` (بدون انقضا · قابل استفاده در هر ۵ پلتفرم)\n"
        f"📊 **کل مصرف تا امروز:** {acc.total_tokens_spent:,} توکن{gift_hint}\n\n"
        f"📢 **کانال‌های آماده ارسال:**\n"
        f"• بله: {bale_cnt} | ایتا: {eitaa_cnt} | روبیکا: {rubika_cnt} | تلگرام: {telegram_cnt} · سروش‌پلاس: {soroush_cnt}"
    )
    _bot_send(
        adapter,
        chat_id,
        msg,
        reply_markup={
            "inline_keyboard": [
                [{"text": "🪙 شارژ توکن / دریافت هدیه رایگان", "url": _WINJOB_PLANS_URL}],
            ]
        },
        platform_slug=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "status sent"})



def _handle_channels_command(chat_id, platform_slug: str = "bale"):
    """نمایش لیست کامل کانال‌های کاربر در همه پلتفرم‌ها با دکمه‌های شیشه‌ای."""
    from product.forward.subscriptions.access import get_active_platform_slugs

    adapter = get_adapter(platform_slug)
    bot_user = BotUser.objects.filter(
        platform__slug=platform_slug, chat_id=str(chat_id)
    ).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "not connected"})

    channels = list(
        BroadcastChannel.objects.filter(user=bot_user.user, is_active=True)
        .select_related("platform")
        .order_by("platform__name", "title")
    )

    if not channels:
        _bot_send(
            adapter,
            chat_id,
            "📋 هنوز هیچ کانالی ثبت نکرده‌اید.\n\n"
            "برای بله و تلگرام، ربات را در کانالتان ادمین کنید؛ و برای ایتا و روبیکا از پنل وب اقدام کنید:",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🌐 افزودن کانال در پنل وب", "url": _WINJOB_FORWARD_URL}],
                ]
            },
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "no channels"})

    active_slugs = get_active_platform_slugs(bot_user.user)
    inline_keyboard = []
    for ch in channels:
        if ch.platform.slug not in active_slugs:
            icon = "🔒"
        elif ch.bot_is_admin:
            icon = "✅"
        else:
            icon = "⚠️"
        inline_keyboard.append([
            {"text": f"{icon} {ch.title} ({ch.platform.name})", "callback_data": f"ch_{ch.pk}"}
        ])

    inline_keyboard.append([{"text": "🌐 مدیریت و افزودن کانال در سایت", "url": _WINJOB_FORWARD_URL}])
    _bot_send(
        adapter,
        chat_id,
        "📢 **لیست کانال‌های شما**\nبرای مشاهده جزئیات، روی هر کانال بزنید (حذف یا ویرایش از طریق پنل وب انجام می‌شود):",
        reply_markup={"inline_keyboard": inline_keyboard},
        platform_slug=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "channels sent"})



def _handle_presets_command(chat_id, platform_slug: str = "bale"):
    """نمایش لیست پکیج‌های ارسال کاربر برای مشاهده جزئیات یا مدیریت در پنل وب."""
    adapter = get_adapter(platform_slug)
    bot_user = BotUser.objects.filter(
        platform__slug=platform_slug, chat_id=str(chat_id)
    ).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "not connected"})

    presets = list(
        ChannelPreset.objects.filter(user=bot_user.user, is_active=True)
        .prefetch_related("channels")
        .order_by("-created_at")
    )

    if not presets:
        _bot_send(
            adapter,
            chat_id,
            "📦 شما هنوز هیچ پکیج ارسالی نساخته‌اید.\n\n"
            "با ساخت پکیج (مثلاً «فروش» یا «اخبار»)، هنگام ارسال پیام فقط با یک کلیک به کل آن گروه کانال پیام می‌فرستید.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "➕ ساخت پکیج در پنل وب", "url": _WINJOB_PRESETS_URL}],
                ]
            },
            platform_slug=platform_slug,
        )
        return JsonResponse({"ok": True, "status": "no presets"})

    inline_keyboard = [
        [{"text": f"📦 {p.name} ({p.channels.count()} کانال)", "callback_data": f"viewpreset_{p.pk}"}]
        for p in presets
    ]
    inline_keyboard.append([{"text": "⚙️ ساخت یا مدیریت پکیج‌ها در سایت", "url": _WINJOB_PRESETS_URL}])

    _bot_send(
        adapter,
        chat_id,
        "📦 **پکیج‌های ارسال شما**\nبرای دیدن کانال‌های عضو هر پکیج روی آن بزنید (ویرایش و حذف در پنل وب انجام می‌شود):",
        reply_markup={"inline_keyboard": inline_keyboard},
        platform_slug=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "presets sent"})



def _handle_start_send_command(chat_id, platform_slug: str = "bale"):
    """ورود کاربر به حالت مرحله‌ای انتظار دریافت پیام/رسانه برای ارسال همگانی."""
    adapter = get_adapter(platform_slug)
    bot_user = BotUser.objects.filter(
        platform__slug=platform_slug, chat_id=str(chat_id)
    ).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "not connected"})

    _set_awaiting_broadcast(bot_user, True)
    _bot_send(
        adapter,
        chat_id,
        "✍️ **آماده دریافت پیام شما هستم!**\n\n"
        "الان می‌توانید متن، عکس، ویدیو، ویس، آهنگ یا فایل خود را همین‌جا بفرستید یا از کانال دیگری **فوروارد** کنید.\n"
        "اگر منصرف شدید، روی «🔙 بازگشت به منوی اصلی» بزنید.",
        reply_markup=_CANCEL_SEND_KEYBOARD,
        platform_slug=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "awaiting broadcast"})



def _handle_help_command(chat_id, platform_slug: str = "bale"):
    """نمایش راهنمای سریع کار با ربات و پشتیبانی وین فوروارد."""
    adapter = get_adapter(platform_slug)
    bot_user = BotUser.objects.filter(
        platform__slug=platform_slug, chat_id=str(chat_id)
    ).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id, platform_slug=platform_slug)
        return JsonResponse({"ok": True, "status": "not connected"})

    help_text = (
        "❓ **راهنمای سریع وین فوروارد**\n\n"
        "1️⃣ **ارسال پیام:** دکمه «📤 ارسال پیام» را بزنید، پست یا فایل خود را بفرستید، پکیج یا کانال‌ها را انتخاب کنید و «🚀 تایید و ارسال» را بزنید.\n"
        "2️⃣ **پکیج‌های ارسال:** از پنل وب کانال‌هایتان را دسته‌بندی کنید تا هر بار مجبور به انتخاب تکی کانال‌ها نباشید.\n"
        "3️⃣ **اتصال ۵ پلتفرم:** بله، تلگرام، ایتا، روبیکا و سروش‌پلاس همگی از طریق پنل وب قابل اتصال‌اند و از همین ربات می‌توانید به همه آن‌ها پیام بفرستید.\n\n"
        f"🌐 **پنل وب و پشتیبانی:** [ورود به پنل وین فوروارد]({_WINJOB_FORWARD_URL})"
    )
    _bot_send(
        adapter,
        chat_id,
        help_text,
        reply_markup={
            "inline_keyboard": [
                [{"text": "🌐 ورود به پنل وین فوروارد", "url": _WINJOB_FORWARD_URL}],
            ]
        },
        platform_slug=platform_slug,
    )
    return JsonResponse({"ok": True, "status": "help sent"})

