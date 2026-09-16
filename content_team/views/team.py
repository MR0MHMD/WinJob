from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from core.models import ContentServiceType
from django.utils import timezone
from itertools import groupby
from django.db import models
import logging
from django.db.models import (
    F, ExpressionWrapper, fields,
    Q, Prefetch, Avg, Count,
    OuterRef, Subquery,
    Case, When, Value
)
from content_team.models import (
    ContentTeam,
    TeamReview,
    ContentTeamMember,
    ContentOrder,
    ContentServicePlan, ContentPortfolio
)

logger = logging.getLogger(__name__)


def team_list_view(request):
    """
    ویو لیست تیم‌های تولید محتوا
    """
    search_query = request.GET.get('search', '')
    service_type_filter = request.GET.getlist('service_type')
    ordering = request.GET.get('ordering', '-annotated_avg_rating')

    allowed_ordering = [
        '-annotated_avg_rating', 'annotated_avg_rating',
        '-annotated_review_count', 'annotated_review_count',
        '-annotated_completed_orders', 'annotated_completed_orders',
        '-created_at', 'created_at',
        'name', '-name'
    ]
    if ordering not in allowed_ordering:
        ordering = '-annotated_avg_rating'

    teams = ContentTeam.objects.filter(is_active=True)

    if search_query:
        teams = teams.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if service_type_filter:
        for slug in service_type_filter:
            teams = teams.filter(
                service_plans__service_type__slug=slug,
                service_plans__is_active=True
            )

    teams = teams.prefetch_related(
        'service_plans__service_type',
        Prefetch('reviews', queryset=TeamReview.objects.order_by('-created_at')),
        Prefetch('members', queryset=ContentTeamMember.objects.filter(is_active=True))
    ).annotate(
        annotated_avg_rating=Avg('reviews__rating'),
        annotated_review_count=Count('reviews'),
        annotated_completed_orders=Count('orders', filter=Q(orders__status='completed')),
        annotated_active_members_count=Count('members', filter=Q(members__is_active=True))
    ).order_by(ordering)

    paginator = Paginator(teams, 21)
    page = request.GET.get('page', 1)

    try:
        teams_page = paginator.page(page)
    except PageNotAnInteger:
        teams_page = paginator.page(1)
    except EmptyPage:
        teams_page = paginator.page(paginator.num_pages)

    context = {
        'teams': teams_page,
        'search_query': search_query,
        'selected_service_types': service_type_filter,
        'current_ordering': ordering,
        'service_types': ContentServiceType.objects.filter(is_active=True),
        'selected_service_type': service_type_filter[0] if len(service_type_filter) == 1 else '',
        'total_teams': teams.count(),
        'is_paginated': teams_page.has_other_pages(),
        'page_obj': teams_page,
        'paginator': paginator,
    }

    return render(request, 'content_team/pages/team_list.html', context)


def team_detail_view(request, slug, id):
    """
    ویو جزئیات تیم تولید محتوا
    با پشتیبانی از بازگشت به سفارش مستقل و کمپین
    """
    team = get_object_or_404(
        ContentTeam.objects.filter(is_active=True).prefetch_related(
            'members',
            'service_plans__service_type',
            Prefetch(
                'reviews',
                queryset=TeamReview.objects.select_related(
                    'advertiser__user', 'order'
                ).order_by('-created_at')
            ),
            Prefetch(
                'orders',
                queryset=ContentOrder.objects.select_related(
                    'campaign__advertiser__user'
                ).prefetch_related(
                    'revisions',
                    'deliveries'
                ).order_by('-created_at')
            )
        ).annotate(
            annotated_avg_rating=Avg('reviews__rating'),
            annotated_review_count=Count('reviews'),
            annotated_completed_orders=Count('orders', filter=Q(orders__status='completed')),
            annotated_active_members_count=Count('members', filter=Q(members__is_active=True))
        ),
        slug=slug, id=id
    )

    # ========== تولید QR Code در صورت عدم وجود ==========
    if not team.qr_code:
        try:
            team.generate_qr(force=False)
            team.refresh_from_db()
        except Exception as e:
            logger.error(f"QR Code generation failed for team {team.id}: {e}")

    # ========== اعضای تیم بر اساس نقش ==========
    managers = team.members.filter(is_active=True, role='manager')
    editors = team.members.filter(is_active=True, role='editor')
    writers = team.members.filter(is_active=True, role='writer')
    designers = team.members.filter(is_active=True, role='designer')
    videographers = team.members.filter(is_active=True, role='videographer')
    other_members = team.members.filter(is_active=True, role='other')

    member_roles = [
        {'id': 'managers', 'title': 'مدیران', 'icon': 'fi-star-filled', 'members': managers},
        {'id': 'editors', 'title': 'ادیتورها', 'icon': 'fi-edit', 'members': editors},
        {'id': 'writers', 'title': 'نویسندگان', 'icon': 'fi-pencil', 'members': writers},
        {'id': 'designers', 'title': 'طراحان', 'icon': 'fi-image', 'members': designers},
        {'id': 'videographers', 'title': 'فیلم‌برداران', 'icon': 'fi-video', 'members': videographers},
        {'id': 'other', 'title': 'سایر اعضا', 'icon': 'fi-layers', 'members': other_members},
    ]

    # ========== دریافت پلن‌های فعال ==========
    active_plans = team.service_plans.filter(
        is_active=True
    ).select_related('service_type').order_by('service_type__name', 'price')

    # ========== محاسبه محبوب‌ترین پلن برای هر سرویس ==========
    most_popular_subquery = ContentServicePlan.objects.filter(
        team=team,
        service_type=OuterRef('service_type'),
        is_active=True
    ).annotate(
        completed_count=Count(
            'orders',
            filter=Q(orders__status__in=[ContentOrder.Status.COMPLETED, ContentOrder.Status.DONE])
        )
    ).filter(
        completed_count__gt=0
    ).order_by('-completed_count').values('id')[:1]

    active_plans = active_plans.annotate(
        is_most_popular=Case(
            When(
                id=Subquery(most_popular_subquery),
                then=Value(True)
            ),
            default=Value(False),
            output_field=models.BooleanField()
        )
    )

    # ========== ساختاردهی پلن‌ها بر اساس نوع سرویس ==========
    service_plans_by_type = []
    for service_type, plans in groupby(active_plans, key=lambda p: p.service_type):
        plan_list = list(plans)
        service_plans_by_type.append({
            'service_type': service_type,
            'plans': plan_list,
        })

    # ================================================================
    # ========== محاسبات کارت حرفه‌ای‌گری ==========
    # ================================================================

    now = timezone.now()
    team_age_days = (now - team.created_at).days

    total_orders = team.orders.count()
    completed_orders = team.orders.filter(status='completed').count()
    success_rate = int((completed_orders / total_orders * 100)) if total_orders > 0 else 0

    avg_revisions = team.orders.annotate(
        rev_count=Count('revisions')
    ).aggregate(avg=Avg('rev_count'))['avg']
    avg_revisions = round(avg_revisions, 1) if avg_revisions else 0

    completed_orders_with_delivery = team.orders.filter(
        status='completed',
        deliveries__isnull=False
    ).distinct()

    avg_delivery_days = 0
    if completed_orders_with_delivery.exists():
        avg_delivery_days_result = completed_orders_with_delivery.annotate(
            delivery_days=ExpressionWrapper(
                F('deliveries__delivered_at') - F('created_at'),
                output_field=fields.DurationField()
            )
        ).aggregate(avg=Avg('delivery_days'))['avg']

        if avg_delivery_days_result:
            avg_delivery_days = int(avg_delivery_days_result.total_seconds() / 86400)

    # ========== آمار تیم ==========
    stats = {
        'avg_rating': team.annotated_avg_rating,
        'review_count': team.annotated_review_count,
        'completed_orders': team.annotated_completed_orders,
        'active_members': team.annotated_active_members_count,
        'revenue_share_valid': team.is_revenue_share_valid(),
        'total_revenue_percent': team.get_total_revenue_percent(),
        'team_age_days': team_age_days,
        'success_rate': success_rate,
        'avg_revisions': avg_revisions,
        'avg_delivery_days': avg_delivery_days,
    }

    # ========== نظرات ==========
    reviews = team.reviews.all()[:3]
    recent_completed_orders = team.orders.filter(status='completed')[:5]

    # ================================================================
    # ========== 🆕 پشتیبانی از بازگشت به سفارش مستقل ==========
    # ================================================================

    # پارامترهای بازگشت
    return_to = request.GET.get('return_to')
    service_type_id = request.GET.get('service_type_id')
    source = request.GET.get('source', '')
    from_campaign = request.GET.get('from') == 'create_campaign'
    page = request.GET.get('page', '1')
    select_plan_id = request.GET.get('select_plan_id')  # برای بازگشت به کمپین با پلن انتخاب شده

    # متغیرهای پیش‌فرض
    back_url = None
    select_team_url = None
    from_standalone = False
    is_from_campaign = False

    # ====== ۱. حالت بازگشت به سفارش مستقل ======
    if return_to == 'standalone_order' and service_type_id:
        from_standalone = True
        back_url = reverse('content_team:standalone_order_step1')
        # 🔥 صفحه رو هم به URL اضافه کن
        select_team_url = f"{back_url}?selected_service={service_type_id}&selected_team={team.id}&return_to=team_detail&page={page}"

    # ====== ۲. حالت بازگشت به کمپین (استپ ۳) ======
    elif from_campaign or source == 'campaign':
        is_from_campaign = True
        campaign_id = request.session.get('campaign_draft_id')
        if campaign_id:
            back_url = reverse('campaigns:campaign_create_step3_team')
            # اگر پلن هم انتخاب شده باشه، اونم برگردون
            if select_plan_id:
                select_team_url = f"{back_url}?selected_team={team.id}&selected_plan={select_plan_id}&page={page}"
            else:
                select_team_url = f"{back_url}?selected_team={team.id}&page={page}"
        else:
            back_url = reverse('campaigns:campaign_create_step1')
            select_team_url = None

    # ====== ۳. حالت عادی (لیست تیم‌ها) ======
    else:
        back_url = reverse('content_team:team_list')
        select_team_url = None

    # ========== بررسی امکان ثبت نظر ==========
    can_submit_review = False
    pending_orders = []

    if request.user.is_authenticated and hasattr(request.user, 'advertiser_profile'):
        advertiser = request.user.advertiser_profile
        pending_orders = list(ContentOrder.objects.filter(
            campaign__advertiser=advertiser,
            team=team,
            status=ContentOrder.Status.COMPLETED,
            review__isnull=True
        ).select_related('campaign').order_by('-created_at'))

        has_any_review = TeamReview.objects.filter(team=team, advertiser=advertiser).exists()

        if not has_any_review:
            can_submit_review = True
        elif pending_orders:
            can_submit_review = True

    # ========== مرتب‌سازی نظرات ==========
    all_reviews = list(team.reviews.all())
    if request.user.is_authenticated and hasattr(request.user, 'advertiser_profile'):
        user_reviews = [r for r in all_reviews if r.advertiser.user == request.user]
        other_reviews = [r for r in all_reviews if r.advertiser.user != request.user]
        sorted_reviews = user_reviews + sorted(other_reviews, key=lambda x: x.created_at, reverse=True)
    else:
        sorted_reviews = sorted(all_reviews, key=lambda x: x.created_at, reverse=True)

    # ========== کانتکست نهایی ==========
    context = {
        'team': team,
        'managers': managers,
        'editors': editors,
        'writers': writers,
        'designers': designers,
        'member_roles': member_roles,
        'videographers': videographers,
        'other_members': other_members,
        'service_plans_by_type': service_plans_by_type,
        'stats': stats,
        'reviews': reviews,
        'recent_completed_orders': recent_completed_orders,
        'from_campaign': is_from_campaign,
        'from_standalone': from_standalone,
        'team_id': team.id,
        'return_page': page,
        'gamification': team.gamification_status,
        'can_submit_review': can_submit_review,
        'pending_orders': pending_orders,
        'sorted_reviews': sorted_reviews,
        # ====== 🔥 اضافه شده برای بازگشت ======
        'page': page,
        'back_url': back_url,
        'select_team_url': select_team_url,
        'service_type_id': service_type_id,
        'return_to': return_to,
        'select_plan_id': select_plan_id,
    }

    return render(request, 'content_team/pages/team_detail.html', context)


def plan_detail(request, plan_id):
    """
    نمایش جزئیات یک پلن
    با پشتیبانی از بازگشت به سفارش مستقل و کمپین
    """
    plan = get_object_or_404(
        ContentServicePlan.objects.select_related('team', 'service_type'),
        id=plan_id,
        is_active=True,
    )
    team = plan.team

    # ================================================================
    # ========== 🆕 پشتیبانی از بازگشت به سفارش مستقل ==========
    # ================================================================

    return_to = request.GET.get('return_to')
    service_type_id = request.GET.get('service_type_id')
    team_id = request.GET.get('team_id')
    source = request.GET.get('source', '')

    from_campaign = request.GET.get('from') == 'create_campaign'
    page = request.GET.get('page', '1')

    back_url = None
    select_plan_url = None
    from_standalone = False
    is_from_campaign = False

    # ====== ۱. حالت بازگشت به سفارش مستقل ======
    if return_to == 'standalone_order' and service_type_id and team_id:
        from_standalone = True
        back_url = reverse('content_team:standalone_order_step1')
        select_plan_url = (
            f"{back_url}?selected_service={service_type_id}"
            f"&selected_team={team_id}&selected_plan={plan.id}"
            f"&return_to=plan_detail&page={page}"
        )

    # ====== ۲. حالت بازگشت به کمپین (استپ ۳) ======
    elif from_campaign or source == 'campaign':
        is_from_campaign = True
        campaign_id = request.session.get('campaign_draft_id')
        if campaign_id:
            back_url = reverse('campaigns:campaign_create_step3_team')
            select_plan_url = (
                f"{back_url}?selected_plan={plan.id}"
                f"&selected_team={team.id}&page={page}"
            )
        else:
            back_url = reverse('campaigns:campaign_create_step1')

    # ====== ۳. حالت عادی (لیست تیم‌ها) ======
    else:
        back_url = reverse('content_team:team_list')

    # ================================================================
    # ========== آمار و اطلاعات پلن ==========
    # ================================================================

    # ---------- شمارش سفارش‌های موفق + میانگین امتیاز (یک کوئری) ----------
    order_stats = ContentOrder.objects.filter(
        plan=plan,
        status=ContentOrder.Status.COMPLETED,
    ).aggregate(
        completed_count=Count('id'),
        avg_rating=Avg('review__rating'),
    )

    completed_orders_count = order_stats['completed_count'] or 0
    avg_rating = order_stats['avg_rating']
    if avg_rating:
        avg_rating = round(avg_rating, 1)

    # ---------- نظرات (۵ تای آخر) ----------
    reviews_qs = TeamReview.objects.filter(
        order__plan=plan,
        order__status=ContentOrder.Status.COMPLETED,
    ).select_related(
        'advertiser__user', 'order'
    ).order_by('-created_at')

    reviews = reviews_qs[:5]
    reviews_count = reviews_qs.count()

    # ---------- 🆕 نمونه کارها (۵ تای آخر این پلن) ----------
    portfolio_items = ContentPortfolio.objects.filter(
        plan=plan,
    ).only(
        'id', 'file', 'created_at'  # فقط فیلدهای لازم
    ).order_by('-created_at')[:5]

    # ---------- اعضای تیم ----------
    members = team.members.filter(is_active=True).only(
        'id', 'user', 'role', 'revenue_share_percent'
    ).select_related('user')

    # ---------- محبوب‌ترین پلن ----------
    most_popular = ContentServicePlan.objects.filter(
        team=team,
        service_type=plan.service_type,
        is_active=True,
    ).annotate(
        completed_count=Count(
            'orders',
            filter=Q(orders__status=ContentOrder.Status.COMPLETED),
        )
    ).filter(
        completed_count__gt=0
    ).order_by('-completed_count').only('id').first()

    is_most_popular = (most_popular and most_popular.id == plan.id)

    context = {
        'plan': plan,
        'team': team,
        'completed_orders_count': completed_orders_count,
        'avg_rating': avg_rating,
        'reviews': reviews,
        'reviews_count': reviews_count,
        'portfolio_items': portfolio_items,  # ✅ ۵ تای آخر
        'members': members,
        'from_campaign': is_from_campaign,
        'from_standalone': from_standalone,
        'page': page,
        'is_most_popular': is_most_popular,
        'back_url': back_url,
        'select_plan_url': select_plan_url,
        'service_type_id': service_type_id,
        'team_id': team_id,
        'return_to': return_to,
    }
    return render(request, 'content_team/pages/plan_detail.html', context)
