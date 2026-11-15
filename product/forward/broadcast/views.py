"""ویوهای پنل وب وین فوروارد (همراه با ارسال لوگوهای پلتفرم از دیتابیس و داده‌های تحلیلی داشبورد)."""

from datetime import timedelta
import json
import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from product.forward.broadcast.forms import BroadcastSendForm
from product.forward.broadcast.models import BroadcastChannel, BroadcastJob, BroadcastTarget
from product.forward.broadcast.services.dispatcher import dispatch_job, enqueue_dispatch_job


def _get_forward_platforms_map() -> dict:
    """واکشی دیکشنری پلتفرم‌های وین‌فوروارد از دیتابیس (شامل فیلد logo) بر اساس اسلاگ."""
    from core.models import Platform

    qs = Platform.objects.filter(slug__in=["bale", "eitaa", "rubika"])
    return {p.slug: p for p in qs}


def _format_persian_date() -> str:
    """تولید رشته تاریخ شمسی خوانا مشابه داشبورد وین‌دایرکت و تبلیغ‌دهندگان."""
    today = jdatetime.date.today()
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

    return render(
        request,
        "product/forward/broadcast/send.html",
        {
            "form": form,
            "nav_platforms": nav_platforms,
        },
    )


@login_required
def job_detail(request, job_id):
    """نمایش جزئیات یک عملیات ارسال همگانی و وضعیت تحویل به تفکیک هر کانال."""
    nav_platforms = _get_forward_platforms_map()
    job = get_object_or_404(BroadcastJob.objects.select_related("message"), pk=job_id, message__user=request.user)
    targets = job.targets.select_related("channel", "channel__platform").all()
    total_targets = job.total_targets or targets.count()
    success_rate = int(round((job.success_count / total_targets) * 100)) if total_targets > 0 else 0

    return render(
        request,
        "product/forward/broadcast/job_detail.html",
        {
            "job": job,
            "targets": targets,
            "success_rate": success_rate,
            "nav_platforms": nav_platforms,
        },
    )


@method_decorator(login_required, name="dispatch")
class JobListView(ListView):
    """نمایش تاریخچه عملیات‌های ارسال همگانی کاربر به همراه آمار کلی."""

    model = BroadcastJob
    template_name = "product/forward/broadcast/job_list.html"
    context_object_name = "jobs"
    paginate_by = 15

    def get_queryset(self):
        """واکشی جاب‌های مربوط به کاربر لاگین‌شده به همراه کانال‌ها و پلتفرم‌های مقصد."""
        return (
            BroadcastJob.objects.filter(message__user=self.request.user)
            .select_related("message")
            .prefetch_related("targets__channel__platform")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        """افزودن آمار کلی ارسال‌ها و لوگوهای پلتفرم به کانتکست صفحه تاریخچه."""
        ctx = super().get_context_data(**kwargs)
        ctx["nav_platforms"] = _get_forward_platforms_map()
        qs = BroadcastJob.objects.filter(message__user=self.request.user)
        agg = qs.aggregate(
            total_sent=Sum("success_count"),
            total_failed=Sum("failed_count"),
        )
        ctx["total_jobs_count"] = qs.count()
        ctx["total_sent_count"] = agg["total_sent"] or 0
        ctx["total_failed_count"] = agg["total_failed"] or 0
        return ctx


# ============================================================
# Eitaa Web Panel Views
# ============================================================


@login_required
def eitaa_connect_token(request):
    """صفحه اتصال توکن ایتایار (گام ۱)."""
    from product.forward.subscriptions.access import user_has_platform_access

    if not user_has_platform_access(request.user, "eitaa"):
        messages.warning(request, "🔒 برای اتصال و استفاده از ایتا ابتدا باید اشتراک فعال آن را تهیه کنید.")
        return redirect("forward_subscriptions:plans")

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
    """صفحه لیست و مدیریت کانال‌های ایتا."""
    from core.models import Platform
    from product.forward.messengers.models import BotUser
    from product.forward.subscriptions.access import get_user_platform_access_map

    nav_platforms = _get_forward_platforms_map()
    eitaa_platform = nav_platforms.get("eitaa") or Platform.objects.filter(slug="eitaa").first()
    if not eitaa_platform:
        messages.error(request, "پلتفرم ایتا در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    bot_user = BotUser.objects.filter(user=request.user, platform=eitaa_platform).first()
    channels = (
        BroadcastChannel.objects.filter(user=request.user, platform=eitaa_platform, is_active=True)
        .select_related("platform")
        .order_by("-created_at")
    )
    access_map = get_user_platform_access_map(request.user)

    return render(
        request,
        "product/forward/broadcast/eitaa/channels.html",
        {
            "bot_user": bot_user,
            "channels": channels,
            "platform": eitaa_platform,
            "platform_access": access_map.get("eitaa"),
            "nav_platforms": nav_platforms,
        },
    )


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


# ============================================================
# Rubika Web Panel Views
# ============================================================


@login_required
def rubika_connect_phone(request):
    """گام اول اتصال به روبیکا: دریافت شماره موبایل و ارسال کد تایید (OTP)."""
    from product.forward.subscriptions.access import user_has_platform_access

    if not user_has_platform_access(request.user, "rubika"):
        messages.warning(request, "🔒 برای اتصال و استفاده از روبیکا ابتدا باید اشتراک فعال آن را تهیه کنید.")
        return redirect("forward_subscriptions:plans")

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
    """صفحه لیست و مدیریت کانال‌های متصل‌شده روبیکا."""
    from core.models import Platform
    from product.forward.messengers.models import BotUser
    from product.forward.subscriptions.access import get_user_platform_access_map

    nav_platforms = _get_forward_platforms_map()
    rubika_platform = nav_platforms.get("rubika") or Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    bot_user = BotUser.objects.filter(user=request.user, platform=rubika_platform).first()
    channels = (
        BroadcastChannel.objects.filter(user=request.user, platform=rubika_platform, is_active=True)
        .select_related("platform")
        .order_by("-created_at")
    )
    access_map = get_user_platform_access_map(request.user)

    return render(
        request,
        "product/forward/broadcast/rubika/channels.html",
        {
            "bot_user": bot_user,
            "channels": channels,
            "platform": rubika_platform,
            "platform_access": access_map.get("rubika"),
            "nav_platforms": nav_platforms,
        },
    )


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

    synced_count = 0
    for ch in found_channels:
        BroadcastChannel.objects.update_or_create(
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
        synced_count += 1

    messages.success(request, f"✅ {synced_count} کانال روبیکا همگام‌سازی شد.")
    return redirect("broadcast:rubika_channels")


@login_required
def rubika_add_channel(request):
    """صفحه افزودن دستی کانال روبیکا با نام کاربری یا شناسه GUID."""
    from core.models import Platform
    from product.forward.broadcast.forms import RubikaChannelForm
    from product.forward.messengers.adapters.rubika import RubikaAdapter
    from product.forward.messengers.models import BotUser

    nav_platforms = _get_forward_platforms_map()
    rubika_platform = nav_platforms.get("rubika") or Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    bot_user = BotUser.objects.filter(user=request.user, platform=rubika_platform).first()

    if not bot_user or not bot_user.has_rubika_session:
        messages.warning(request, "ابتدا باید حساب روبیکای خود را متصل کنید.")
        return redirect("broadcast:rubika_connect_phone")

    session_data = bot_user.session_data or {}
    adapter = RubikaAdapter(
        auth=session_data.get("auth"),
        private_key=session_data.get("private_key"),
    )

    if request.method == "POST":
        form = RubikaChannelForm(request.POST, user=request.user, rubika_adapter=adapter)
        if form.is_valid() and form.resolved_channel:
            resolved = form.resolved_channel
            channel, _created = BroadcastChannel.objects.update_or_create(
                user=request.user,
                platform=rubika_platform,
                chat_id=resolved["chat_id"],
                defaults={
                    "title": resolved["title"],
                    "username": resolved["username"],
                    "bot_is_admin": True,
                    "bot_admin_checked_at": timezone.now(),
                    "is_active": True,
                },
            )
            messages.success(request, f"✅ کانال «{channel.title}» با موفقیت به وین‌فوروارد متصل شد.")
            return redirect("broadcast:rubika_channels")
    else:
        form = RubikaChannelForm(user=request.user, rubika_adapter=adapter)

    return render(
        request,
        "product/forward/broadcast/rubika/add_channel.html",
        {
            "form": form,
            "bot_user": bot_user,
            "platform": rubika_platform,
            "nav_platforms": nav_platforms,
        },
    )


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


# ============================================================
# WinForward Unified Dashboard & Bale Views
# ============================================================


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

    channels_by_slug = {"bale": [], "eitaa": [], "rubika": []}
    for ch in active_channels:
        if ch.platform.slug in channels_by_slug:
            channels_by_slug[ch.platform.slug].append(ch)

    bale_connect_link = ""
    try:
        bale_connect_link = generate_connect_link(request.user, "bale")
    except Exception:
        bale_connect_link = "https://ble.ir/win_forward_bot"

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
    ]

    platform_cards = []
    connected_platforms_count = 0
    for p in platform_definitions:
        slug = p["slug"]
        p_obj = nav_platforms.get(slug)
        logo_url = p_obj.logo.url if (p_obj and p_obj.logo) else ""
        acc = access_map.get(slug)
        has_sub = bool(acc and acc.is_valid)
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
                "remaining_days": acc.remaining_days if has_sub else 0,
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

    # داده‌های نمودار ۳۰ روز اخیر ارسال‌ها
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    daily_stats = (
        BroadcastJob.objects.filter(message__user=request.user, created_at__gte=last_30_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            sent_sum=Sum("success_count"),
            failed_sum=Sum("failed_count"),
        )
        .order_by("day")
    )
    activity_labels = []
    activity_success_data = []
    activity_failed_data = []
    for item in daily_stats:
        if item["day"]:
            jalali = jdatetime.date.fromgregorian(date=item["day"])
            activity_labels.append(jalali.strftime("%m/%d"))
            activity_success_data.append(item["sent_sum"] or 0)
            activity_failed_data.append(item["failed_sum"] or 0)

    bale_access = access_map.get("bale")
    subscription_days_left = bale_access.remaining_days if (bale_access and bale_access.is_valid) else 0
    active_plan_name = bale_access.plan.name if (bale_access and bale_access.plan) else ""

    return render(
        request,
        "product/forward/broadcast/dashboard.html",
        {
            "account": account,
            "access_map": access_map,
            "nav_platforms": nav_platforms,
            "platform_cards": platform_cards,
            "subscribed_platforms_count": len(access_map),
            "connected_platforms_count": connected_platforms_count,
            "total_channels_count": active_channels.count(),
            "total_jobs_count": total_jobs_count,
            "total_sent_count": agg["total_sent"] or 0,
            "total_failed_count": agg["total_failed"] or 0,
            "recent_jobs": recent_jobs,
            "bale_connect_link": bale_connect_link,
            "subscription_days_left": subscription_days_left,
            "active_plan_name": active_plan_name,
            "wallet_balance": wallet_balance,
            "persian_date": _format_persian_date(),
            "activity_labels_json": json.dumps(activity_labels, ensure_ascii=False),
            "activity_success_data_json": json.dumps(activity_success_data, ensure_ascii=False),
            "activity_failed_data_json": json.dumps(activity_failed_data, ensure_ascii=False),
        },
    )


@login_required
def bale_connect(request):
    """صفحه راهنما و دریافت لینک یک‌بارمصرف اتصال حساب بله به ربات وین فوروارد."""
    from product.forward.subscriptions.access import user_has_platform_access

    if not user_has_platform_access(request.user, "bale"):
        messages.warning(request, "🔒 برای اتصال و استفاده از بله ابتدا باید اشتراک فعال وین‌فوروارد داشته باشید.")
        return redirect("forward_subscriptions:plans")

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
    """صفحه لیست و مدیریت کانال‌های متصل‌شده کاربر در پیام‌رسان بله."""
    from core.models import Platform
    from product.forward.messengers.models import BotUser
    from product.forward.subscriptions.access import get_user_platform_access_map

    nav_platforms = _get_forward_platforms_map()
    bale_platform = nav_platforms.get("bale") or Platform.objects.filter(slug="bale").first()
    if not bale_platform:
        messages.error(request, "پلتفرم بله در سیستم ثبت نشده است.")
        return redirect("broadcast:dashboard")

    bot_user = BotUser.objects.filter(user=request.user, platform=bale_platform).first()
    channels = (
        BroadcastChannel.objects.filter(user=request.user, platform=bale_platform, is_active=True)
        .select_related("platform")
        .order_by("-created_at")
    )
    access_map = get_user_platform_access_map(request.user)

    return render(
        request,
        "product/forward/broadcast/bale/channels.html",
        {
            "bot_user": bot_user,
            "channels": channels,
            "platform": bale_platform,
            "platform_access": access_map.get("bale"),
            "nav_platforms": nav_platforms,
        },
    )


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
