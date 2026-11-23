"""ویوهای مانیتورینگ و مدیریت مالی اختصاصی وین‌فوروارد در پنل Support (فقط مدیرعامل و توسعه‌دهنده · Read-Only)."""

from __future__ import annotations

import json
from datetime import timedelta
from zoneinfo import ZoneInfo

import jdatetime
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from product.forward.broadcast.models import BroadcastChannel, BroadcastHub, BroadcastJob, BroadcastMessage, ChannelPreset
from product.forward.broadcast.views.helpers import _jalali_label, _to_gregorian_dt
from product.forward.constants import TOKEN_TOMAN_RATE
from product.forward.subscriptions.models import (
    ForwardSubscriptionAccount,
    ForwardSubscriptionOrder,
    ForwardTokenTransaction,
)
from ..mixins import TopManagerRequiredMixin


def _get_jalali_today_str() -> tuple[str, str]:
    weekdays = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه")
    today_j = jdatetime.date.today()
    return weekdays[today_j.weekday()], today_j.strftime("%Y/%m/%d")


# ============================================================
# ۱. داشبورد مانیتورینگ وین‌فوروارد
# ============================================================


class ForwardSupportDashboardView(TopManagerRequiredMixin, TemplateView):
    """داشبورد جامع مانیتورینگ عملیاتی وین‌فوروارد (فقط CEO و Developer)."""

    template_name = "support/forward/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tehran_tz = ZoneInfo("Asia/Tehran")
        now_local = timezone.now().astimezone(tehran_tz)
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_14d = now_local - timedelta(days=14)

        weekday_fa, jalali_date = _get_jalali_today_str()
        ctx["jalali_weekday"] = weekday_fa
        ctx["jalali_date"] = jalali_date

        # آمار کلی کاربران، کانال‌ها، پکیج‌ها و هاب‌ها
        ctx["total_forward_users"] = ForwardSubscriptionAccount.objects.count()
        channels_qs = BroadcastChannel.objects.filter(is_active=True)
        ctx["total_channels"] = channels_qs.count()
        ctx["ai_enabled_channels"] = channels_qs.exclude(watermark_mode=BroadcastChannel.WatermarkMode.OFF).count()
        ctx["total_presets"] = ChannelPreset.objects.filter(is_active=True).count()
        ctx["total_hubs"] = BroadcastHub.objects.filter(is_active=True).count()

        # تفکیک کانال‌ها بر اساس پلتفرم
        plat_rows = list(
            channels_qs.values("platform__name", "platform__slug")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")
        )
        ctx["platform_breakdown"] = plat_rows

        # آمار ارسال‌ها (کل و امروز)
        jobs_qs = BroadcastJob.objects.all()
        job_agg = jobs_qs.aggregate(
            total_jobs=Count("id"),
            total_success=Sum("success_count"),
            total_failed=Sum("failed_count"),
        )
        total_success = int(job_agg["total_success"] or 0)
        total_failed = int(job_agg["total_failed"] or 0)
        total_all = total_success + total_failed
        ctx["total_jobs"] = int(job_agg["total_jobs"] or 0)
        ctx["total_success"] = total_success
        ctx["total_failed"] = total_failed
        ctx["overall_success_rate"] = int(round((total_success / total_all) * 100)) if total_all > 0 else 100

        today_jobs = jobs_qs.filter(created_at__gte=today_start).aggregate(
            cnt=Count("id"),
            succ=Sum("success_count"),
            fail=Sum("failed_count"),
        )
        ctx["today_jobs_count"] = int(today_jobs["cnt"] or 0)
        ctx["today_success_count"] = int(today_jobs["succ"] or 0)
        ctx["today_failed_count"] = int(today_jobs["fail"] or 0)

        # آمار توکن و فروش
        acc_agg = ForwardSubscriptionAccount.objects.aggregate(
            total_balance=Sum("token_balance"),
            total_spent=Sum("total_tokens_spent"),
            total_earned=Sum("total_tokens_earned"),
        )
        ctx["total_tokens_balance"] = int(acc_agg["total_balance"] or 0)
        ctx["total_tokens_spent"] = int(acc_agg["total_spent"] or 0)
        ctx["total_tokens_spent_toman"] = ctx["total_tokens_spent"] * TOKEN_TOMAN_RATE

        paid_orders_agg = ForwardSubscriptionOrder.objects.filter(
            status=ForwardSubscriptionOrder.Status.PAID
        ).aggregate(cnt=Count("id"), rev=Sum("total_amount"))
        ctx["paid_orders_count"] = int(paid_orders_agg["cnt"] or 0)
        ctx["total_revenue"] = int(paid_orders_agg["rev"] or 0)

        # نمودار روند ۱۴ روز اخیر (شمسی دقیق)
        recent_jobs_14 = list(
            jobs_qs.filter(created_at__gte=cutoff_14d).values("created_at", "success_count", "failed_count")
        )
        buckets = {}
        today_g = now_local.date()
        for i in range(13, -1, -1):
            d = today_g - timedelta(days=i)
            buckets[d] = {"label": _jalali_label(d), "success": 0, "failed": 0}
        for r in recent_jobs_14:
            ldt = _to_gregorian_dt(r["created_at"], tehran_tz)
            if ldt and ldt.date() in buckets:
                buckets[ldt.date()]["success"] += int(r["success_count"] or 0)
                buckets[ldt.date()]["failed"] += int(r["failed_count"] or 0)
        ordered_days = sorted(buckets.keys())
        ctx["trend_chart_json"] = json.dumps(
            {
                "labels": [buckets[d]["label"] for d in ordered_days],
                "success": [buckets[d]["success"] for d in ordered_days],
                "failed": [buckets[d]["failed"] for d in ordered_days],
            },
            ensure_ascii=False,
        )

        # آخرین جاب‌های ناموفق / نیمه‌موفق برای رصد سریع مشکلات
        ctx["problem_jobs"] = list(
            BroadcastJob.objects.filter(status__in=[BroadcastJob.Status.FAILED, BroadcastJob.Status.PARTIAL])
            .select_related("message", "message__user")
            .order_by("-created_at")[:10]
        )

        # کاربران پرمصرف وین‌فوروارد
        ctx["top_spenders"] = list(
            ForwardSubscriptionAccount.objects.select_related("user")
            .filter(total_tokens_spent__gt=0)
            .order_by("-total_tokens_spent")[:10]
        )
        return ctx


# ============================================================
# ۲. داشبورد مدیریت مالی اختصاصی وین‌فوروارد
# ============================================================


class ForwardFinanceDashboardView(TopManagerRequiredMixin, TemplateView):
    """داشبورد مالی اختصاصی وین‌فوروارد: فروش بسته‌های توکن، هدایا، مصرف توکن و سفارش‌ها."""

    template_name = "support/forward/finance.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tehran_tz = ZoneInfo("Asia/Tehran")
        now_local = timezone.now().astimezone(tehran_tz)
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_30d = now_local - timedelta(days=30)

        weekday_fa, jalali_date = _get_jalali_today_str()
        ctx["jalali_weekday"] = weekday_fa
        ctx["jalali_date"] = jalali_date

        orders_qs = ForwardSubscriptionOrder.objects.select_related("user", "plan").order_by("-created_at")
        paid_qs = orders_qs.filter(status=ForwardSubscriptionOrder.Status.PAID)

        total_agg = paid_qs.aggregate(
            revenue=Sum("total_amount"),
            subtotal=Sum("subtotal_amount"),
            vat=Sum("vat_amount"),
            tokens=Sum("tokens_amount"),
            cnt=Count("id"),
        )
        today_agg = paid_qs.filter(paid_at__gte=today_start).aggregate(revenue=Sum("total_amount"), cnt=Count("id"))
        month_agg = paid_qs.filter(paid_at__gte=cutoff_30d).aggregate(revenue=Sum("total_amount"), cnt=Count("id"))

        ctx["total_revenue"] = int(total_agg["revenue"] or 0)
        ctx["total_subtotal"] = int(total_agg["subtotal"] or 0)
        ctx["total_vat"] = int(total_agg["vat"] or 0)
        ctx["total_tokens_sold"] = int(total_agg["tokens"] or 0)
        ctx["paid_orders_count"] = int(total_agg["cnt"] or 0)
        ctx["pending_orders_count"] = orders_qs.filter(status=ForwardSubscriptionOrder.Status.PENDING).count()
        ctx["today_revenue"] = int(today_agg["revenue"] or 0)
        ctx["today_orders_count"] = int(today_agg["cnt"] or 0)
        ctx["month_revenue"] = int(month_agg["revenue"] or 0)
        ctx["month_orders_count"] = int(month_agg["cnt"] or 0)

        # آمار کلی دفترکل توکن (هدیه، خرید، مصرف، موجودی کل در گردش)
        acc_agg = ForwardSubscriptionAccount.objects.aggregate(
            total_balance=Sum("token_balance"),
            total_spent=Sum("total_tokens_spent"),
        )
        ctx["circulating_tokens"] = int(acc_agg["total_balance"] or 0)
        ctx["total_tokens_spent"] = int(acc_agg["total_spent"] or 0)
        ctx["total_gift_tokens"] = int(
            ForwardTokenTransaction.objects.filter(tx_type=ForwardTokenTransaction.TxType.GIFT)
            .aggregate(s=Sum("amount"))["s"] or 0
        )

        # فروش به تفکیک بسته
        ctx["plan_breakdown"] = list(
            paid_qs.values("plan__name", "plan__tokens_amount")
            .annotate(orders=Count("id"), rev=Sum("total_amount"))
            .order_by("-rev")
        )

        # نمودار درآمد ۱۴ روز اخیر
        buckets = {}
        today_g = now_local.date()
        for i in range(13, -1, -1):
            d = today_g - timedelta(days=i)
            buckets[d] = {"label": _jalali_label(d), "revenue": 0}
        for row in paid_qs.filter(paid_at__gte=now_local - timedelta(days=14)).values("paid_at", "total_amount"):
            ldt = _to_gregorian_dt(row["paid_at"], tehran_tz)
            if ldt and ldt.date() in buckets:
                buckets[ldt.date()]["revenue"] += int(row["total_amount"] or 0)
        odays = sorted(buckets.keys())
        ctx["revenue_chart_json"] = json.dumps(
            {
                "labels": [buckets[d]["label"] for d in odays],
                "revenue": [buckets[d]["revenue"] for d in odays],
            },
            ensure_ascii=False,
        )

        ctx["recent_orders"] = list(orders_qs[:25])
        return ctx


# ============================================================
# ۳. لیست‌های مانیتورینگ (ارسال‌ها، کانال‌ها، کیف توکن و تراکنش‌ها)
# ============================================================


class ForwardJobListView(TopManagerRequiredMixin, ListView):
    """مانیتورینگ تمام ارسال‌های وین‌فوروارد با فیلتر وضعیت، پلتفرم و جستجو."""

    model = BroadcastJob
    template_name = "support/forward/jobs.html"
    context_object_name = "jobs"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            BroadcastJob.objects.select_related("message", "message__user")
            .prefetch_related("targets__channel__platform")
            .order_by("-created_at")
        )
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        ctype = (self.request.GET.get("content_type") or "").strip()
        plat = (self.request.GET.get("platform") or "").strip()
        if q:
            if q.isdigit():
                qs = qs.filter(Q(pk=int(q)) | Q(message__user__phone_number__icontains=q) | Q(message__text__icontains=q))
            else:
                qs = qs.filter(
                    Q(message__text__icontains=q)
                    | Q(message__user__phone_number__icontains=q)
                    | Q(message__user__nickname__icontains=q)
                )
        if status:
            qs = qs.filter(status=status)
        if ctype:
            qs = qs.filter(message__content_type=ctype)
        if plat:
            qs = qs.filter(targets__channel__platform__slug=plat).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["status_filter"] = (self.request.GET.get("status") or "").strip()
        ctx["ctype_filter"] = (self.request.GET.get("content_type") or "").strip()
        ctx["plat_filter"] = (self.request.GET.get("platform") or "").strip()
        ctx["status_choices"] = BroadcastJob.Status.choices
        ctx["ctype_choices"] = BroadcastMessage.ContentType.choices
        return ctx


class ForwardChannelListView(TopManagerRequiredMixin, ListView):
    """مانیتورینگ تمام کانال‌های متصل‌شده در وین‌فوروارد (به همراه وضعیت امضای AI)."""

    model = BroadcastChannel
    template_name = "support/forward/channels.html"
    context_object_name = "channels"
    paginate_by = 25

    def get_queryset(self):
        qs = BroadcastChannel.objects.select_related("user", "platform").order_by("-created_at")
        q = (self.request.GET.get("q") or "").strip()
        plat = (self.request.GET.get("platform") or "").strip()
        wm = (self.request.GET.get("watermark_mode") or "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(username__icontains=q)
                | Q(chat_id__icontains=q)
                | Q(user__phone_number__icontains=q)
                | Q(user__nickname__icontains=q)
            )
        if plat:
            qs = qs.filter(platform__slug=plat)
        if wm:
            qs = qs.filter(watermark_mode=wm)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["plat_filter"] = (self.request.GET.get("platform") or "").strip()
        ctx["wm_filter"] = (self.request.GET.get("watermark_mode") or "").strip()
        ctx["wm_choices"] = BroadcastChannel.WatermarkMode.choices
        return ctx


class ForwardTokenLedgerView(TopManagerRequiredMixin, ListView):
    """مانیتورینگ دفترکل تراکنش‌های توکن کاربران وین‌فوروارد."""

    model = ForwardTokenTransaction
    template_name = "support/forward/tokens.html"
    context_object_name = "transactions"
    paginate_by = 30

    def get_queryset(self):
        qs = ForwardTokenTransaction.objects.select_related("user").order_by("-created_at")
        q = (self.request.GET.get("q") or "").strip()
        tx_type = (self.request.GET.get("tx_type") or "").strip()
        if q:
            qs = qs.filter(
                Q(user__phone_number__icontains=q)
                | Q(user__nickname__icontains=q)
                | Q(description__icontains=q)
            )
        if tx_type:
            qs = qs.filter(tx_type=tx_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["tx_type_filter"] = (self.request.GET.get("tx_type") or "").strip()
        ctx["tx_choices"] = ForwardTokenTransaction.TxType.choices
        return ctx
