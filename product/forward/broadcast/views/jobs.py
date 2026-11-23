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
        "product/forward/broadcast/jobs/detail.html",
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
    template_name = "product/forward/broadcast/jobs/list.html"
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

