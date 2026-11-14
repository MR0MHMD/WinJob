"""ویوهای پنل وب وین فوروارد."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from product.forward.broadcast.forms import BroadcastSendForm
from product.forward.broadcast.models import BroadcastJob, BroadcastTarget
from product.forward.broadcast.services.dispatcher import dispatch_job
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect


@login_required
def send_broadcast(request):
    """صفحه ارسال پیام جدید به کانال‌ها از طریق پنل وب."""
    if request.method == "POST":
        form = BroadcastSendForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            message = form.save(commit=False)
            message.user = request.user
            message.save()

            job = BroadcastJob.objects.create(message=message)
            selected_channels = form.cleaned_data["channels"]

            for channel in selected_channels:
                BroadcastTarget.objects.create(job=job, channel=channel)

            dispatch_job(job.pk)
            job.refresh_from_db()

            if job.status == BroadcastJob.Status.DONE:
                messages.success(request, f"✅ پیام با موفقیت به {job.success_count} کانال ارسال شد.")
            else:
                messages.warning(request, f"⚠️ ارسال انجام شد: {job.success_count} موفق، {job.failed_count} ناموفق.")

            return redirect("broadcast:job_detail", job_id=job.pk)
    else:
        form = BroadcastSendForm(user=request.user)

    return render(request, "product/forward/broadcast/send.html", {"form": form})


@login_required
def job_detail(request, job_id):
    """نمایش جزئیات یک جاب و وضعیت ارسال به هر کانال."""
    job = get_object_or_404(BroadcastJob, pk=job_id, message__user=request.user)
    targets = job.targets.select_related("channel").all()
    return render(request, "product/forward/broadcast/job_detail.html", {"job": job, "targets": targets})


@method_decorator(login_required, name='dispatch')
class JobListView(ListView):
    """نمایش تاریخچه جاب‌های ارسال کاربر."""
    model = BroadcastJob
    template_name = "product/forward/broadcast/job_list.html"
    context_object_name = "jobs"
    paginate_by = 15

    def get_queryset(self):
        """فقط جاب‌های مربوط به کاربر لاگین شده را برمی‌گرداند."""
        return BroadcastJob.objects.filter(message__user=self.request.user).select_related("message").order_by(
            "-created_at")


# ============================================================
# Eitaa Web Panel Views
# ============================================================


@login_required
def eitaa_connect_token(request):
    """صفحه اتصال توکن ایتایار (گام ۱)."""
    from core.models import Platform
    from product.forward.broadcast.forms import EitaaTokenForm
    from product.forward.messengers.models import BotUser

    eitaa_platform = Platform.objects.filter(slug="eitaa").first()
    if not eitaa_platform:
        messages.error(request, "پلتفرم ایتا در سیستم ثبت نشده است.")
        return redirect("broadcast:job_list")

    existing_bot_user = BotUser.objects.filter(
        user=request.user, platform=eitaa_platform
    ).first()

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
                "✅ توکن ایتایار با موفقیت ذخیره شد. حالا می‌توانید کانال‌های خود را اضافه کنید."
            )
            return redirect("broadcast:eitaa_channels")
    else:
        form = EitaaTokenForm()

    return render(request, "product/forward/broadcast/eitaa/connect_token.html", {
        "form": form,
        "existing_bot_user": existing_bot_user,
    })


@login_required
def eitaa_channels(request):
    """صفحه لیست و مدیریت کانال‌های ایتا (گام ۲ - لیست)."""
    from core.models import Platform
    from product.forward.broadcast.models import BroadcastChannel
    from product.forward.messengers.models import BotUser

    eitaa_platform = Platform.objects.filter(slug="eitaa").first()
    if not eitaa_platform:
        messages.error(request, "پلتفرم ایتا در سیستم ثبت نشده است.")
        return redirect("broadcast:job_list")

    bot_user = BotUser.objects.filter(
        user=request.user, platform=eitaa_platform
    ).first()

    channels = BroadcastChannel.objects.filter(
        user=request.user, platform=eitaa_platform
    ).order_by("-created_at")

    return render(request, "product/forward/broadcast/eitaa/channels.html", {
        "bot_user": bot_user,
        "channels": channels,
    })


@login_required
def eitaa_add_channel(request):
    """صفحه افزودن کانال جدید ایتا (گام ۲ - افزودن)."""
    from core.models import Platform
    from product.forward.broadcast.forms import EitaaChannelForm
    from product.forward.messengers.models import BotUser

    eitaa_platform = Platform.objects.filter(slug="eitaa").first()
    if not eitaa_platform:
        messages.error(request, "پلتفرم ایتا در سیستم ثبت نشده است.")
        return redirect("broadcast:job_list")

    bot_user = BotUser.objects.filter(
        user=request.user, platform=eitaa_platform
    ).first()

    if not bot_user or not bot_user.api_token:
        messages.warning(request, "ابتدا باید توکن ایتایار خود را ثبت کنید.")
        return redirect("broadcast:eitaa_connect_token")

    if request.method == "POST":
        form = EitaaChannelForm(
            request.POST, user=request.user, api_token=bot_user.api_token
        )
        if form.is_valid():
            from django.utils import timezone
            from product.forward.broadcast.models import BroadcastChannel

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

    return render(request, "product/forward/broadcast/eitaa/add_channel.html", {
        "form": form,
        "bot_user": bot_user,
    })


@login_required
def eitaa_delete_channel(request, channel_id):
    """غیرفعال‌سازی کانال ایتا (POST only)."""
    from product.forward.broadcast.models import BroadcastChannel

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
    from core.models import Platform
    from product.forward.broadcast.forms import RubikaPhoneForm
    from product.forward.messengers.adapters.base import MessengerError
    from product.forward.messengers.adapters.rubika import RubikaAdapter
    from product.forward.messengers.models import BotUser

    rubika_platform = Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:job_list")

    existing_bot_user = BotUser.objects.filter(
        user=request.user, platform=rubika_platform
    ).first()

    if request.method == "POST":
        form = RubikaPhoneForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone_number"]
            adapter = RubikaAdapter()
            try:
                otp_res = adapter.send_code(phone_number=phone)
            except MessengerError as exc:
                messages.error(request, f"خطا در ارسال کد تایید روبیکا: {exc}")
            else:
                request.session["rubika_otp_phone"] = phone
                request.session["rubika_otp_hash"] = otp_res["phone_code_hash"]
                request.session["rubika_otp_tmp"] = otp_res["tmp_session"]
                messages.info(request, "کد تایید به حساب روبیکا یا شماره موبایل شما ارسال شد.")
                return redirect("broadcast:rubika_verify_code")
    else:
        form = RubikaPhoneForm()

    return render(request, "product/forward/broadcast/rubika/connect_phone.html", {
        "form": form,
        "existing_bot_user": existing_bot_user,
    })


@login_required
def rubika_verify_code(request):
    """گام دوم اتصال به روبیکا: تایید کد OTP و ذخیره نشست دائمی در BotUser."""
    from django.utils import timezone
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

    rubika_platform = Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:job_list")

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
            except MessengerError as exc:
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

    return render(request, "product/forward/broadcast/rubika/verify_code.html", {
        "form": form,
        "phone": phone,
    })


@login_required
def rubika_channels(request):
    """صفحه لیست و مدیریت کانال‌های متصل‌شده روبیکا."""
    from core.models import Platform
    from product.forward.broadcast.models import BroadcastChannel
    from product.forward.messengers.models import BotUser

    rubika_platform = Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:job_list")

    bot_user = BotUser.objects.filter(
        user=request.user, platform=rubika_platform
    ).first()

    channels = BroadcastChannel.objects.filter(
        user=request.user, platform=rubika_platform
    ).order_by("-created_at")

    return render(request, "product/forward/broadcast/rubika/channels.html", {
        "bot_user": bot_user,
        "channels": channels,
    })


@login_required
def rubika_sync_channels(request):
    """همگام‌سازی خودکار کانال‌هایی که کاربر در روبیکا دسترسی ارسال پیام دارد (POST only)."""
    from django.utils import timezone
    from core.models import Platform
    from product.forward.broadcast.models import BroadcastChannel
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
    except MessengerError as exc:
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
    from django.utils import timezone
    from core.models import Platform
    from product.forward.broadcast.forms import RubikaChannelForm
    from product.forward.broadcast.models import BroadcastChannel
    from product.forward.messengers.adapters.rubika import RubikaAdapter
    from product.forward.messengers.models import BotUser

    rubika_platform = Platform.objects.filter(slug="rubika").first()
    if not rubika_platform:
        messages.error(request, "پلتفرم روبیکا در سیستم ثبت نشده است.")
        return redirect("broadcast:job_list")

    bot_user = BotUser.objects.filter(
        user=request.user, platform=rubika_platform
    ).first()

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

    return render(request, "product/forward/broadcast/rubika/add_channel.html", {
        "form": form,
        "bot_user": bot_user,
    })


@login_required
def rubika_delete_channel(request, channel_id):
    """غیرفعال‌سازی کانال روبیکا (POST only)."""
    from product.forward.broadcast.models import BroadcastChannel

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
