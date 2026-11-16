"""دریافت و پردازش آپدیت‌های Webhook ربات بله با UX پیشرفته و کیبورد ثابت تعاملی."""

import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import Platform
from product.forward.broadcast.models import BroadcastChannel, BroadcastJob, BroadcastTarget, ChannelPreset
from product.forward.broadcast.services.channel_sync import finalize_verification, sync_channel_avatar
from product.forward.broadcast.services.dispatcher import enqueue_dispatch_job
from product.forward.messengers.adapters.registry import get_adapter
from product.forward.messengers.models import BotUser, ConnectToken

logger = logging.getLogger(__name__)

# آدرس‌های مرجع پنل وب وین فوروارد و وینجاب
_WINJOB_FORWARD_URL = "https://winjob.ir/forward/"
_WINJOB_PLANS_URL = "https://winjob.ir/forward/subscriptions/"
_WINJOB_PRESETS_URL = "https://winjob.ir/forward/presets/"

# کیبورد ثابت پایین ربات برای کاربر متصل‌شده
_USER_KEYBOARD = {
    "keyboard": [
        [{"text": "📢 کانال‌های من"}, {"text": "📦 پروفایل‌های ارسال"}],
        [{"text": "👤 حساب و اشتراک"}, {"text": "📤 ارسال پیام"}],
        [{"text": "❓ راهنما و پشتیبانی"}, {"text": "🌐 پنل وب"}],
    ],
    "resize_keyboard": True,
}

# کیبورد ثابت پایین ربات برای کاربر جدید (متصل‌نشده)
_GUEST_KEYBOARD = {
    "keyboard": [
        [{"text": "🌐 ورود به پنل وینجاب"}],
    ],
    "resize_keyboard": True,
}

# کیبورد حالت انتظار دریافت پیام برای ارسال
_CANCEL_SEND_KEYBOARD = {
    "keyboard": [
        [{"text": "🔙 بازگشت به منوی اصلی"}],
    ],
    "resize_keyboard": True,
}


def _set_awaiting_broadcast(bot_user: BotUser, state: bool) -> None:
    """ثبت یا پاکسازی وضعیت انتظار دریافت پیام برای ارسال روی session_data کاربر."""
    data = dict(bot_user.session_data or {})
    if state:
        data["awaiting_broadcast"] = True
    else:
        data.pop("awaiting_broadcast", None)
    bot_user.session_data = data
    bot_user.save(update_fields=["session_data"])


def _send_guest_welcome(adapter, chat_id) -> None:
    """ارسال پیام خوش‌آمدگویی کامل و راهنمای اتصال برای کاربران متصل‌نشده."""
    welcome_text = (
        "سلام! به ربات هوشمند **وین فوروارد** خوش آمدید ✨\n\n"
        "با وین فوروارد می‌توانید پست‌های خود را هم‌زمان در کانال‌های **بله، ایتا و روبیکا** منتشر کنید.\n\n"
        "📌 **برای شروع، این ۳ قدم ساده را انجام دهید:**\n"
        "۱️⃣ روی دکمه زیر بزنید و وارد سایت **وینجاب** شوید (اگر حساب ندارید در چند ثانیه ثبت‌نام کنید).\n"
        "۲️⃣ پس از ورود، مستقیماً به پنل وین فوروارد هدایت می‌شوید؛ همان‌جا روی **«اتصال حساب بله»** بزنید تا ربات به حسابتان وصل شود.\n"
        "۳️⃣ اشتراک **۷ روزه رایگان** را از بخش اشتراک‌ها فعال کنید و ربات را در کانال‌هایتان ادمین نمایید.\n\n"
        "👇 برای شروع روی دکمه زیر بزنید:"
    )
    adapter.send_text(
        chat_id,
        welcome_text,
        reply_markup={
            "inline_keyboard": [
                [{"text": "🌐 ورود به پنل وینجاب و شروع", "url": _WINJOB_FORWARD_URL}],
            ]
        },
    )
    adapter.send_text(
        chat_id,
        "از دکمه پایین هم همیشه می‌توانید وارد پنل وینجاب شوید 👇",
        reply_markup=_GUEST_KEYBOARD,
    )


def _send_user_home(adapter, chat_id, bot_user: BotUser) -> None:
    """ارسال پیام خوش‌آمدگویی و منوی اصلی همراه با کیبورد ثابت برای کاربر متصل."""
    from product.forward.subscriptions.access import get_active_platform_slugs

    _set_awaiting_broadcast(bot_user, False)
    active_slugs = get_active_platform_slugs(bot_user.user)
    channels_count = BroadcastChannel.objects.filter(
        user=bot_user.user, is_active=True, bot_is_admin=True
    ).count()
    presets_count = ChannelPreset.objects.filter(user=bot_user.user, is_active=True).count()

    sub_status = "✅ فعال" if active_slugs else "🔒 غیرفعال (نیاز به تهیه اشتراک)"
    text = (
        "سلام رفیق! به **وین فوروارد** خوش برگشتی 👋\n\n"
        f"📊 **وضعیت فعلی شما:**\n"
        f"• اشتراک: {sub_status}\n"
        f"• کانال‌های آماده ارسال: **{channels_count} کانال**\n"
        f"• پروفایل‌های ارسال: **{presets_count} پروفایل**\n\n"
        "برای ارسال پیام جدید، از منوی پایین دکمه **«📤 ارسال پیام»** را بزن 👇"
    )
    adapter.send_text(chat_id, text, reply_markup=_USER_KEYBOARD)


@csrf_exempt
def bale_webhook(request):
    """نقطه ورود Webhook بله برای دریافت پیام‌ها و کلیک دکمه‌های شیشه‌ای."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    logger.info(f"Bale webhook received: {json.dumps(data, ensure_ascii=False)}")

    if "message" in data:
        return _handle_message(data["message"])

    if "callback_query" in data:
        return _handle_callback_query(data["callback_query"])

    return JsonResponse({"ok": True, "status": "ignored"})


def _handle_message(message):
    """پردازش پیام‌های دریافتی — شامل دستورات، دکمه‌های کیبورد، رویدادهای کانال و پیش‌نویس."""
    if "new_chat_members" in message:
        return _handle_bot_added_to_chat(message)

    if "left_chat_member" in message:
        return _handle_bot_removed_from_chat(message)

    text = (message.get("text") or "").strip()
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return JsonResponse({"ok": True, "status": "no chat_id"})

    if text.startswith("/"):
        parts = text.split(" ")
        command = parts[0].lower()

        adapter = get_adapter("bale")
        if adapter is None:
            logger.error("BaleAdapter is not registered")
            return JsonResponse({"ok": False, "error": "Adapter missing"}, status=500)

        if command == "/start":
            if len(parts) > 1 and parts[1].startswith("verify_"):
                token = parts[1].replace("verify_", "")
                result = finalize_verification(token, "bale", str(chat_id))
                if result["ok"]:
                    adapter.send_text(chat_id, f"✅ کانال «{result['channel'].title}» با موفقیت به وین فوروارد متصل شد.")
                else:
                    error_map = {
                        "invalid_or_used_token": "❌ لینک نامعتبر است یا قبلاً استفاده شده.",
                        "expired_token": "❌ لینک منقضی شده است. لطفاً از سایت لینک جدید بگیرید.",
                        "bot_not_admin": "❌ ربات در کانال ادمین نیست. لطفاً ربات را ادمین کنید.",
                        "api_error": "❌ خطا در ارتباط با بله. لطفاً بعداً تلاش کنید.",
                    }
                    adapter.send_text(chat_id, error_map.get(result.get("error"), "❌ خطای نامشخص."))
                return JsonResponse({"ok": True, "status": "verify processed"})

            if len(parts) > 1 and parts[1].startswith("connect_"):
                token = parts[1].replace("connect_", "")
                from_user = message.get("from", {})
                return _handle_connect_user(token, chat_id, from_user)

            bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()
            if bot_user:
                _send_user_home(adapter, chat_id, bot_user)
            else:
                _send_guest_welcome(adapter, chat_id)
            return JsonResponse({"ok": True, "status": "welcome sent"})

        if command == "/status":
            return _handle_status_command(chat_id)

        if command == "/channels":
            return _handle_channels_command(chat_id)

        if command == "/presets":
            return _handle_presets_command(chat_id)

        if command == "/send":
            return _handle_start_send_command(chat_id)

        if command == "/help":
            return _handle_help_command(chat_id)

        bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()
        adapter.send_text(
            chat_id,
            "دستور واردشده معتبر نیست؛ از دکمه‌های منوی پایین استفاده کنید 👇",
            reply_markup=_USER_KEYBOARD if bot_user else _GUEST_KEYBOARD,
        )
        return JsonResponse({"ok": True, "status": "unknown command"})

    chat_type = message.get("chat", {}).get("type")
    if chat_type == "private":
        return _handle_private_message(message)

    return JsonResponse({"ok": True, "status": "ignored"})


def _handle_bot_added_to_chat(message):
    """پردازش رویداد اضافه شدن ربات به کانال (new_chat_members)."""
    chat = message.get("chat", {})
    from_user = message.get("from", {})

    chat_id = chat.get("id")
    chat_type = chat.get("type")
    from_chat_id = from_user.get("id")

    if chat_type != "channel":
        return JsonResponse({"ok": True, "status": "not a channel"})

    platform = Platform.objects.filter(slug="bale").first()
    if not platform:
        logger.error("Platform 'bale' not found")
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    chat_id_str = str(chat_id)
    adapter = get_adapter("bale")

    bot_user = BotUser.objects.filter(platform=platform, chat_id=str(from_chat_id)).select_related("user").first()

    if not bot_user:
        if adapter and from_chat_id:
            try:
                adapter.send_text(
                    from_chat_id,
                    f"سلام! کانال «{chat.get('title', '')}» شناسایی شد.\n"
                    "برای مدیریت و ارسال پیام، ابتدا وارد پنل وینجاب شوید و حساب بله خود را متصل کنید، "
                    "سپس ربات را یک‌بار از کانال حذف و دوباره اضافه کنید:",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "🌐 ورود به پنل وینجاب", "url": _WINJOB_FORWARD_URL}]
                        ]
                    },
                )
            except Exception as exc:
                logger.warning(f"Failed to send onboarding DM: {exc}")
        return JsonResponse({"ok": True, "status": "user not linked, dm sent"})

    channel, created = BroadcastChannel.objects.update_or_create(
        user=bot_user.user,
        platform=platform,
        chat_id=chat_id_str,
        defaults={
            "title": chat.get("title", "") or chat.get("username", "") or "کانال بدون عنوان",
            "username": chat.get("username", "") or "",
            "bot_is_admin": False,
            "bot_admin_checked_at": timezone.now(),
            "is_active": True,
        },
    )

    if adapter:
        try:
            is_admin = adapter.check_bot_is_admin(chat_id_str)
            channel.bot_is_admin = is_admin
            channel.bot_admin_checked_at = timezone.now()
            channel.save(update_fields=["bot_is_admin", "bot_admin_checked_at"])
            sync_channel_avatar(channel, adapter=adapter)

            if is_admin:
                adapter.send_text(
                    from_chat_id,
                    f"✅ کانال «{channel.title}» با دسترسی ادمین ثبت شد و آماده دریافت پیام است!",
                    reply_markup=_USER_KEYBOARD,
                )
            else:
                adapter.send_text(
                    from_chat_id,
                    f"⚠️ ربات به کانال «{channel.title}» اضافه شد، اما هنوز ادمین نیست.\n"
                    "لطفاً ربات را با دسترسی ارسال پیام ادمین کنید تا در لیست ارسال ظاهر شود.",
                    reply_markup=_USER_KEYBOARD,
                )
        except Exception as exc:
            logger.warning(f"Failed to verify admin status: {exc}")

    return JsonResponse({
        "ok": True,
        "status": "channel created" if created else "channel updated",
        "channel_id": channel.pk,
    })


def _handle_bot_removed_from_chat(message):
    """پردازش حذف شدن ربات از کانال (left_chat_member)."""
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if chat.get("type") != "channel":
        return JsonResponse({"ok": True, "status": "not a channel"})

    platform = Platform.objects.filter(slug="bale").first()
    if not platform:
        return JsonResponse({"ok": False, "error": "Platform missing"}, status=500)

    chat_id_str = str(chat_id)
    updated = BroadcastChannel.objects.filter(
        platform=platform, chat_id=chat_id_str
    ).update(
        is_active=False, bot_is_admin=False, bot_admin_checked_at=timezone.now()
    )

    return JsonResponse({"ok": True, "status": "channel deactivated" if updated else "channel not found"})


def _handle_connect_user(token, chat_id, from_user):
    """اتصال کاربر سایت به ربات با استفاده از توکن تولیدشده در سایت."""
    token_obj = ConnectToken.objects.filter(token=token, used_at__isnull=True).select_related("user", "platform").first()

    adapter = get_adapter("bale")
    if not adapter:
        return JsonResponse({"ok": False, "error": "Adapter missing"}, status=500)

    if not token_obj or not token_obj.is_valid():
        adapter.send_text(
            chat_id,
            "❌ لینک اتصال نامعتبر است یا منقضی شده.\nلطفاً دوباره وارد پنل وینجاب شوید و لینک اتصال جدید بگیرید.",
            reply_markup=_GUEST_KEYBOARD,
        )
        return JsonResponse({"ok": True, "status": "invalid token"})

    bot_user, created = BotUser.objects.get_or_create(
        user=token_obj.user,
        platform=token_obj.platform,
        defaults={"chat_id": str(chat_id), "is_verified": True, "username": from_user.get("username", "")},
    )
    if not created:
        bot_user.chat_id = str(chat_id)
        bot_user.is_verified = True
        bot_user.save(update_fields=["chat_id", "is_verified"])

    token_obj.used_at = timezone.now()
    token_obj.save(update_fields=["used_at"])

    _set_awaiting_broadcast(bot_user, False)
    adapter.send_text(
        chat_id,
        "🎉 حساب بله شما با موفقیت به **وین فوروارد** متصل شد!\n\n"
        "الان می‌توانید ربات را در کانال‌های بله خود ادمین کنید تا خودکار ثبت شوند، "
        "و یا از پنل وب کانال‌های ایتا و روبیکا را متصل کنید.\n\n"
        "همه گزینه‌ها از منوی پایین در دسترس است 👇",
        reply_markup=_USER_KEYBOARD,
    )
    return JsonResponse({"ok": True, "status": "connected"})


def _handle_status_command(chat_id):
    """نمایش وضعیت حساب کاربری، اشتراک پلتفرم‌ها و تعداد کانال‌ها."""
    from product.forward.subscriptions.access import get_user_platform_access_map, platform_label

    adapter = get_adapter("bale")
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id)
        return JsonResponse({"ok": True, "status": "not connected"})

    access_map = get_user_platform_access_map(bot_user.user)
    sub_lines = []
    for slug in ("bale", "eitaa", "rubika"):
        acc = access_map.get(slug)
        if acc and acc.is_valid:
            sub_lines.append(f"  ✅ {platform_label(slug)}: فعال ({acc.remaining_days} روز مانده)")
        else:
            sub_lines.append(f"  🔒 {platform_label(slug)}: غیرفعال")

    channels = BroadcastChannel.objects.filter(user=bot_user.user, is_active=True, bot_is_admin=True)
    bale_cnt = channels.filter(platform__slug="bale").count()
    eitaa_cnt = channels.filter(platform__slug="eitaa").count()
    rubika_cnt = channels.filter(platform__slug="rubika").count()

    msg = (
        f"👤 **وضعیت حساب و اشتراک شما**\n\n"
        f"📱 شماره موبایل: `{bot_user.user.phone_number}`\n"
        f"📅 تاریخ اتصال بله: {bot_user.linked_at.strftime('%Y/%m/%d') if bot_user.linked_at else 'نامشخص'}\n\n"
        f"💎 **وضعیت اشتراک پلتفرم‌ها:**\n" + "\n".join(sub_lines) + "\n\n"
        f"📢 **کانال‌های آماده ارسال:**\n"
        f"• بله: {bale_cnt} | ایتا: {eitaa_cnt} | روبیکا: {rubika_cnt}"
    )
    adapter.send_text(
        chat_id,
        msg,
        reply_markup={
            "inline_keyboard": [
                [{"text": "💎 خرید یا تمدید اشتراک در سایت", "url": _WINJOB_PLANS_URL}],
            ]
        },
    )
    return JsonResponse({"ok": True, "status": "status sent"})


def _handle_channels_command(chat_id):
    """نمایش لیست کامل کانال‌های کاربر در همه پلتفرم‌ها با دکمه‌های شیشه‌ای."""
    from product.forward.subscriptions.access import get_active_platform_slugs

    adapter = get_adapter("bale")
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id)
        return JsonResponse({"ok": True, "status": "not connected"})

    channels = list(
        BroadcastChannel.objects.filter(user=bot_user.user, is_active=True)
        .select_related("platform")
        .order_by("platform__name", "title")
    )

    if not channels:
        adapter.send_text(
            chat_id,
            "📋 هنوز هیچ کانالی ثبت نکرده‌اید.\n\n"
            "برای بله، ربات را در کانالتان ادمین کنید؛ و برای ایتا و روبیکا از پنل وب اقدام کنید:",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🌐 افزودن کانال در پنل وب", "url": _WINJOB_FORWARD_URL}],
                ]
            },
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
    adapter.send_text(
        chat_id,
        "📢 **لیست کانال‌های شما**\nبرای مشاهده جزئیات، روی هر کانال بزنید (حذف یا ویرایش از طریق پنل وب انجام می‌شود):",
        reply_markup={"inline_keyboard": inline_keyboard},
    )
    return JsonResponse({"ok": True, "status": "channels sent"})


def _handle_presets_command(chat_id):
    """نمایش لیست پروفایل‌های ارسال کاربر برای مشاهده جزئیات یا مدیریت در پنل وب."""
    adapter = get_adapter("bale")
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id)
        return JsonResponse({"ok": True, "status": "not connected"})

    presets = list(
        ChannelPreset.objects.filter(user=bot_user.user, is_active=True)
        .prefetch_related("channels")
        .order_by("-created_at")
    )

    if not presets:
        adapter.send_text(
            chat_id,
            "📦 شما هنوز هیچ پروفایل ارسالی نساخته‌اید.\n\n"
            "با ساخت پروفایل (مثلاً «فروش» یا «اخبار»)، هنگام ارسال پیام فقط با یک کلیک به کل آن گروه کانال پیام می‌فرستید.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "➕ ساخت پروفایل در پنل وب", "url": _WINJOB_PRESETS_URL}],
                ]
            },
        )
        return JsonResponse({"ok": True, "status": "no presets"})

    inline_keyboard = [
        [{"text": f"📦 {p.name} ({p.channels.count()} کانال)", "callback_data": f"viewpreset_{p.pk}"}]
        for p in presets
    ]
    inline_keyboard.append([{"text": "⚙️ ساخت یا مدیریت پروفایل‌ها در سایت", "url": _WINJOB_PRESETS_URL}])

    adapter.send_text(
        chat_id,
        "📦 **پروفایل‌های ارسال شما**\nبرای دیدن کانال‌های عضو هر پروفایل روی آن بزنید (ویرایش و حذف در پنل وب انجام می‌شود):",
        reply_markup={"inline_keyboard": inline_keyboard},
    )
    return JsonResponse({"ok": True, "status": "presets sent"})


def _handle_start_send_command(chat_id):
    """ورود کاربر به حالت مرحله‌ای انتظار دریافت پیام/رسانه برای ارسال همگانی."""
    adapter = get_adapter("bale")
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id)
        return JsonResponse({"ok": True, "status": "not connected"})

    _set_awaiting_broadcast(bot_user, True)
    adapter.send_text(
        chat_id,
        "✍️ **آماده دریافت پیام شما هستم!**\n\n"
        "الان می‌توانید متن، عکس، ویدیو، ویس، آهنگ یا فایل خود را همین‌جا بفرستید یا از کانال دیگری **فوروارد** کنید.\n"
        "اگر منصرف شدید، روی «🔙 بازگشت به منوی اصلی» بزنید.",
        reply_markup=_CANCEL_SEND_KEYBOARD,
    )
    return JsonResponse({"ok": True, "status": "awaiting broadcast"})


def _handle_help_command(chat_id):
    """نمایش راهنمای سریع کار با ربات و پشتیبانی وین فوروارد."""
    adapter = get_adapter("bale")
    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()

    if not bot_user:
        _send_guest_welcome(adapter, chat_id)
        return JsonResponse({"ok": True, "status": "not connected"})

    help_text = (
        "❓ **راهنمای سریع وین فوروارد**\n\n"
        "1️⃣ **ارسال پیام:** دکمه «📤 ارسال پیام» را بزنید، پست یا فایل خود را بفرستید، پروفایل یا کانال‌ها را انتخاب کنید و «🚀 تایید و ارسال» را بزنید.\n"
        "2️⃣ **پروفایل‌های ارسال:** از پنل وب کانال‌هایتان را دسته‌بندی کنید تا هر بار مجبور به انتخاب تکی کانال‌ها نباشید.\n"
        "3️⃣ **اتصال ایتا و روبیکا:** از طریق پنل وب وین فوروارد انجام می‌شود و مستقیماً در همین ربات هم قابل ارسال است.\n\n"
        f"🌐 **پنل وب و پشتیبانی:** [ورود به پنل وین فوروارد]({_WINJOB_FORWARD_URL})"
    )
    adapter.send_text(
        chat_id,
        help_text,
        reply_markup={
            "inline_keyboard": [
                [{"text": "🌐 ورود به پنل وین فوروارد", "url": _WINJOB_FORWARD_URL}],
            ]
        },
    )
    return JsonResponse({"ok": True, "status": "help sent"})


def _build_draft_keyboard(job, manual_mode: bool = False):
    """ساخت کیبورد شیشه‌ای هوشمند برای انتخاب پروفایل‌ها، انتخاب دستی کانال‌ها، انتخاب همه و لغو پیش‌نویس."""
    from product.forward.subscriptions.access import get_active_platform_slugs

    active_slugs = get_active_platform_slugs(job.message.user)
    channels = list(
        BroadcastChannel.objects.filter(
            user=job.message.user, is_active=True, bot_is_admin=True
        ).select_related("platform")
    )
    eligible_channel_ids = {ch.pk for ch in channels if ch.platform.slug in active_slugs}
    selected_channel_ids = set(job.targets.values_list("channel_id", flat=True))

    presets = list(
        ChannelPreset.objects.filter(user=job.message.user, is_active=True)
        .prefetch_related("channels__platform")
        .order_by("-created_at")
    )

    inline_keyboard = []

    if presets and not manual_mode:
        for preset in presets:
            preset_eligible_ids = {
                ch.pk
                for ch in preset.channels.all()
                if ch.is_active and ch.bot_is_admin and ch.platform.slug in active_slugs
            }
            if not preset_eligible_ids:
                inline_keyboard.append([
                    {"text": f"🔒 📦 {preset.name} (نیاز به اشتراک یا کانال فعال)", "callback_data": f"preset_{job.pk}_{preset.pk}"}
                ])
            else:
                is_selected = preset_eligible_ids.issubset(selected_channel_ids)
                icon = "✅" if is_selected else "⬜"
                inline_keyboard.append([
                    {"text": f"{icon} 📦 {preset.name} ({len(preset_eligible_ids)} کانال)", "callback_data": f"preset_{job.pk}_{preset.pk}"}
                ])

        if eligible_channel_ids:
            all_selected = eligible_channel_ids.issubset(selected_channel_ids)
            all_icon = "✅" if all_selected else "⬜"
            inline_keyboard.append([
                {"text": f"{all_icon} 🌟 انتخاب همه ({len(eligible_channel_ids)} کانال)", "callback_data": f"selall_{job.pk}"}
            ])

        inline_keyboard.append([
            {"text": "📋 انتخاب دستی کانال‌ها", "callback_data": f"manual_{job.pk}"}
        ])
    else:
        if presets:
            inline_keyboard.append([
                {"text": "🔙 بازگشت به پروفایل‌های ارسال", "callback_data": f"presetsview_{job.pk}"}
            ])

        if eligible_channel_ids:
            all_selected = eligible_channel_ids.issubset(selected_channel_ids)
            all_icon = "✅" if all_selected else "⬜"
            selall_cb = f"selallm_{job.pk}" if presets else f"selall_{job.pk}"
            inline_keyboard.append([
                {"text": f"{all_icon} 🌟 انتخاب همه ({len(eligible_channel_ids)} کانال)", "callback_data": selall_cb}
            ])

        for ch in channels:
            if ch.platform.slug not in active_slugs:
                inline_keyboard.append([
                    {"text": f"🔒 {ch.title} ({ch.platform.name} - نیاز به اشتراک)", "callback_data": f"locked_{ch.platform.slug}"}
                ])
            else:
                is_selected = ch.pk in selected_channel_ids
                icon = "✅" if is_selected else "⬜"
                inline_keyboard.append([{"text": f"{icon} {ch.title}", "callback_data": f"sel_{job.pk}_{ch.pk}"}])

    inline_keyboard.append([
        {"text": "🚀 تایید و ارسال", "callback_data": f"send_{job.pk}"},
        {"text": "❌ لغو پیش‌نویس", "callback_data": f"cancel_{job.pk}"},
    ])
    return {"inline_keyboard": inline_keyboard}


def _handle_callback_query(callback):
    """پردازش کلیک کاربر روی دکمه‌های شیشه‌ای."""
    adapter = get_adapter("bale")
    data = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    message_id = callback.get("message", {}).get("message_id")

    if not chat_id:
        return JsonResponse({"ok": True, "status": "no chat"})

    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=str(chat_id)).select_related("user").first()
    if not bot_user:
        _send_guest_welcome(adapter, chat_id)
        return JsonResponse({"ok": True, "status": "unauthorized"})

    # ۰. کلیک روی کانال نیازمند اشتراک
    if data.startswith("locked_"):
        from product.forward.subscriptions.access import platform_label
        slug = data.replace("locked_", "")
        adapter.send_text(
            chat_id,
            f"🔒 اشتراک فعال برای پلتفرم «{platform_label(slug)}» ندارید.\n"
            "برای فعال‌سازی، به بخش اشتراک وین‌فوروارد در سایت مراجعه کنید.",
            reply_markup={"inline_keyboard": [[{"text": "💎 خرید اشتراک", "url": _WINJOB_PLANS_URL}]]},
        )
        return JsonResponse({"ok": True, "status": "locked platform"})

    # ۱-الف. انتخاب/لغو انتخاب یک پروفایل ارسال
    if data.startswith("preset_"):
        try:
            from product.forward.subscriptions.access import get_active_platform_slugs

            _, job_id, preset_id = data.split("_")
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            preset = ChannelPreset.objects.filter(pk=preset_id, user=bot_user.user, is_active=True).first()
            if not job or not preset:
                return JsonResponse({"ok": True, "status": "job or preset not found"})

            active_slugs = get_active_platform_slugs(bot_user.user)
            eligible_ids = [
                ch.pk
                for ch in preset.channels.filter(is_active=True, bot_is_admin=True).select_related("platform")
                if ch.platform.slug in active_slugs
            ]
            if not eligible_ids:
                adapter.send_text(
                    chat_id,
                    f"⚠️ پروفایل «{preset.name}» هیچ کانال فعالی با اشتراک معتبر ندارد.",
                )
                return JsonResponse({"ok": True, "status": "preset has no eligible channels"})

            selected_ids = set(job.targets.values_list("channel_id", flat=True))
            if set(eligible_ids).issubset(selected_ids):
                BroadcastTarget.objects.filter(job=job, channel_id__in=eligible_ids).delete()
            else:
                for cid in eligible_ids:
                    if cid not in selected_ids:
                        BroadcastTarget.objects.get_or_create(job=job, channel_id=cid)

            if message_id:
                reply_markup = _build_draft_keyboard(job)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error in preset_ callback: {e}")

        return JsonResponse({"ok": True, "status": "preset toggled"})

    # ۱-ب. جابجایی به حالت انتخاب دستی کانال‌ها یا بازگشت به پروفایل‌ها
    if data.startswith("manual_") or data.startswith("presetsview_"):
        try:
            is_manual = data.startswith("manual_")
            job_id = data.split("_", 1)[1]
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            if job and message_id:
                reply_markup = _build_draft_keyboard(job, manual_mode=is_manual)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error switching manual/preset view: {e}")
        return JsonResponse({"ok": True, "status": "view switched"})

    # ۱-ج. انتخاب یا لغو انتخاب همه کانال‌های مجاز
    if data.startswith("selall_") or data.startswith("selallm_"):
        try:
            from product.forward.subscriptions.access import get_active_platform_slugs

            is_manual = data.startswith("selallm_")
            job_id = data.split("_", 1)[1]
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            if not job:
                return JsonResponse({"ok": True, "status": "job not found"})

            active_slugs = get_active_platform_slugs(bot_user.user)
            eligible_ids = [
                ch.pk
                for ch in BroadcastChannel.objects.filter(
                    user=bot_user.user, is_active=True, bot_is_admin=True
                ).select_related("platform")
                if ch.platform.slug in active_slugs
            ]
            selected_ids = set(job.targets.values_list("channel_id", flat=True))
            if eligible_ids and set(eligible_ids).issubset(selected_ids):
                job.targets.all().delete()
            else:
                for cid in eligible_ids:
                    if cid not in selected_ids:
                        BroadcastTarget.objects.get_or_create(job=job, channel_id=cid)

            if message_id:
                reply_markup = _build_draft_keyboard(job, manual_mode=is_manual)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error in selall_ callback: {e}")

        return JsonResponse({"ok": True, "status": "select all toggled"})

    # ۱-د. انتخاب/لغو انتخاب کانال تکی (حفظ حالت دستی)
    if data.startswith("sel_"):
        try:
            _, job_id, channel_id = data.split("_")
            job = BroadcastJob.objects.filter(pk=job_id, message__user=bot_user.user).first()
            if not job:
                return JsonResponse({"ok": True, "status": "job not found"})

            target = BroadcastTarget.objects.filter(job=job, channel_id=channel_id).first()
            if target:
                target.delete()
            else:
                BroadcastTarget.objects.create(job=job, channel_id=channel_id)

            if message_id:
                reply_markup = _build_draft_keyboard(job, manual_mode=True)
                adapter.edit_message_reply_markup(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.error(f"Error in sel_ callback: {e}")

        return JsonResponse({"ok": True, "status": "selection toggled"})

    # ۱-ه. لغو پیش‌نویس و پاک کردن پیام انتخاب
    if data.startswith("cancel_"):
        try:
            job_id = data.replace("cancel_", "")
            job = BroadcastJob.objects.filter(
                pk=job_id, message__user=bot_user.user, status=BroadcastJob.Status.DRAFT
            ).first()
            if job:
                msg_obj = job.message
                job.delete()
                if msg_obj and not msg_obj.jobs.exists():
                    msg_obj.delete()
            if message_id:
                adapter.delete_message(chat_id, message_id)
            still_awaiting = bool((bot_user.session_data or {}).get("awaiting_broadcast"))
            adapter.send_text(
                chat_id,
                "❌ پیش‌نویس ارسال لغو و پاک شد.",
                reply_markup=_CANCEL_SEND_KEYBOARD if still_awaiting else _USER_KEYBOARD,
            )
        except Exception as e:
            logger.error(f"Error in cancel_ callback: {e}")
        return JsonResponse({"ok": True, "status": "draft cancelled"})

    # ۲. تایید و ارسال نهایی (حذف فوری پیام پیش‌نویس و اجرای پس‌زمینه)
    if data.startswith("send_"):
        try:
            job_id = data.replace("send_", "")
            job = BroadcastJob.objects.filter(
                pk=job_id, message__user=bot_user.user, status=BroadcastJob.Status.DRAFT
            ).first()
            if not job:
                adapter.send_text(chat_id, "❌ پیش‌نویس یافت نشد یا قبلاً ارسال شده است.", reply_markup=_USER_KEYBOARD)
                return JsonResponse({"ok": True, "status": "job not found"})

            if not job.targets.exists():
                adapter.send_text(chat_id, "⚠️ لطفاً حداقل یک پروفایل یا کانال را انتخاب کنید.")
                return JsonResponse({"ok": True, "status": "no targets"})

            job.status = BroadcastJob.Status.PENDING
            job.total_targets = job.targets.count()
            job.save(update_fields=["status", "total_targets"])

            # حذف فوری پیام پیش‌نویس/انتخاب کانال تا صفحه تمیز بماند و کلیک تکراری ممکن نباشد
            if message_id:
                adapter.delete_message(chat_id, message_id)

            enqueue_dispatch_job(job.pk, progress_chat_id=str(chat_id))
        except Exception as e:
            logger.exception(f"Error in send_ callback: {e}")
            adapter.send_text(chat_id, "❌ خطایی در شروع ارسال رخ داد.", reply_markup=_USER_KEYBOARD)

        return JsonResponse({"ok": True, "status": "send processed"})

    # ۳. مدیریت کانال‌ها و پروفایل‌ها
    if (
        data.startswith("ch_")
        or data == "back_list"
        or data.startswith("refresh_")
        or data.startswith("viewpreset_")
        or data == "back_presets"
    ):
        return _handle_dashboard_callback(callback, adapter, chat_id, bot_user)

    return JsonResponse({"ok": True, "status": "ignored"})


def _handle_dashboard_callback(callback, adapter, chat_id, bot_user):
    """مدیریت مشاهده جزئیات کانال‌ها و پروفایل‌ها در ربات (حذف و ویرایش از طریق پنل وب)."""
    from product.forward.subscriptions.access import user_has_platform_access

    data = callback.get("data", "")

    if data.startswith("ch_"):
        channel_id = data.replace("ch_", "")
        channel = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).select_related("platform").first()
        if not channel:
            adapter.send_text(chat_id, "❌ کانال یافت نشد.")
            return JsonResponse({"ok": True})

        admin_status = "✅ ربات/اکانت متصل است" if channel.bot_is_admin else "⚠️ دسترسی ارسال تایید نشده"
        has_sub = user_has_platform_access(bot_user.user, channel.platform.slug)
        sub_status = "✅ اشتراک فعال" if has_sub else "🔒 نیاز به اشتراک"
        username_line = f"🔗 آیدی: @{channel.username}\n" if channel.username else ""

        text = (
            f"📢 **{channel.title}**\n\n"
            f"📱 پلتفرم: **{channel.platform.name}**\n"
            f"{username_line}"
            f"🆔 شناسه: `{channel.chat_id}`\n"
            f"🛡️ وضعیت اتصال: {admin_status}\n"
            f"💎 وضعیت اشتراک: {sub_status}\n\n"
            "برای حذف یا ویرایش این کانال از پنل وب استفاده کنید:"
        )
        web_channel_url = f"https://winjob.ir/forward/{channel.platform.slug}/channels/"
        inline_keyboard = []
        if channel.platform.slug == "bale":
            inline_keyboard.append([{"text": "🔄 بروزرسانی وضعیت ادمین", "callback_data": f"refresh_{channel.pk}"}])
        inline_keyboard.append([{"text": "⚙️ حذف یا مدیریت در پنل وب", "url": web_channel_url}])
        inline_keyboard.append([{"text": "🔙 بازگشت به لیست کانال‌ها", "callback_data": "back_list"}])

        adapter.send_text(chat_id, text, reply_markup={"inline_keyboard": inline_keyboard})
        return JsonResponse({"ok": True})

    if data.startswith("refresh_"):
        channel_id = data.replace("refresh_", "")
        channel = BroadcastChannel.objects.filter(pk=channel_id, user=bot_user.user).select_related("platform").first()
        if channel and adapter and channel.platform.slug == "bale":
            try:
                is_admin = adapter.check_bot_is_admin(channel.chat_id)
                channel.bot_is_admin = is_admin
                channel.save(update_fields=["bot_is_admin"])
                sync_channel_avatar(channel, adapter=adapter)
                adapter.send_text(
                    chat_id,
                    f"✅ وضعیت «{channel.title}» بروزرسانی شد:\n{'✅ ربات ادمین است' if is_admin else '⚠️ ربات ادمین نیست'}",
                )
            except Exception as e:
                adapter.send_text(chat_id, f"❌ خطا در بروزرسانی: {e}")
        return JsonResponse({"ok": True})

    if data == "back_list":
        return _handle_channels_command(chat_id)

    if data.startswith("viewpreset_"):
        preset_id = data.replace("viewpreset_", "")
        preset = (
            ChannelPreset.objects.filter(pk=preset_id, user=bot_user.user, is_active=True)
            .prefetch_related("channels__platform")
            .first()
        )
        if not preset:
            adapter.send_text(chat_id, "❌ پروفایل یافت نشد.")
            return JsonResponse({"ok": True})

        ch_lines = [
            f"  • {ch.title} ({ch.platform.name})"
            for ch in preset.channels.filter(is_active=True)
        ]
        channels_block = "\n".join(ch_lines) if ch_lines else "  (بدون کانال)"
        text = (
            f"📦 **جزئیات پروفایل «{preset.name}»**\n\n"
            f"📢 **کانال‌های عضو ({len(ch_lines)}):**\n{channels_block}\n\n"
            "برای ویرایش یا حذف این پروفایل از پنل وب اقدام کنید:"
        )
        edit_url = f"https://winjob.ir/forward/presets/{preset.pk}/edit/"
        adapter.send_text(
            chat_id,
            text,
            reply_markup={
                "inline_keyboard": [
                    [{"text": "✏️ ویرایش یا حذف در پنل وب", "url": edit_url}],
                    [{"text": "🔙 بازگشت به لیست پروفایل‌ها", "callback_data": "back_presets"}],
                ]
            },
        )
        return JsonResponse({"ok": True})

    if data == "back_presets":
        return _handle_presets_command(chat_id)

    return JsonResponse({"ok": True})


def _handle_private_message(message):
    """پردازش دکمه‌های کیبورد ثابت و ساخت پیش‌نویس در حالت مرحله‌ای ارسال پیام."""
    from product.forward.broadcast.models import BroadcastMessage

    chat_id = message.get("chat", {}).get("id")
    chat_str = str(chat_id)
    text_content = (message.get("text") or "").strip()
    adapter = get_adapter("bale")

    bot_user = BotUser.objects.filter(platform__slug="bale", chat_id=chat_str).select_related("user").first()
    if not bot_user:
        _send_guest_welcome(adapter, chat_id)
        return JsonResponse({"ok": True, "status": "not connected"})

    if text_content.startswith("/"):
        return JsonResponse({"ok": True, "status": "command ignored in private"})

    # ۱. پردازش دکمه‌های کیبورد ثابت پایین ربات
    if text_content == "📢 کانال‌های من":
        _set_awaiting_broadcast(bot_user, False)
        return _handle_channels_command(chat_id)

    if text_content == "📦 پروفایل‌های ارسال":
        _set_awaiting_broadcast(bot_user, False)
        return _handle_presets_command(chat_id)

    if text_content == "👤 حساب و اشتراک":
        _set_awaiting_broadcast(bot_user, False)
        return _handle_status_command(chat_id)

    if text_content == "📤 ارسال پیام":
        return _handle_start_send_command(chat_id)

    if text_content == "🔙 بازگشت به منوی اصلی":
        _set_awaiting_broadcast(bot_user, False)
        adapter.send_text(chat_id, "به منوی اصلی برگشتید 👇", reply_markup=_USER_KEYBOARD)
        return JsonResponse({"ok": True, "status": "send cancelled"})

    if text_content == "❓ راهنما و پشتیبانی":
        _set_awaiting_broadcast(bot_user, False)
        return _handle_help_command(chat_id)

    if text_content == "🌐 پنل وب":
        _set_awaiting_broadcast(bot_user, False)
        adapter.send_text(
            chat_id,
            f"🌐 برای مدیریت کامل کانال‌ها، پروفایل‌ها و گزارش ارسال‌ها روی [ورود به پنل وین فوروارد]({_WINJOB_FORWARD_URL}) بزنید.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🌐 باز کردن پنل وین فوروارد", "url": _WINJOB_FORWARD_URL}]
                ]
            },
        )
        return JsonResponse({"ok": True, "status": "web panel sent"})

    # ۲. بررسی حالت مرحله‌ای (کاربر باید اول دکمه «📤 ارسال پیام» را زده باشد)
    is_awaiting = bool((bot_user.session_data or {}).get("awaiting_broadcast"))
    if not is_awaiting:
        adapter.send_text(
            chat_id,
            "برای ارسال پیام یا فایل به کانال‌ها، لطفاً اول دکمه **«📤 ارسال پیام»** را از منوی پایین بزنید 👇",
            reply_markup=_USER_KEYBOARD,
        )
        return JsonResponse({"ok": True, "status": "not awaiting broadcast"})

    # کاربر همچنان در حالت ارسال پیام باقی می‌ماند تا با «🔙 بازگشت به منوی اصلی» خارج شود

    # ۳. استخراج نوع محتوا و file_id
    content_type = "text"
    platform_file_id = None
    original_file_name = ""

    if "sticker" in message:
        content_type = "sticker"
        platform_file_id = message["sticker"]["file_id"]
        text_content = ""
    elif "animation" in message:
        content_type = "animation"
        platform_file_id = message["animation"]["file_id"]
        original_file_name = message["animation"].get("file_name") or ""
        text_content = message.get("caption", "")
    elif "photo" in message:
        content_type = "photo"
        platform_file_id = message["photo"][-1]["file_id"]
        text_content = message.get("caption", "")
    elif "video" in message:
        content_type = "video"
        platform_file_id = message["video"]["file_id"]
        original_file_name = message["video"].get("file_name") or ""
        text_content = message.get("caption", "")
    elif "voice" in message:
        content_type = "voice"
        platform_file_id = message["voice"]["file_id"]
        original_file_name = message["voice"].get("file_name") or ""
        text_content = message.get("caption", "")
    elif "audio" in message:
        content_type = "audio"
        audio_obj = message["audio"]
        platform_file_id = audio_obj["file_id"]
        original_file_name = audio_obj.get("file_name") or ""
        if not original_file_name and audio_obj.get("title"):
            original_file_name = f"{audio_obj['title']}.mp3"
        text_content = message.get("caption", "")
    elif "document" in message:
        doc_obj = message["document"]
        platform_file_id = doc_obj["file_id"]
        original_file_name = doc_obj.get("file_name") or ""
        doc_mime = (doc_obj.get("mime_type") or "").lower()
        if doc_mime.startswith("audio/") or original_file_name.lower().endswith((".mp3", ".m4a", ".wav", ".flac", ".aac")):
            content_type = "audio"
        else:
            content_type = "document"
        text_content = message.get("caption", "")

    if not text_content and not platform_file_id:
        adapter.send_text(chat_id, "⚠️ محتوای پیام قابل پردازش نبود.", reply_markup=_USER_KEYBOARD)
        return JsonResponse({"ok": True, "status": "empty message"})

    file_ids_payload = {}
    if platform_file_id:
        file_ids_payload["bale"] = platform_file_id
        if original_file_name:
            file_ids_payload["bale_file_name"] = original_file_name

    try:
        msg = BroadcastMessage.objects.create(
            user=bot_user.user,
            content_type=content_type,
            text=text_content,
            platform_file_ids=file_ids_payload,
        )
        job = BroadcastJob.objects.create(message=msg, status=BroadcastJob.Status.DRAFT)
    except Exception as exc:
        logger.exception(f"Failed to create draft message/job: {exc}")
        adapter.send_text(chat_id, f"❌ خطا در ساخت پیش‌نویس: {exc}", reply_markup=_USER_KEYBOARD)
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)

    from product.forward.subscriptions.access import user_has_platform_access
    if not user_has_platform_access(bot_user.user, "bale"):
        adapter.send_text(
            chat_id,
            "🔒 اشتراک وین‌فوروارد شما فعال نیست یا منقضی شده است.\n"
            "لطفاً ابتدا از سایت اشتراک خود را فعال یا تمدید کنید.",
            reply_markup={"inline_keyboard": [[{"text": "💎 خرید اشتراک", "url": _WINJOB_PLANS_URL}]]},
        )
        return JsonResponse({"ok": True, "status": "subscription required"})

    channels = BroadcastChannel.objects.filter(user=bot_user.user, is_active=True, bot_is_admin=True)
    if not channels.exists():
        adapter.send_text(
            chat_id,
            "⚠️ هنوز هیچ کانال فعالی با دسترسی ادمین ندارید.",
            reply_markup=_USER_KEYBOARD,
        )
        return JsonResponse({"ok": True, "status": "no channels"})

    reply_markup = _build_draft_keyboard(job)
    try:
        adapter.send_text(
            chat_id,
            "📝 **پیش‌نویس پیام شما آماده شد!**\nپروفایل یا کانال‌های مقصد را انتخاب کنید و «🚀 تایید و ارسال» را بزنید (یا پیام بعدی خود را بفرستید):",
            reply_markup=reply_markup,
        )
    except Exception as exc:
        logger.exception(f"Failed to send draft keyboard: {exc}")

    return JsonResponse({"ok": True, "status": "draft created"})
