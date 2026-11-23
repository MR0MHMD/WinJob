"""ویوهای پنل وب وین فوروارد (همراه با ارسال لوگوهای پلتفرم از دیتابیس و داده‌های تحلیلی داشبورد)."""

from datetime import timedelta
from zoneinfo import ZoneInfo
from django.core.paginator import Paginator
from django.urls import reverse
import json
import jdatetime

_PERSIAN_WEEKDAYS = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه")


def _to_gregorian_dt(dt_val, tz):
    """تبدیل ایمن datetime یا jdatetime.datetime (از django_jalali) به datetime میلادی با timezone تهران."""
    if dt_val is None:
        return None
    if isinstance(dt_val, jdatetime.datetime):
        dt_val = dt_val.togregorian()
    elif isinstance(dt_val, jdatetime.date) and not hasattr(dt_val, "hour"):
        g = dt_val.togregorian()
        from datetime import datetime as _dt
        dt_val = _dt(g.year, g.month, g.day)
    if timezone.is_naive(dt_val):
        dt_val = timezone.make_aware(dt_val, tz)
    return dt_val.astimezone(tz)


def _jalali_label(g_date, weekday_only: bool = False) -> str:
    """تبدیل ایمن تاریخ به برچسب شمسی (MM/DD) یا نام روز هفته فارسی."""
    jd = g_date if isinstance(g_date, jdatetime.date) else jdatetime.date.fromgregorian(date=g_date)
    if weekday_only:
        return _PERSIAN_WEEKDAYS[jd.weekday()]
    return jd.strftime("%m/%d")


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from product.forward.broadcast.forms import BroadcastSendForm
from product.forward.broadcast.models import BroadcastChannel, BroadcastJob, BroadcastTarget, ChannelPreset, \
    BroadcastHub
from product.forward.broadcast.services.dispatcher import dispatch_job, enqueue_dispatch_job

TOKEN_TOMAN_RATE = 50


def _get_token_balance_safe(user) -> int:
    """دریافت ایمن موجودی توکن کاربر."""
    from product.forward.subscriptions.access import get_user_token_balance
    return get_user_token_balance(user)


def _get_jobs_token_spend_map(user, job_ids: list) -> dict:
    """محاسبه تجمیعی توکن مصرف‌شده هر عملیات ارسال در یک کوئری واحد."""
    if not job_ids:
        return {}
    from product.forward.subscriptions.models import ForwardTokenTransaction

    rows = (
        ForwardTokenTransaction.objects.filter(
            user=user,
            tx_type=ForwardTokenTransaction.TxType.SPEND,
            broadcast_job_id__in=job_ids,
        )
        .values("broadcast_job_id")
        .annotate(total=Sum("amount"))
    )
    return {r["broadcast_job_id"]: abs(int(r["total"] or 0)) for r in rows}


def _get_pricing_json() -> str:
    """سریال‌سازی جدول نرخ مصرف توکن برای محاسبه‌گر زنده در استدیو ارسال."""
    from product.forward.subscriptions.services import get_pricing_config
    cfg = get_pricing_config()
    return json.dumps(
        {
            "text": cfg.text_cost,
            "photo": cfg.photo_cost,
            "caption_extra": cfg.caption_extra_cost,
            "sticker_gif": cfg.sticker_gif_cost,
            "under_5": cfg.media_under_5mb_cost,
            "from_5_10": cfg.media_5_to_10mb_cost,
            "from_10_20": cfg.media_10_to_20mb_cost,
            "max_mb": cfg.max_file_size_mb,
            "hub_extra": cfg.hub_extra_cost,
            "ai_extra": cfg.ai_watermark_extra_cost,
        },
        ensure_ascii=False,
    )


def _get_forward_platforms_map() -> dict:
    """واکشی دیکشنری پلتفرم‌های وین‌فوروارد از دیتابیس (شامل فیلد logo) بر اساس اسلاگ."""
    from core.models import Platform

    qs = Platform.objects.filter(slug__in=["bale", "eitaa", "rubika", "telegram", "soroush"])
    return {p.slug: p for p in qs}


def _format_persian_date() -> str:
    """تولید رشته تاریخ شمسی خوانا مشابه داشبورد وین‌دایرکت و تبلیغ‌دهندگان."""
    now_tehran = timezone.now().astimezone(ZoneInfo("Asia/Tehran"))
    today = jdatetime.date.fromgregorian(date=now_tehran.date())
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


def _render_job_report(request, job: BroadcastJob, is_public_view: bool = False):
    """ساخت کانتکست مشترک گزارش تحلیلی ارسال همگانی برای نمای مالک و نمای عمومی بدون لاگین."""
    nav_platforms = _get_forward_platforms_map()
    targets = list(job.targets.select_related("channel", "channel__platform").all())
    total_targets = job.total_targets or len(targets)
    success_rate = int(round((job.success_count / total_targets) * 100)) if total_targets > 0 else 0
    pending_count = max(0, total_targets - (job.success_count + job.failed_count))

    plat_order = ["bale", "eitaa", "rubika", "telegram", "soroush"]
    plat_stats = {}
    for t in targets:
        slug = t.channel.platform.slug
        if slug not in plat_stats:
            plat_stats[slug] = {"name": t.channel.platform.name, "success": 0, "failed": 0, "pending": 0}
        if t.status == BroadcastTarget.Status.SUCCESS:
            plat_stats[slug]["success"] += 1
        elif t.status in (BroadcastTarget.Status.FAILED, BroadcastTarget.Status.SKIPPED):
            plat_stats[slug]["failed"] += 1
        else:
            plat_stats[slug]["pending"] += 1

    ordered_slugs = [s for s in plat_order if s in plat_stats] + [s for s in plat_stats if s not in plat_order]
    platform_chart = {
        "labels": [plat_stats[s]["name"] for s in ordered_slugs],
        "success": [plat_stats[s]["success"] for s in ordered_slugs],
        "failed": [plat_stats[s]["failed"] for s in ordered_slugs],
    }

    from product.forward.subscriptions.services import calculate_delivery_token_cost

    job_tokens_spent = _get_jobs_token_spend_map(job.message.user, [job.pk]).get(job.pk, 0)
    job_tokens_toman = job_tokens_spent * TOKEN_TOMAN_RATE
    unit_token_cost = (
        int(round(job_tokens_spent / job.success_count))
        if (job.success_count > 0 and job_tokens_spent > 0)
        else 0
    )
    from product.forward.subscriptions.models import ForwardTokenTransaction

    meta = job.message.platform_file_ids or {}
    is_hub_msg = bool(meta.get("hub_id"))
    has_msg_text = bool((job.message.text or "").strip())
    file_size_bytes = int(meta.get("file_size") or 0)
    if job.message.file:
        try:
            file_size_bytes = int(job.message.file.size or file_size_bytes)
        except Exception:
            pass

    # خواندن تراکنش‌های واقعی دفترکل برای این جاب جهت تطابق ۱۰۰٪ هر کانال (از جمله +۲ توکن امضای AI)
    job_tx_rows = list(
        ForwardTokenTransaction.objects.filter(
            user=job.message.user,
            tx_type=ForwardTokenTransaction.TxType.SPEND,
            broadcast_job_id=job.pk,
        ).values("amount", "description")
    )
    used_tx_indices = set()
    for t in targets:
        if t.status != BroadcastTarget.Status.SUCCESS:
            t.tokens_spent = 0
            t.tokens_toman = 0
            continue

        matched_cost = None
        ch_needle = f"«{t.channel.title}»"
        for idx, tx in enumerate(job_tx_rows):
            if idx in used_tx_indices:
                continue
            if ch_needle in (tx.get("description") or ""):
                matched_cost = abs(int(tx["amount"]))
                used_tx_indices.add(idx)
                break

        if matched_cost is None:
            ch_ai = (
                    (getattr(t.channel, "watermark_mode", "off") or "off") != "off"
                    and has_msg_text
                    and job.message.content_type != "sticker"
            )
            if t.channel.platform.slug == "soroush":
                matched_cost = calculate_delivery_token_cost(
                    content_type="text",
                    has_caption=False,
                    file_size_bytes=0,
                    is_hub=is_hub_msg,
                    use_ai_watermark=ch_ai,
                )
            else:
                matched_cost = calculate_delivery_token_cost(
                    content_type=job.message.content_type,
                    has_caption=has_msg_text,
                    file_size_bytes=file_size_bytes,
                    is_hub=is_hub_msg,
                    use_ai_watermark=ch_ai,
                )

        t.tokens_spent = matched_cost
        t.tokens_toman = matched_cost * TOKEN_TOMAN_RATE

    return render(
        request,
        "product/forward/broadcast/job_detail.html",
        {
            "job": job,
            "targets": targets,
            "total_targets": total_targets,
            "success_rate": success_rate,
            "pending_count": pending_count,
            "job_tokens_spent": job_tokens_spent,
            "job_tokens_toman": job_tokens_toman,
            "unit_token_cost": unit_token_cost,
            "token_toman_rate": TOKEN_TOMAN_RATE,
            "platform_chart_json": json.dumps(platform_chart, ensure_ascii=False),
            "nav_platforms": nav_platforms,
            "is_public_view": is_public_view,
            "public_report_url": job.get_public_report_url(),
        },
    )


@login_required
def job_detail(request, job_id):
    """نمایش گزارش تحلیلی ارسال همگانی برای کاربر لاگین‌شده مالک ارسال."""
    job = get_object_or_404(BroadcastJob.objects.select_related("message", "message__user"), pk=job_id,
                            message__user=request.user)
    return _render_job_report(request, job, is_public_view=False)


def public_job_detail(request, slug):
    """نمایش عمومی گزارش ارسال از طریق اسلاگ تصادفی ۱۵ کاراکتری بدون نیاز به لاگین."""
    job = get_object_or_404(BroadcastJob.objects.select_related("message", "message__user"), public_slug=slug)
    is_owner = request.user.is_authenticated and (request.user.pk == job.message.user_id)
    return _render_job_report(request, job, is_public_view=not is_owner)


@method_decorator(login_required, name="dispatch")
class JobListView(ListView):
    """نمایش تاریخچه ارسال‌ها با فیلترهای پیشرفته، نمای جدولی (پیش‌فرض) و کارتی، و نرخ موفقیت هر ارسال."""

    model = BroadcastJob
    template_name = "product/forward/broadcast/job_list.html"
    context_object_name = "jobs"
    paginate_by = 12

    def get_queryset(self):
        qs = (
            BroadcastJob.objects.filter(message__user=self.request.user)
            .select_related("message")
            .prefetch_related("targets__channel__platform")
            .order_by("-created_at")
        )
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "all").strip().lower()
        ctype = (self.request.GET.get("content_type") or "all").strip().lower()
        plat = (self.request.GET.get("platform") or "all").strip().lower()

        if q:
            if q.isdigit():
                qs = qs.filter(Q(pk=int(q)) | Q(message__text__icontains=q))
            else:
                qs = qs.filter(message__text__icontains=q)
        if status in ("done", "partial", "failed", "running", "pending"):
            qs = qs.filter(status=status)
        if ctype in ("text", "photo", "video", "audio", "voice", "document", "animation", "sticker"):
            qs = qs.filter(message__content_type=ctype)
        if plat in ("bale", "eitaa", "rubika", "telegram", "soroush"):
            qs = qs.filter(targets__channel__platform__slug=plat).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_platforms"] = _get_forward_platforms_map()
        qs_all = BroadcastJob.objects.filter(message__user=self.request.user)
        agg = qs_all.aggregate(total_sent=Sum("success_count"), total_failed=Sum("failed_count"))
        total_sent = agg["total_sent"] or 0
        total_failed = agg["total_failed"] or 0
        total_all = total_sent + total_failed

        ctx["total_jobs_count"] = qs_all.count()
        ctx["total_sent_count"] = total_sent
        ctx["total_failed_count"] = total_failed
        ctx["overall_success_rate"] = int(round((total_sent / total_all) * 100)) if total_all > 0 else 100

        view_mode = (self.request.GET.get("view") or "table").strip().lower()
        ctx["view_mode"] = view_mode if view_mode in ("table", "grid") else "table"
        ctx["search_q"] = (self.request.GET.get("q") or "").strip()
        ctx["status_filter"] = (self.request.GET.get("status") or "all").strip().lower()
        ctx["content_type_filter"] = (self.request.GET.get("content_type") or "all").strip().lower()
        ctx["platform_filter"] = (self.request.GET.get("platform") or "all").strip().lower()

        # محاسبه نرخ موفقیت، لیست یکتای پلتفرم‌ها و توکن مصرفی برای هر جاب در صفحه فعلی
        page_jobs = list(ctx["jobs"])
        spend_map = _get_jobs_token_spend_map(self.request.user, [j.pk for j in page_jobs])
        for job in page_jobs:
            seen_p = {}
            for t in job.targets.all():
                p = t.channel.platform
                if p.slug not in seen_p:
                    seen_p[p.slug] = p
            job.unique_platforms = list(seen_p.values())
            job.tokens_spent = spend_map.get(job.pk, 0)
            job.tokens_toman = job.tokens_spent * TOKEN_TOMAN_RATE
        ctx["jobs"] = page_jobs
        return ctx


# ============================================================
# Eitaa Web Panel Views
# ============================================================


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


# ============================================================
# Rubika Web Panel Views
# ============================================================


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


# ============================================================
# Channel Preset Views (پروفایل‌های ارسال کانال)
# ============================================================


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
        "product/forward/broadcast/presets.html",
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
        "product/forward/broadcast/preset_edit.html",
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


# ============================================================
# Telegram Web Panel Views
# ============================================================


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


# ============================================================
# Broadcast Hub Views (مدیریت هاب‌های ارسال گروهی در پنل وب)
# ============================================================


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
        "product/forward/broadcast/hubs.html",
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
        "product/forward/broadcast/hub_edit.html",
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


# ============================================================
# Unified Connected Channels Page (صفحه یکپارچه کانال‌های متصل)
# ============================================================


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
        "product/forward/broadcast/channels.html",
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


# ============================================================
# Soroush+ Web Panel Views
# ============================================================


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
        "product/forward/broadcast/channel_detail.html",
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
