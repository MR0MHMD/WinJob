from datetime import timedelta

import jdatetime
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from windirect.comments.models import Automation, AutomationExecution
from windirect.connections.models import InstagramConnection
from windirect.direct.models import DirectMessageEvent, DirectRule
from windirect.forms.models import ConversationForm
from windirect.showcases.models import Showcase
from windirect.subscriptions.models import UserSubscription


@login_required(login_url="accounts:login")
def dashboard(request):
    """داشبورد مدیریتی وین دایرکت با آمار، نمودار و دسترسی سریع."""
    user = request.user
    now = timezone.now()

    # ==================== تاریخ شمسی ====================
    today = jdatetime.date.today()
    persian_date = today.strftime("%A %d %B %Y")
    weekdays = {
        "Saturday": "شنبه", "Sunday": "یکشنبه", "Monday": "دوشنبه",
        "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
        "Thursday": "پنجشنبه", "Friday": "جمعه",
    }
    months = {
        "Farvardin": "فروردین", "Ordibehesht": "اردیبهشت", "Khordad": "خرداد",
        "Tir": "تیر", "Mordad": "مرداد", "Shahrivar": "شهریور",
        "Mehr": "مهر", "Aban": "آبان", "Azar": "آذر",
        "Dey": "دی", "Bahman": "بهمن", "Esfand": "اسفند",
    }
    for en, fa in weekdays.items():
        persian_date = persian_date.replace(en, fa)
    for en, fa in months.items():
        persian_date = persian_date.replace(en, fa)

    # ==================== اشتراک فعال ====================
    subscription = (
        UserSubscription.objects
        .filter(account__user=user, ends_at__gt=now)
        .select_related("offer", "offer__plan")
        .order_by("-ends_at")
        .first()
    )
    subscription_days_left = 0
    if subscription:
        subscription_days_left = max(
            (subscription.ends_at - now).days, 0
        )

    # ==================== حساب‌های اینستاگرام ====================
    connections = (
        InstagramConnection.objects
        .filter(owner=user)
        .annotate(
            comment_rule_count=Count(
                "automations", filter=Q(automations__is_active=True), distinct=True
            ),
        )
        .order_by("-created_at")
    )
    connections_count = connections.count()

    allowed_pages = (
        subscription.capabilities.get("max_pages", 1) if subscription else 0
    )

    # ==================== قوانین ====================
    comment_rules_count = Automation.objects.filter(
        connection__owner=user, is_active=True
    ).count()
    direct_rules_count = DirectRule.objects.filter(
        connection__owner=user, is_active=True
    ).count()
    total_rules_count = comment_rules_count + direct_rules_count

    # ==================== ابزارها ====================
    showcases_count = Showcase.objects.filter(
        connection__owner=user, is_active=True
    ).count()
    forms_count = ConversationForm.objects.filter(
        connection__owner=user, is_active=True
    ).count()

    # ==================== اجراها ====================
    comment_executions_qs = AutomationExecution.objects.filter(
        automation__connection__owner=user
    )
    direct_executions_qs = DirectMessageEvent.objects.filter(connection__owner=user)

    comment_executions_count = comment_executions_qs.count()
    direct_executions_count = direct_executions_qs.count()
    total_executions_count = comment_executions_count + direct_executions_count

    # ==================== آخرین اجراها (مخلوط کامنت و دایرکت) ====================
    recent_comment_executions = list(
        comment_executions_qs
        .select_related("automation", "automation__connection", "event")
        .order_by("-created_at")[:5]
    )
    recent_direct_events = list(
        direct_executions_qs
        .select_related("rule", "connection")
        .order_by("-created_at")[:5]
    )
    # مخلوط کردن و مرتب‌سازی بر اساس تاریخ
    recent_executions = sorted(
        recent_comment_executions + recent_direct_events,
        key=lambda x: x.created_at,
        reverse=True,
    )[:7]

    # ==================== نمودار فعالیت (فقط روزهای فعال) ====================
    last_30_days = now - timedelta(days=30)

    comment_daily = (
        comment_executions_qs
        .filter(created_at__gte=last_30_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
    )
    direct_daily = (
        direct_executions_qs
        .filter(created_at__gte=last_30_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
    )

    comment_map = {item["day"]: item["total"] for item in comment_daily if item["day"]}
    direct_map = {item["day"]: item["total"] for item in direct_daily if item["day"]}

    # فقط روزهایی که حداقل یه فعالیت دارن
    active_days = sorted(set(comment_map.keys()) | set(direct_map.keys()))

    activity_labels = []
    activity_comment_data = []
    activity_direct_data = []

    for day in active_days:
        jalali = jdatetime.date.fromgregorian(date=day)
        activity_labels.append(jalali.strftime("%m/%d"))
        activity_comment_data.append(comment_map.get(day, 0))
        activity_direct_data.append(direct_map.get(day, 0))

    import json

    # ==================== آخرین حساب‌ها ====================
    top_connections = connections[:5]

    context = {
        "persian_date": persian_date,
        "subscription": subscription,
        "subscription_days_left": subscription_days_left,
        "connections_count": connections_count,
        "allowed_pages": allowed_pages,
        "comment_rules_count": comment_rules_count,
        "direct_rules_count": direct_rules_count,
        "total_rules_count": total_rules_count,
        "showcases_count": showcases_count,
        "forms_count": forms_count,
        "comment_executions_count": comment_executions_count,
        "direct_executions_count": direct_executions_count,
        "total_executions_count": total_executions_count,
        "recent_executions": recent_executions,
        "top_connections": top_connections,
        "activity_labels_json": json.dumps(activity_labels, ensure_ascii=False),
        "activity_comment_data_json": json.dumps(activity_comment_data, ensure_ascii=False),
        "activity_direct_data_json": json.dumps(activity_direct_data, ensure_ascii=False),
        "noindex": True,
    }
    return render(request, "windirect/dashboard.html", context)
