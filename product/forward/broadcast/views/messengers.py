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
def bale_connect(request):
    """صفحه راهنما و دریافت لینک یک‌بارمصرف اتصال حساب بله به ربات وین فوروارد."""
    from product.forward.subscriptions.access import user_has_platform_access

    # در سیستم توکنی، اتصال حساب‌ها و کانال‌ها برای همه کاربران آزاد است

    from core.models import Platform
    from product.forward.messengers.models import BotUser
    from product.forward.messengers.services import generate_connect_link

    nav_platforms = _get_forward_platforms_map()
    bale_platform = nav_platforms.get("bale") or Platform.objects.filter(slug="bale").first()
    existing_bot_user = (
        BotUser.objects.filter(user=request.user, platform=bale_platform).first() if bale_platform else None
    )

    connect_link = ""
    if bale_platform:
        connect_link = generate_connect_link(request.user, "bale")

    return render(
        request,
        "product/forward/broadcast/bale/connect.html",
        {
            "existing_bot_user": existing_bot_user,
            "connect_link": connect_link,
            "platform": bale_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def bale_channels(request):
    """هدایت به صفحه یکپارچه کانال‌های متصل با فیلتر پیش‌فرض bale."""
    return redirect(f"{reverse('broadcast:connected_channels')}?platform=bale")



@login_required
def bale_delete_channel(request, channel_id):
    """غیرفعال‌سازی کانال بله توسط کاربر (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:bale_channels")

    channel = get_object_or_404(
        BroadcastChannel,
        pk=channel_id,
        user=request.user,
        platform__slug="bale",
    )
    channel.is_active = False
    channel.save(update_fields=["is_active"])
    messages.success(request, f"کانال «{channel.title}» در بله غیرفعال شد.")
    return redirect("broadcast:bale_channels")



@login_required
def bale_sync_avatars(request):
    """بروزرسانی عکس پروفایل واقعی کانال‌های بله کاربر (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:bale_channels")

    from product.forward.broadcast.services.channel_sync import sync_channel_avatar
    from product.forward.messengers.adapters.registry import get_adapter

    adapter = get_adapter("bale")
    bale_channels = BroadcastChannel.objects.filter(
        user=request.user, platform__slug="bale", is_active=True
    )
    updated_count = 0
    for ch in bale_channels:
        if sync_channel_avatar(ch, adapter=adapter):
            updated_count += 1

    messages.success(request, f"✅ عکس پروفایل {updated_count} کانال بله بروزرسانی شد.")
    return redirect("broadcast:bale_channels")



@login_required
def telegram_connect(request):
    """صفحه راهنما و دریافت لینک یک‌بارمصرف اتصال حساب تلگرام به ربات وین فوروارد."""
    from product.forward.subscriptions.access import user_has_platform_access

    # در سیستم توکنی، اتصال حساب‌ها و کانال‌ها برای همه کاربران آزاد است

    from core.models import Platform
    from product.forward.messengers.adapters.registry import get_adapter
    from product.forward.messengers.models import BotUser
    from product.forward.messengers.services import generate_connect_link

    nav_platforms = _get_forward_platforms_map()
    telegram_platform = nav_platforms.get("telegram") or Platform.objects.filter(slug="telegram").first()
    existing_bot_user = (
        BotUser.objects.filter(user=request.user, platform=telegram_platform).first() if telegram_platform else None
    )

    connect_link = ""
    if telegram_platform:
        tg_username = ""
        try:
            tg_adapter = get_adapter("telegram")
            if tg_adapter:
                tg_username = tg_adapter.get_bot_username()
        except Exception:
            pass
        connect_link = generate_connect_link(request.user, "telegram", bot_username=tg_username)

    return render(
        request,
        "product/forward/broadcast/telegram/connect.html",
        {
            "existing_bot_user": existing_bot_user,
            "connect_link": connect_link,
            "platform": telegram_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def telegram_channels(request):
    """هدایت به صفحه یکپارچه کانال‌های متصل با فیلتر پیش‌فرض telegram."""
    return redirect(f"{reverse('broadcast:connected_channels')}?platform=telegram")



@login_required
def telegram_delete_channel(request, channel_id):
    """غیرفعال‌سازی کانال تلگرام توسط کاربر (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:telegram_channels")

    channel = get_object_or_404(
        BroadcastChannel,
        pk=channel_id,
        user=request.user,
        platform__slug="telegram",
    )
    channel.is_active = False
    channel.save(update_fields=["is_active"])
    messages.success(request, f"کانال «{channel.title}» در تلگرام غیرفعال شد.")
    return redirect("broadcast:telegram_channels")



@login_required
def telegram_sync_avatars(request):
    """بروزرسانی عکس پروفایل واقعی کانال‌های تلگرام کاربر (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:telegram_channels")

    from product.forward.broadcast.services.channel_sync import sync_channel_avatar
    from product.forward.messengers.adapters.registry import get_adapter

    adapter = get_adapter("telegram")
    tg_channels = BroadcastChannel.objects.filter(
        user=request.user, platform__slug="telegram", is_active=True
    )
    updated_count = 0
    for ch in tg_channels:
        if sync_channel_avatar(ch, adapter=adapter):
            updated_count += 1

    messages.success(request, f"✅ عکس پروفایل {updated_count} کانال تلگرام بروزرسانی شد.")
    return redirect("broadcast:telegram_channels")



@login_required
def eitaa_connect_token(request):
    """صفحه اتصال توکن ایتایار (گام ۱)."""
    from product.forward.subscriptions.access import user_has_platform_access

    # در سیستم توکنی، اتصال حساب‌ها و کانال‌ها برای همه کاربران آزاد است

    from core.models import Platform
    from product.forward.broadcast.forms import EitaaTokenForm
    from product.forward.messengers.models import BotUser

    nav_platforms = _get_forward_platforms_map()
    eitaa_platform = nav_platforms.get("eitaa") or Platform.objects.filter(slug="eitaa").first()
    if not eitaa_platform:
        messages.error(request, "پلتفرم ایتا در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    existing_bot_user = BotUser.objects.filter(user=request.user, platform=eitaa_platform).first()

    if request.method == "POST":
        form = EitaaTokenForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data["api_token"]

            bot_user, created = BotUser.objects.get_or_create(
                user=request.user,
                platform=eitaa_platform,
                defaults={
                    "chat_id": f"eitaa_user_{request.user.id}",
                    "is_verified": True,
                    "api_token": token,
                },
            )
            if not created:
                bot_user.api_token = token
                bot_user.is_verified = True
                bot_user.save(update_fields=["api_token", "is_verified"])

            messages.success(
                request,
                "✅ توکن ایتایار با موفقیت ذخیره شد. حالا می‌توانید کانال‌های خود را اضافه کنید.",
            )
            return redirect("broadcast:eitaa_channels")
    else:
        form = EitaaTokenForm()

    return render(
        request,
        "product/forward/broadcast/eitaa/connect_token.html",
        {
            "form": form,
            "existing_bot_user": existing_bot_user,
            "platform": eitaa_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def eitaa_channels(request):
    """هدایت به صفحه یکپارچه کانال‌های متصل با فیلتر پیش‌فرض eitaa."""
    return redirect(f"{reverse('broadcast:connected_channels')}?platform=eitaa")



@login_required
def eitaa_add_channel(request):
    """صفحه افزودن کانال جدید ایتا به همراه تست ارسال."""
    from core.models import Platform
    from product.forward.broadcast.forms import EitaaChannelForm
    from product.forward.messengers.models import BotUser

    nav_platforms = _get_forward_platforms_map()
    eitaa_platform = nav_platforms.get("eitaa") or Platform.objects.filter(slug="eitaa").first()
    if not eitaa_platform:
        messages.error(request, "پلتفرم ایتا در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    bot_user = BotUser.objects.filter(user=request.user, platform=eitaa_platform).first()

    if not bot_user or not bot_user.api_token:
        messages.warning(request, "ابتدا باید توکن ایتایار خود را ثبت کنید.")
        return redirect("broadcast:eitaa_connect_token")

    if request.method == "POST":
        form = EitaaChannelForm(request.POST, user=request.user, api_token=bot_user.api_token)
        if form.is_valid():
            chat_id = form.cleaned_data["chat_id"]
            title = form.cleaned_data["title"]
            username = form.cleaned_data.get("username", "")

            channel, _created = BroadcastChannel.objects.update_or_create(
                user=request.user,
                platform=eitaa_platform,
                chat_id=chat_id,
                defaults={
                    "title": title,
                    "username": username or "",
                    "bot_is_admin": True,
                    "bot_admin_checked_at": timezone.now(),
                    "is_active": True,
                },
            )

            messages.success(request, f"✅ کانال «{channel.title}» با موفقیت متصل شد.")
            return redirect("broadcast:eitaa_channels")
    else:
        form = EitaaChannelForm(user=request.user, api_token=bot_user.api_token)

    return render(
        request,
        "product/forward/broadcast/eitaa/add_channel.html",
        {
            "form": form,
            "bot_user": bot_user,
            "platform": eitaa_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def eitaa_delete_channel(request, channel_id):
    """غیرفعال‌سازی کانال ایتا (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:eitaa_channels")

    channel = get_object_or_404(
        BroadcastChannel,
        pk=channel_id,
        user=request.user,
        platform__slug="eitaa",
    )
    channel.is_active = False
    channel.save(update_fields=["is_active"])
    messages.success(request, f"کانال «{channel.title}» غیرفعال شد.")
    return redirect("broadcast:eitaa_channels")



@login_required
def rubika_connect_phone(request):
    """گام اول اتصال به روبیکا: دریافت شماره موبایل و ارسال کد تایید (OTP)."""
    from product.forward.subscriptions.access import user_has_platform_access

    # در سیستم توکنی، اتصال حساب‌ها و کانال‌ها برای همه کاربران آزاد است

    from core.models import Platform
    from product.forward.broadcast.forms import RubikaPhoneForm
    from product.forward.messengers.adapters.base import MessengerError
    from product.forward.messengers.adapters.rubika import RubikaAdapter
    from product.forward.messengers.models import BotUser

    nav_platforms = _get_forward_platforms_map()
    rubika_platform = nav_platforms.get("rubika") or Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    existing_bot_user = BotUser.objects.filter(user=request.user, platform=rubika_platform).first()

    if request.method == "POST":
        form = RubikaPhoneForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone_number"]
            adapter = RubikaAdapter()
            try:
                otp_res = adapter.send_code(phone_number=phone)
            except (MessengerError, ValueError) as exc:
                messages.error(request, f"خطا در ارسال کد تایید روبیکا: {exc}")
            else:
                request.session["rubika_otp_phone"] = phone
                request.session["rubika_otp_hash"] = otp_res["phone_code_hash"]
                request.session["rubika_otp_tmp"] = otp_res["tmp_session"]
                messages.info(request, "کد تایید به حساب روبیکا یا شماره موبایل شما ارسال شد.")
                return redirect("broadcast:rubika_verify_code")
    else:
        form = RubikaPhoneForm()

    return render(
        request,
        "product/forward/broadcast/rubika/connect_phone.html",
        {
            "form": form,
            "existing_bot_user": existing_bot_user,
            "platform": rubika_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def rubika_verify_code(request):
    """گام دوم اتصال به روبیکا: تایید کد OTP و ذخیره نشست دائمی در BotUser."""
    from core.models import Platform
    from product.forward.broadcast.forms import RubikaVerifyCodeForm
    from product.forward.messengers.adapters.base import MessengerError
    from product.forward.messengers.adapters.rubika import RubikaAdapter
    from product.forward.messengers.models import BotUser

    phone = request.session.get("rubika_otp_phone")
    phone_code_hash = request.session.get("rubika_otp_hash")
    tmp_session = request.session.get("rubika_otp_tmp")

    if not all([phone, phone_code_hash, tmp_session]):
        messages.warning(request, "اطلاعات نشست موقت منقضی شده است؛ لطفاً دوباره شماره خود را وارد کنید.")
        return redirect("broadcast:rubika_connect_phone")

    nav_platforms = _get_forward_platforms_map()
    rubika_platform = nav_platforms.get("rubika") or Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    if request.method == "POST":
        form = RubikaVerifyCodeForm(request.POST)
        if form.is_valid():
            adapter = RubikaAdapter()
            try:
                creds = adapter.sign_in(
                    phone_number=phone,
                    phone_code=form.cleaned_data["phone_code"],
                    phone_code_hash=phone_code_hash,
                    tmp_session=tmp_session,
                )
            except (MessengerError, ValueError) as exc:
                messages.error(request, f"کد تایید نامعتبر است یا خطایی رخ داد: {exc}")
            else:
                user_info = creds.get("user") or {}
                user_guid = user_info.get("user_guid") or f"rubika_user_{request.user.id}"
                session_payload = {
                    "auth": creds["auth"],
                    "private_key": creds["private_key"],
                    "phone_number": phone,
                    "user_guid": user_guid,
                }

                bot_user, created = BotUser.objects.get_or_create(
                    user=request.user,
                    platform=rubika_platform,
                    defaults={
                        "chat_id": user_guid,
                        "username": user_info.get("username", "") or "",
                        "is_verified": True,
                        "session_data": session_payload,
                    },
                )
                if not created:
                    bot_user.chat_id = user_guid
                    bot_user.username = user_info.get("username", "") or ""
                    bot_user.is_verified = True
                    bot_user.session_data = session_payload
                    bot_user.last_seen_at = timezone.now()
                    bot_user.save(update_fields=["chat_id", "username", "is_verified", "session_data", "last_seen_at"])

                for key in ("rubika_otp_phone", "rubika_otp_hash", "rubika_otp_tmp"):
                    request.session.pop(key, None)

                messages.success(request, "✅ حساب روبیکای شما با موفقیت متصل شد.")
                return redirect("broadcast:rubika_channels")
    else:
        form = RubikaVerifyCodeForm()

    return render(
        request,
        "product/forward/broadcast/rubika/verify_code.html",
        {
            "form": form,
            "phone": phone,
            "platform": rubika_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def rubika_channels(request):
    """هدایت به صفحه یکپارچه کانال‌های متصل با فیلتر پیش‌فرض rubika."""
    return redirect(f"{reverse('broadcast:connected_channels')}?platform=rubika")



@login_required
def rubika_sync_channels(request):
    """همگام‌سازی خودکار کانال‌هایی که کاربر در روبیکا دسترسی ارسال پیام دارد (POST only)."""
    from core.models import Platform
    from product.forward.messengers.adapters.base import MessengerError
    from product.forward.messengers.adapters.rubika import RubikaAdapter
    from product.forward.messengers.models import BotUser

    if request.method != "POST":
        return redirect("broadcast:rubika_channels")

    rubika_platform = Platform.objects.filter(slug="rubika").first()
    bot_user = BotUser.objects.filter(user=request.user, platform=rubika_platform).first() if rubika_platform else None

    if not bot_user or not bot_user.has_rubika_session:
        messages.warning(request, "ابتدا باید وارد حساب روبیکای خود شوید.")
        return redirect("broadcast:rubika_connect_phone")

    session_data = bot_user.session_data or {}
    adapter = RubikaAdapter(
        auth=session_data.get("auth"),
        private_key=session_data.get("private_key"),
    )

    try:
        found_channels = adapter.get_user_channels()
    except (MessengerError, ValueError) as exc:
        messages.error(request, f"خطا در دریافت لیست کانال‌ها از روبیکا: {exc}")
        return redirect("broadcast:rubika_channels")

    from product.forward.broadcast.services.channel_sync import sync_channel_avatar

    synced_count = 0
    avatar_count = 0
    for ch in found_channels:
        channel_obj, _ = BroadcastChannel.objects.update_or_create(
            user=request.user,
            platform=rubika_platform,
            chat_id=ch["chat_id"],
            defaults={
                "title": ch["title"],
                "username": ch["username"],
                "bot_is_admin": True,
                "bot_admin_checked_at": timezone.now(),
                "is_active": True,
            },
        )
        if sync_channel_avatar(channel_obj, adapter=adapter, avatar_meta=ch.get("avatar_meta")):
            avatar_count += 1
        synced_count += 1

    messages.success(
        request,
        f"✅ {synced_count} کانال روبیکا همگام‌سازی و عکس پروفایل {avatar_count} کانال به‌روزرسانی شد.",
    )
    return redirect("broadcast:rubika_channels")



@login_required
def rubika_delete_channel(request, channel_id):
    """غیرفعال‌سازی کانال روبیکا (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:rubika_channels")

    channel = get_object_or_404(
        BroadcastChannel,
        pk=channel_id,
        user=request.user,
        platform__slug="rubika",
    )
    channel.is_active = False
    channel.save(update_fields=["is_active"])
    messages.success(request, f"کانال «{channel.title}» غیرفعال شد.")
    return redirect("broadcast:rubika_channels")



@login_required
def soroush_connect_phone(request):
    """گام اول اتصال به سروش‌پلاس: دریافت شماره موبایل و ارسال کد تایید (OTP)."""
    from core.models import Platform
    from product.forward.broadcast.forms import SoroushPhoneForm
    from product.forward.messengers.adapters.base import MessengerError
    from product.forward.messengers.adapters.soroush import SoroushAdapter
    from product.forward.messengers.models import BotUser

    nav_platforms = _get_forward_platforms_map()
    soroush_platform = nav_platforms.get("soroush") or Platform.objects.filter(slug="soroush").first()
    if not soroush_platform:
        messages.error(request, "پلتفرم سروش‌پلاس در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    existing_bot_user = BotUser.objects.filter(user=request.user, platform=soroush_platform).first()

    if request.method == "POST":
        form = SoroushPhoneForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone_number"]
            adapter = SoroushAdapter()
            try:
                otp_res = adapter.send_code(phone_number=phone)
            except (MessengerError, ValueError) as exc:
                messages.error(request, f"خطا در ارسال کد تایید سروش‌پلاس: {exc}")
            else:
                request.session["soroush_otp_phone"] = otp_res["phone_number"]
                request.session["soroush_otp_hash"] = otp_res["phone_code_hash"]
                request.session["soroush_otp_tmp"] = otp_res["tmp_session"]
                messages.info(request, "کد تایید به حساب سروش‌پلاس یا پیامک شماره موبایل شما ارسال شد.")
                return redirect("broadcast:soroush_verify_code")
    else:
        form = SoroushPhoneForm()

    return render(
        request,
        "product/forward/broadcast/soroush/connect_phone.html",
        {
            "form": form,
            "existing_bot_user": existing_bot_user,
            "platform": soroush_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def soroush_verify_code(request):
    """گام دوم اتصال به سروش‌پلاس: تایید کد OTP (و رمز دو مرحله‌ای در صورت نیاز) و ذخیره StringSession."""
    from core.models import Platform
    from product.forward.broadcast.forms import SoroushVerifyCodeForm
    from product.forward.messengers.adapters.base import MessengerError
    from product.forward.messengers.adapters.soroush import SoroushAdapter
    from product.forward.messengers.models import BotUser

    phone = request.session.get("soroush_otp_phone")
    phone_code_hash = request.session.get("soroush_otp_hash")
    tmp_session = request.session.get("soroush_otp_tmp")

    if not all([phone, phone_code_hash, tmp_session]):
        messages.warning(request, "اطلاعات نشست موقت منقضی شده است؛ لطفاً دوباره شماره موبایل خود را وارد کنید.")
        return redirect("broadcast:soroush_connect_phone")

    nav_platforms = _get_forward_platforms_map()
    soroush_platform = nav_platforms.get("soroush") or Platform.objects.filter(slug="soroush").first()
    if not soroush_platform:
        messages.error(request, "پلتفرم سروش‌پلاس در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    if request.method == "POST":
        form = SoroushVerifyCodeForm(request.POST)
        if form.is_valid():
            adapter = SoroushAdapter()
            try:
                creds = adapter.sign_in(
                    phone_number=phone,
                    phone_code=form.cleaned_data["phone_code"],
                    phone_code_hash=phone_code_hash,
                    tmp_session=tmp_session,
                    password=form.cleaned_data.get("two_step_password", ""),
                )
            except (MessengerError, ValueError) as exc:
                messages.error(request, f"خطا در تایید کد سروش‌پلاس: {exc}")
            else:
                user_info = creds.get("user") or {}
                splus_uid = user_info.get("id") or f"soroush_user_{request.user.id}"
                session_payload = {
                    "string_session": creds["string_session"],
                    "phone_number": phone,
                    "user_id": splus_uid,
                }

                bot_user, created = BotUser.objects.get_or_create(
                    user=request.user,
                    platform=soroush_platform,
                    defaults={
                        "chat_id": splus_uid,
                        "username": user_info.get("username", "") or "",
                        "is_verified": True,
                        "session_data": session_payload,
                    },
                )
                if not created:
                    bot_user.chat_id = splus_uid
                    bot_user.username = user_info.get("username", "") or ""
                    bot_user.is_verified = True
                    bot_user.session_data = session_payload
                    bot_user.last_seen_at = timezone.now()
                    bot_user.save(update_fields=["chat_id", "username", "is_verified", "session_data", "last_seen_at"])

                for key in ("soroush_otp_phone", "soroush_otp_hash", "soroush_otp_tmp"):
                    request.session.pop(key, None)

                messages.success(request,
                                 "✅ حساب سروش‌پلاس شما با موفقیت متصل شد! حالا می‌توانید کانال‌هایتان را همگام‌سازی کنید.")
                return redirect("broadcast:soroush_channels")
    else:
        form = SoroushVerifyCodeForm()

    return render(
        request,
        "product/forward/broadcast/soroush/verify_code.html",
        {
            "form": form,
            "phone": phone,
            "platform": soroush_platform,
            "nav_platforms": nav_platforms,
        },
    )



@login_required
def soroush_channels(request):
    """هدایت به صفحه یکپارچه کانال‌های متصل با فیلتر پیش‌فرض soroush."""
    return redirect(f"{reverse('broadcast:connected_channels')}?platform=soroush")



@login_required
def soroush_sync_channels(request):
    """همگام‌سازی خودکار کانال‌ها و آواتارهای سروش‌پلاس که کاربر در آن‌ها دسترسی ارسال دارد (POST only)."""
    from django.core.files.base import ContentFile
    from core.models import Platform
    from product.forward.messengers.adapters.base import MessengerError
    from product.forward.messengers.adapters.soroush import SoroushAdapter
    from product.forward.messengers.models import BotUser

    if request.method != "POST":
        return redirect("broadcast:soroush_channels")

    soroush_platform = Platform.objects.filter(slug="soroush").first()
    bot_user = BotUser.objects.filter(user=request.user,
                                      platform=soroush_platform).first() if soroush_platform else None

    if not bot_user or not bot_user.has_soroush_session:
        messages.warning(request, "ابتدا باید وارد حساب سروش‌پلاس خود شوید.")
        return redirect("broadcast:soroush_connect_phone")

    session_data = bot_user.session_data or {}
    adapter = SoroushAdapter(string_session=session_data.get("string_session", ""))

    try:
        found_channels = adapter.get_user_channels(include_avatars=True)
    except MessengerError as exc:
        messages.error(request, f"خطا در همگام‌سازی کانال‌های سروش‌پلاس: {exc}")
        return redirect("broadcast:soroush_channels")

    synced_count = 0
    channel_hashes = dict(session_data.get("channel_hashes") or {})
    for ch in found_channels:
        chat_id = ch["chat_id"]
        obj, _ = BroadcastChannel.objects.update_or_create(
            user=request.user,
            platform=soroush_platform,
            chat_id=chat_id,
            defaults={
                "title": ch["title"],
                "username": ch.get("username") or "",
                "bot_is_admin": True,
                "bot_admin_checked_at": timezone.now(),
                "is_active": True,
            },
        )
        ahash = (ch.get("access_hash") or "").strip()
        if ahash:
            channel_hashes[str(chat_id)] = ahash
            if ch.get("numeric_id"):
                channel_hashes[str(ch["numeric_id"])] = ahash
        avatar_bytes = ch.get("avatar_bytes")
        if avatar_bytes:
            try:
                obj.avatar.save(f"soroush_{obj.pk}.jpg", ContentFile(avatar_bytes), save=True)
            except Exception:
                pass
        synced_count += 1

    if channel_hashes:
        updated_session = dict(session_data)
        updated_session["channel_hashes"] = channel_hashes
        bot_user.session_data = updated_session
        bot_user.save(update_fields=["session_data"])

    if synced_count:
        messages.success(request, f"✅ {synced_count} کانال سروش‌پلاس (همراه با آواتار) با موفقیت همگام‌سازی شد.")
    else:
        messages.info(request, "هیچ کانالی با دسترسی ادمین/ارسال در این حساب سروش‌پلاس یافت نشد.")
    return redirect("broadcast:soroush_channels")



@login_required
def soroush_delete_channel(request, channel_id):
    """غیرفعال‌سازی کانال سروش‌پلاس (POST only)."""
    if request.method != "POST":
        return redirect("broadcast:soroush_channels")

    channel = get_object_or_404(
        BroadcastChannel,
        pk=channel_id,
        user=request.user,
        platform__slug="soroush",
    )
    channel.is_active = False
    channel.save(update_fields=["is_active"])
    messages.success(request, f"کانال «{channel.title}» غیرفعال شد.")
    return redirect("broadcast:soroush_channels")



@login_required
def soroush_logout(request):
    """خروج کامل از نشست سروش‌پلاس و پاک‌سازی امن StringSession (POST only)."""
    from core.models import Platform
    from product.forward.messengers.adapters.soroush import SoroushAdapter
    from product.forward.messengers.models import BotUser

    if request.method != "POST":
        return redirect("broadcast:soroush_channels")

    soroush_platform = Platform.objects.filter(slug="soroush").first()
    bot_user = BotUser.objects.filter(user=request.user,
                                      platform=soroush_platform).first() if soroush_platform else None
    if bot_user and bot_user.has_soroush_session:
        try:
            adapter = SoroushAdapter(string_session=(bot_user.session_data or {}).get("string_session", ""))
            adapter.logout()
        except Exception:
            pass
        bot_user.session_data = {}
        bot_user.is_verified = False
        bot_user.save(update_fields=["session_data", "is_verified"])
        messages.success(request, "✅ نشست سروش‌پلاس با موفقیت قطع و پاک‌سازی شد.")
    return redirect("broadcast:dashboard")

