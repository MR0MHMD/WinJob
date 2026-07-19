from content_team.utils import get_last_n_months, get_jalali_month_name
from django.db.models.functions import TruncMonth, TruncDay
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg, Count, Q
from campaigns.models import Campaign, Coupon
from django.shortcuts import redirect, render
from datetime import timedelta, datetime
from accounts.models import Transaction
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import jdatetime
import json
from content_team.models import (
    ContentOrder,
    ContentServiceType,
    ContentServicePlan,
    ContentDelivery,
    ContentOrderRevision,
    TeamReview,
    ContentTeamMember
)


@login_required
def content_team_dashboard(request):
    if not hasattr(request.user, 'team_member'):
        messages.error(request, "شما عضو هیچ تیم تولید محتوایی نیستید.")
        return redirect('core:home')

    current_member = request.user.team_member
    team = current_member.team

    if not current_member.is_active:
        messages.error(request, "حساب کاربری شما در این تیم غیرفعال شده است.")
        return redirect('core:home')

    is_manager = (current_member.role == 'manager')

    # سفارش‌ها
    orders = ContentOrder.objects.filter(team=team, ).exclude(
        campaign__status__in=[Campaign.Status.DRAFT, Campaign.Status.PENDING]
    )

    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    in_progress_orders = orders.filter(status='in_progress').count()
    completed_orders = orders.filter(status='completed').count()
    cancelled_orders = orders.filter(status='cancelled').count()

    total_revenue = orders.filter(status='completed').aggregate(
        total=Sum('price')
    )['total'] or 0

    pending_revenue = orders.filter(
        status__in=['review_pending', 'in_progress', 'done']
    ).aggregate(total=Sum('price'))['total'] or 0

    personal_share_percent = current_member.revenue_share_percent

    if personal_share_percent > 0:
        personal_earned = (total_revenue * personal_share_percent) // 100
    else:
        personal_earned = 0

    avg_rating = team.reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    if avg_rating:
        avg_rating = round(avg_rating, 1)

    total_reviews = team.reviews.count()
    total_members = team.members.filter(is_active=True).count()

    total_percent_sum = team.members.filter(is_active=True).aggregate(
        total=Sum('revenue_share_percent')
    )['total'] or 0

    wallet_balance = request.user.wallet.balance if hasattr(request.user, 'wallet') else 0

    # ========== سفارش‌های اخیر (با select_related اصلاح شده) ==========
    recent_orders = orders.select_related(
        'campaign', 'team', 'plan__service_type'
    ).order_by('-created_at')[:10]

    active_orders = orders.filter(
        status='in_progress'
    ).select_related('campaign', 'plan__service_type').order_by('created_at')[:5]

    pending_approval_orders = []
    if is_manager:
        pending_approval_orders = orders.filter(
            status='pending'
        ).select_related('campaign', 'plan__service_type').order_by('created_at')[:5]

    # ========== سفارشات در حال انجام با ددلاین نزدیک (کمتر از 24 ساعت) ==========
    now = timezone.now()
    orders_near_deadline = []

    for order in active_orders:
        if order.deadline:
            # deadline از نوع jdatetime.datetime است، تبدیل به datetime معمولی برای مقایسه
            deadline_dt = order.deadline.togregorian()
            if timezone.is_naive(deadline_dt):
                deadline_dt = timezone.make_aware(deadline_dt)
            time_left = deadline_dt - now
            if 0 < time_left.total_seconds() < 24 * 3600:
                orders_near_deadline.append(order)

    near_deadline_count = len(orders_near_deadline)

    recent_reviews = team.reviews.select_related(
        'advertiser', 'order'
    ).order_by('-created_at')[:5]

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]

    # کدهای تخفیف اخیر تیم
    latest_coupons = Coupon.objects.filter(
        team=team,
        is_active=True
    ).order_by('-id')[:3]

    team_members = []
    if is_manager:
        team_members = team.members.filter(is_active=True).select_related('user')

    # ========== وضعیت پلن‌های خدمات (برای مدیر) ==========
    service_types_with_plans = []
    service_types_without_plans = []
    services_without_plans = 0
    services_with_plans_count = 0
    total_services = 0

    if is_manager:
        all_service_types = ContentServiceType.objects.filter(is_active=True)

        for st in all_service_types:
            active_plans_count = ContentServicePlan.objects.filter(
                team=team,
                service_type=st,
                is_active=True
            ).count()

            item = {
                'service_type': st,
                'active_plans_count': active_plans_count,
                'max_plans': 3,
                'percentage': (active_plans_count / 3) * 100,
                'has_plans': active_plans_count > 0,
                'is_full': active_plans_count >= 3,
                'empty_slots': 3 - active_plans_count
            }

            if active_plans_count > 0:
                service_types_with_plans.append(item)
            else:
                service_types_without_plans.append(item)

        services_without_plans = len(service_types_without_plans)
        services_with_plans_count = len(service_types_with_plans)
        total_services = len(all_service_types)

    # تاریخ شمسی امروز
    today = jdatetime.date.today()
    persian_date = today.strftime("%A %d %B %Y")

    weekdays = {
        'Saturday': 'شنبه', 'Sunday': 'یکشنبه', 'Monday': 'دوشنبه',
        'Tuesday': 'سه‌شنبه', 'Wednesday': 'چهارشنبه',
        'Thursday': 'پنجشنبه', 'Friday': 'جمعه'
    }
    months = {
        'Farvardin': 'فروردین', 'Ordibehesht': 'اردیبهشت', 'Khordad': 'خرداد',
        'Tir': 'تیر', 'Mordad': 'مرداد', 'Shahrivar': 'شهریور',
        'Mehr': 'مهر', 'Aban': 'آبان', 'Azar': 'آذر',
        'Dey': 'دی', 'Bahman': 'بهمن', 'Esfand': 'اسفند'
    }

    for en, fa in weekdays.items():
        persian_date = persian_date.replace(en, fa)
    for en, fa in months.items():
        persian_date = persian_date.replace(en, fa)

    # ========== محاسبه درصد تکمیل اطلاعات تیم ==========
    team_info_fields = {
        'name': bool(team.name and team.name.strip()),
        'slug': bool(team.slug and team.slug.strip()),
        'logo': bool(team.logo),
        'description': bool(team.description and team.description.strip()),
    }
    completed_fields = sum(team_info_fields.values())
    total_fields = len(team_info_fields)
    completion_percent = int((completed_fields / total_fields) * 100) if total_fields > 0 else 0
    is_team_info_complete = (completion_percent == 100)

    # ========== بررسی وجود پلن فعال برای هر نوع خدمتی ==========
    has_any_active_plan = ContentServicePlan.objects.filter(
        team=team,
        is_active=True
    ).exists()

    # ========== سفارشات در انتظار تایید (برای هشدار) ==========
    # همه سفارشات pending بدون محدودیت
    all_pending_orders = orders.filter(
        status='pending'
    ).select_related('campaign').order_by('created_at')

    pending_orders_count_for_alert = all_pending_orders.count()

    context = {
        'current_member': current_member,
        'team': team,
        'is_manager': is_manager,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'in_progress_orders': in_progress_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'total_revenue': total_revenue,
        'latest_coupons': latest_coupons,
        'pending_revenue': pending_revenue,
        'personal_share_percent': personal_share_percent,
        'personal_earned': personal_earned,
        'total_percent_sum': total_percent_sum,
        'avg_rating': avg_rating,
        'total_reviews': total_reviews,
        'total_members': total_members,
        'wallet_balance': wallet_balance,
        'recent_orders': recent_orders,
        'active_orders': active_orders,
        'pending_approval_orders': pending_approval_orders,
        'recent_reviews': recent_reviews,
        'recent_transactions': recent_transactions,
        'team_members': team_members,
        'service_types_with_plans': service_types_with_plans,
        'service_types_without_plans': service_types_without_plans,
        'services_without_plans': services_without_plans,
        'services_with_plans_count': services_with_plans_count,
        'total_services': total_services,
        'persian_date': persian_date,
        'gamification': team.gamification_status,
        'completion_percent': completion_percent,
        'is_team_info_complete': is_team_info_complete,
        'has_any_active_plan': has_any_active_plan,
        'pending_orders_count_for_alert': pending_orders_count_for_alert,
        'all_pending_orders': all_pending_orders[:5],
        'orders_near_deadline': orders_near_deadline,
        'near_deadline_count': near_deadline_count,
    }

    return render(request, "content_team/pages/dashboard.html", context)


@login_required
def team_performance_report(request):
    # بررسی عضویت در تیم
    if not hasattr(request.user, 'team_member') or not request.user.team_member:
        return redirect('core:home')

    team_member = request.user.team_member
    team = team_member.team
    current_user_nickname = request.user.nickname or request.user.phone_number

    # ----- آمار پایه -----

    orders = ContentOrder.objects.filter(team=team).exclude(
        campaign__status__in=[Campaign.Status.DRAFT, Campaign.Status.PENDING]
    )
    total_orders = orders.count()
    completed_orders = orders.filter(status=ContentOrder.Status.COMPLETED)
    completed_count = completed_orders.count()
    total_revenue = completed_orders.aggregate(total=Sum('price'))['total'] or 0
    avg_rating = team.avg_rating
    in_progress_count = orders.filter(status=ContentOrder.Status.IN_PROGRESS).count()
    pending_count = orders.filter(status=ContentOrder.Status.PENDING).count()
    review_pending_count = orders.filter(status=ContentOrder.Status.REVIEW_PENDING).count()

    # میانگین زمان تحویل
    deliveries = ContentDelivery.objects.filter(
        order__team=team,
        status=ContentDelivery.DeliveryStatus.FINAL_ACCEPTED
    ).select_related('order')
    delivery_times = []
    for delivery in deliveries:
        if delivery.order.created_at and delivery.accepted_at:
            delta = delivery.accepted_at - delivery.order.created_at
            delivery_times.append(delta.days)
    avg_delivery_days = round(sum(delivery_times) / len(delivery_times), 1) if delivery_times else None

    total_revisions = ContentOrderRevision.objects.filter(order__team=team).count()
    pending_revisions = ContentOrderRevision.objects.filter(order__team=team, status='pending').count()

    positive_reviews = TeamReview.objects.filter(team=team, rating__gte=4).count()
    total_reviews = TeamReview.objects.filter(team=team).count()
    satisfaction_rate = round((positive_reviews / total_reviews) * 100) if total_reviews > 0 else 0

    # ----- نمودار روند ماهانه (۶ ماه) -----
    last_months = get_last_n_months(6)
    first_day = last_months[0]
    orders_by_month = (
        ContentOrder.objects.filter(
            team=team,
            status=ContentOrder.Status.COMPLETED,
            created_at__gte=first_day
        )
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'), revenue=Sum('price'))
        .order_by('month')
    )
    data_dict = {}
    for item in orders_by_month:
        if item['month']:
            key = item['month'].date()
            data_dict[key] = {
                'count': item['count'],
                'revenue': int(item['revenue'] or 0)
            }

    month_labels = []
    orders_data = []
    revenue_data = []
    for datet in last_months:
        month_labels.append(get_jalali_month_name(datet))
        key_date = datet.date()
        if key_date in data_dict:
            orders_data.append(data_dict[key_date]['count'])
            revenue_data.append(data_dict[key_date]['revenue'])
        else:
            orders_data.append(0)
            revenue_data.append(0)

    # ----- نمودار روند روزانه (۱۰ روز اخیر) -----
    today = timezone.now().date()
    start_10_days_ago = today - timedelta(days=9)  # ۱۰ روز شامل امروز
    start_datetime = datetime.combine(start_10_days_ago, datetime.min.time(), tzinfo=timezone.get_current_timezone())

    daily_orders = (
        ContentOrder.objects.filter(
            team=team,
            status=ContentOrder.Status.COMPLETED,
            created_at__gte=start_datetime
        )
        .annotate(day=TruncDay('created_at'))
        .values('day')
        .annotate(count=Count('id'), revenue=Sum('price'))
        .order_by('day')
    )

    daily_dict = {}
    for item in daily_orders:
        if item['day']:
            day_date = item['day'].date()
            daily_dict[day_date] = {
                'count': item['count'],
                'revenue': int(item['revenue'] or 0)
            }

    daily_labels = []
    daily_orders_count = []
    daily_revenue = []
    for i in range(10):
        current_day = start_10_days_ago + timedelta(days=i)
        jd = jdatetime.date.fromgregorian(date=current_day)
        # فرمت روز/ماه با دو رقم (مثلاً ۳۱/۰۲)
        label = f"{jd.month:02d}/{jd.day:02d}"
        daily_labels.append(label)
        if current_day in daily_dict:
            daily_orders_count.append(daily_dict[current_day]['count'])
            daily_revenue.append(daily_dict[current_day]['revenue'])
        else:
            daily_orders_count.append(0)
            daily_revenue.append(0)

    # ----- تفکیک خدمات -----
    service_breakdown = (
        ContentOrder.objects.filter(team=team, status=ContentOrder.Status.COMPLETED)
        .values('plan__service_type__name')
        .annotate(count=Count('id'), total_price=Sum('price'))
        .order_by('-count')
    )
    service_labels = [item['plan__service_type__name'] or 'متفرقه' for item in service_breakdown]
    service_counts = [item['count'] for item in service_breakdown]
    service_revenues = [int(item['total_price'] or 0) for item in service_breakdown]

    members_income = (
        Transaction.objects.filter(
            type=Transaction.Type.TEAM_PAYMENT,
            team_member__team=team,
            status=Transaction.Status.SUCCESS
        )
        .values('team_member__user__nickname', 'team_member__role', 'team_member__user__avatar')
        .annotate(total_income=Sum('amount'))
        .order_by('-total_income')
    )
    members_income_list = []
    current_user_income = 0
    for m in members_income:
        nickname = m['team_member__user__nickname'] or 'نامشخص'
        income = int(m['total_income'] or 0)
        avatar_path = m['team_member__user__avatar']
        if avatar_path:
            full_avatar_url = settings.MEDIA_URL + avatar_path
        else:
            full_avatar_url = None
        members_income_list.append({
            'nickname': nickname,
            'role': dict(ContentTeamMember.Role.choices).get(m['team_member__role'], m['team_member__role']),
            'total_income': income,
            'avatar': full_avatar_url,
        })
        if nickname == current_user_nickname:
            current_user_income = income

    # ----- آمار ماه جاری -----
    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_orders = orders.filter(created_at__gte=current_month_start)
    current_month_count = current_month_orders.count()
    current_month_revenue = \
    current_month_orders.filter(status=ContentOrder.Status.COMPLETED).aggregate(total=Sum('price'))['total'] or 0
    current_month_completed = current_month_orders.filter(status=ContentOrder.Status.COMPLETED).count()

    # آماده‌سازی JSON برای نمودارها
    chart_data = {
        'months': month_labels,
        'orders_count': orders_data,
        'revenue': revenue_data,
        'service_labels': service_labels,
        'service_counts': service_counts,
        'service_revenues': service_revenues,
        'daily_labels': daily_labels,
        'daily_orders': daily_orders_count,
        'daily_revenue': daily_revenue,
    }

    print(current_month_count)

    context = {
        'team': team,
        'team_member': team_member,
        'current_user_nickname': current_user_nickname,
        'current_user_income': current_user_income,
        'total_orders': total_orders,
        'completed_count': completed_count,
        'total_revenue': total_revenue,
        'avg_rating': avg_rating,
        'in_progress_count': in_progress_count,
        'pending_count': pending_count,
        'review_pending_count': review_pending_count,
        'avg_delivery_days': avg_delivery_days,
        'total_revisions': total_revisions,
        'pending_revisions': pending_revisions,
        'satisfaction_rate': satisfaction_rate,
        'members_income': members_income_list,
        'current_month_count': current_month_count,
        'current_month_revenue': current_month_revenue,
        'current_month_completed': current_month_completed,
        'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
    }
    return render(request, 'content_team/pages/performance_report.html', context)


@login_required
def plans_dashboard(request):
    """صفحه داشبورد مدیریت پلن‌ها - نمایش لیست خدمات به صورت کارتی"""
    if not hasattr(request.user, 'team_member'):
        messages.error(request, 'شما عضو هیچ تیمی نیستید.')
        return redirect('dashboard')

    team_member = request.user.team_member
    if not team_member.is_manager():
        messages.error(request, 'شما دسترسی مدیریت پلن‌ها را ندارید.')
        return redirect('team:dashboard')

    team = team_member.team

    service_types = ContentServiceType.objects.filter(
        is_active=True
    ).annotate(
        plans_count=Count(
            'plans',
            filter=Q(plans__team=team, plans__is_active=True)
        )
    ).order_by('display_order', 'name')

    for service in service_types:
        service.active_plans = ContentServicePlan.objects.filter(
            team=team,
            service_type=service,
            is_active=True
        )[:3]

    total_services = service_types.count()
    services_with_plans = service_types.filter(plans_count__gt=0).count()
    services_without_plans = service_types.filter(plans_count=0).count()
    total_plans = sum(service.plans_count for service in service_types)

    context = {
        'team': team,
        'service_types': service_types,
        'max_plans_per_service': 3,
        'total_services': total_services,
        'services_with_plans': services_with_plans,
        'services_without_plans': services_without_plans,
        'total_plans': total_plans,
    }

    return render(request, 'content_team/plans/plans_dashboard.html', context)
