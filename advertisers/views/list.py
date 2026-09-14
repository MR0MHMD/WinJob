from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from content_team.models import ContentOrder
from django.core.paginator import Paginator
from core.models import AdType, Platform
from campaigns.models import Campaign
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q


@login_required
def campaigns_list(request):
    advertiser = request.user.advertiser_profile

    status_filter = request.GET.get("status", "all")
    search_query = request.GET.get("q", "").strip()
    platform_slug = request.GET.get("platform", "")
    ad_type_slug = request.GET.get("ad_type", "")
    free_filter = request.GET.get("free", "")
    sort_by = request.GET.get("sort", "newest")

    campaigns_qs = Campaign.objects.filter(advertiser=advertiser).select_related(
        "platform", "content_type", "ad_type", "content_service_type", "invoice"
    )

    if status_filter != "all":
        campaigns_qs = campaigns_qs.filter(status=status_filter)

    if search_query:
        campaigns_qs = campaigns_qs.filter(name__icontains=search_query)

    if platform_slug:
        campaigns_qs = campaigns_qs.filter(platform__slug=platform_slug)

    if ad_type_slug:
        campaigns_qs = campaigns_qs.filter(ad_type__slug=ad_type_slug)

    if free_filter == "yes":
        campaigns_qs = campaigns_qs.filter(is_free=True)
    elif free_filter == "no":
        campaigns_qs = campaigns_qs.filter(is_free=False)

    if sort_by == "oldest":
        campaigns_qs = campaigns_qs.order_by("created_at")
    else:  # newest
        campaigns_qs = campaigns_qs.order_by("-created_at")

    available_statuses = campaigns_qs.values_list("status", flat=True).distinct()
    filtered_status_choices = [
        (value, label)
        for value, label in Campaign.Status.choices
        if value in available_statuses
    ]

    paginator = Paginator(campaigns_qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    platforms = Platform.objects.filter(is_active=True)
    ad_types = AdType.objects.filter(is_active=True)

    context = {
        "campaigns": page_obj,
        "status_filter": status_filter,
        "statuses": filtered_status_choices,
        "search_query": search_query,
        "platform_slug": platform_slug,
        "ad_type_slug": ad_type_slug,
        "free_filter": free_filter,
        "sort_by": sort_by,
        "platforms": platforms,
        "ad_types": ad_types,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string(
            "advertisers/partials/campaign_cards.html",
            context,
            request=request
        )
        return JsonResponse({"html": html})

    return render(request, "advertisers/pages/campaign_list.html", context)

@login_required
def content_orders_list(request):
    """
    لیست همه سفارش‌های تولید محتوای تبلیغ‌دهنده
    - مستقل (is_standalone=True)
    - کمپینی (campaign__advertiser=user.advertiser_profile)

    URL params:
        - type: all | standalone | campaign (پیش‌فرض: all)
        - status: فیلتر وضعیت
        - search: جستجو در نام کمپین/تیم/پلن/برند
        - sort: مرتب‌سازی (created_at, -created_at, price, -price)
        - page: شماره صفحه
    """

    # ========== بررسی دسترسی ==========
    if not hasattr(request.user, 'advertiser_profile'):
        messages.error(request, 'شما دسترسی به این بخش ندارید.')
        return redirect('core:home')

    advertiser = request.user.advertiser_profile

    # ========== پارامترها ==========
    order_type = request.GET.get('type', 'all')  # all | standalone | campaign
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', '-created_at')

    # اعتبارسنجی sort
    allowed_sorts = ['-created_at', 'created_at', '-price', 'price']
    if sort_by not in allowed_sorts:
        sort_by = '-created_at'

    # ========== کوئری پایه: سفارش‌های خود کاربر ==========
    # مستقل: standalone_user = کاربر
    # کمپینی: campaign.advertiser = advertiser
    orders = ContentOrder.objects.filter(
        Q(standalone_user=request.user, is_standalone=True) |
        Q(campaign__advertiser=advertiser)
    ).select_related(
        'campaign',
        'campaign__advertiser',
        'campaign__advertiser__user',
        'standalone_user',
        'team',
        'plan',
        'plan__service_type',
    ).prefetch_related(
        'files',
        'brief',
        'deliveries__files',
        'revisions',
    ).distinct()

    # ========== فیلتر نوع سفارش ==========
    if order_type == 'standalone':
        orders = orders.filter(is_standalone=True)
    elif order_type == 'campaign':
        orders = orders.filter(campaign__isnull=False)
    # else: all (بدون فیلتر)

    # ========== فیلتر وضعیت ==========
    if status_filter:
        orders = orders.filter(status=status_filter)

    # ========== جستجو ==========
    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) |
            Q(campaign__name__icontains=search_query) |
            Q(team__name__icontains=search_query) |
            Q(plan__name__icontains=search_query) |
            Q(brief__brand_name__icontains=search_query)
        )

    # ========== مرتب‌سازی ==========
    orders = orders.order_by(sort_by)

    # ========== آمار ==========
    # برای آمار، از یه کوئری جداگانه استفاده می‌کنیم که فیلتر نوع رو اعمال نکنه
    base_orders_for_stats = ContentOrder.objects.filter(
        Q(standalone_user=request.user, is_standalone=True) |
        Q(campaign__advertiser=advertiser)
    ).distinct()

    stats = {
        'total': base_orders_for_stats.count(),
        'standalone_count': base_orders_for_stats.filter(is_standalone=True).count(),
        'campaign_count': base_orders_for_stats.filter(campaign__isnull=False).count(),
        'pending': base_orders_for_stats.filter(status='pending').count(),
        'in_progress': base_orders_for_stats.filter(status='in_progress').count(),
        'completed': base_orders_for_stats.filter(status='completed').count(),
    }

    # ========== صفحه‌بندی ==========
    paginator = Paginator(orders, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ========== محاسبه کمیسیون تیم محتوا برای هر سفارش ==========
    # توی تمپلیت نیاز داریم که برای کمپینی‌ها کمیسیون محتوا رو نشون بدیم
    for order in page_obj:
        # تعیین کاربر سفارش‌دهنده
        if order.campaign:
            order.ordering_user = order.campaign.advertiser.user
            order.ordering_user_type = 'campaign'
            order.display_title = order.campaign.name
        elif order.standalone_user:
            order.ordering_user = order.standalone_user
            order.ordering_user_type = 'standalone'
            order.display_title = f'سفارش مستقل #{order.id}'
        else:
            order.ordering_user = None
            order.ordering_user_type = 'unknown'
            order.display_title = f'سفارش #{order.id}'

        # محاسبه کمیسیون محتوا (فقط برای کمپینی)
        order.content_commission = 0
        if order.campaign and hasattr(order.campaign, 'invoice') and order.campaign.invoice:
            invoice = order.campaign.invoice
            if invoice.content_cost:
                order.content_commission = int(invoice.content_cost * 0.15)

    # ========== Context ==========
    context = {
        'page_obj': page_obj,
        'orders': page_obj,
        'stats': stats,
        'order_type': order_type,
        'status_filter': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'status_choices': ContentOrder.Status.choices,
        'total_count': orders.count(),
        'title': 'لیست سفارش‌های تولید محتوا',
    }

    return render(request, 'advertisers/pages/content_orders_list.html', context)