from django.shortcuts import render, get_object_or_404, redirect
from django.db.models.functions import TruncMonth, TruncDate
from django.contrib.auth.decorators import login_required
from accounts.models import Transaction, CustomUser
from django.db.models import Q, Count, Avg, Prefetch
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from core.utils import convert_to_jalali
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import *
import jdatetime
import json
from .models import (
    ContentTeam,
    ContentServiceType,
    ContentServiceRate,
    TeamReview,
    ContentTeamMember,
    ContentOrder,
)


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
                service_rates__service_type__slug=slug,
                service_rates__is_available=True
            )

    # Prefetch بدون اسلایس
    teams = teams.prefetch_related(
        'service_rates__service_type',
        'portfolio_items',
        Prefetch('reviews', queryset=TeamReview.objects.order_by('-created_at')),  # اسلایس رو برداشتم
        Prefetch('members', queryset=ContentTeamMember.objects.filter(is_active=True))
    ).annotate(
        annotated_avg_rating=Avg('reviews__rating'),
        annotated_review_count=Count('reviews'),
        annotated_completed_orders=Count('orders', filter=Q(orders__status='completed')),
        annotated_active_members_count=Count('members', filter=Q(members__is_active=True))
    ).order_by(ordering)

    paginator = Paginator(teams, 12)
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


def team_detail_view(request, slug):
    """
    ویو جزئیات تیم تولید محتوا
    """
    team = get_object_or_404(
        ContentTeam.objects.filter(is_active=True).prefetch_related(
            'members',
            'service_rates__service_type',
            'portfolio_items',
            Prefetch(
                'reviews',
                queryset=TeamReview.objects.select_related(
                    'advertiser__user', 'order'
                ).order_by('-created_at')  # اسلایس رو برداشتم
            ),
            Prefetch(
                'orders',
                queryset=ContentOrder.objects.select_related(
                    'campaign__advertiser__user'
                ).order_by('-created_at')  # اسلایس رو برداشتم
            )
        ).annotate(
            annotated_avg_rating=Avg('reviews__rating'),
            annotated_review_count=Count('reviews'),
            annotated_completed_orders=Count('orders', filter=Q(orders__status='completed')),
            annotated_active_members_count=Count('members', filter=Q(members__is_active=True))
        ),
        slug=slug
    )

    managers = team.members.filter(is_active=True, role='manager')
    editors = team.members.filter(is_active=True, role='editor')
    writers = team.members.filter(is_active=True, role='writer')
    designers = team.members.filter(is_active=True, role='designer')
    videographers = team.members.filter(is_active=True, role='videographer')
    other_members = team.members.filter(is_active=True, role='other')

    # ساختار نقش‌ها برای حلقه در تمپلیت
    member_roles = [
        {
            'id': 'managers',
            'title': 'مدیران',
            'icon': 'fi-star-filled',
            'members': managers,
        },
        {
            'id': 'editors',
            'title': 'ادیتورها',
            'icon': 'fi-edit',
            'members': editors,
        },
        {
            'id': 'writers',
            'title': 'نویسندگان',
            'icon': 'fi-pencil',
            'members': writers,
        },
        {
            'id': 'designers',
            'title': 'طراحان',
            'icon': 'fi-image',
            'members': designers,
        },
        {
            'id': 'videographers',
            'title': 'فیلم‌برداران',
            'icon': 'fi-video',
            'members': videographers,
        },
        {
            'id': 'other',
            'title': 'سایر اعضا',
            'icon': 'fi-layers',
            'members': other_members,
        },
    ]

    available_services = team.service_rates.filter(
        is_available=True
    ).select_related('service_type')

    portfolio_items = team.portfolio_items.filter(
        is_active=True
    ).order_by('display_order', '-created_at')[:3]

    stats = {
        'avg_rating': team.annotated_avg_rating,
        'review_count': team.annotated_review_count,
        'completed_orders': team.annotated_completed_orders,
        'active_members': team.annotated_active_members_count,
        'revenue_share_valid': team.is_revenue_share_valid(),
        'total_revenue_percent': team.get_total_revenue_percent(),
    }

    reviews = team.reviews.all()[:3]
    recent_completed_orders = team.orders.filter(status='completed')[:5]

    context = {
        'team': team,
        'managers': managers,
        'editors': editors,
        'writers': writers,
        'designers': designers,
        'member_roles': member_roles,
        'videographers': videographers,
        'other_members': other_members,
        'available_services': available_services,
        'portfolio_items': portfolio_items,
        'stats': stats,
        'reviews': reviews,
        'recent_completed_orders': recent_completed_orders,
    }

    return render(request, 'content_team/pages/team_detail.html', context)


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

    orders = ContentOrder.objects.filter(team=team)

    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    in_progress_orders = orders.filter(status='in_progress').count()
    completed_orders = orders.filter(status='completed').count()
    cancelled_orders = orders.filter(status='cancelled').count()

    total_revenue = orders.filter(status='completed').aggregate(
        total=Sum('price')
    )['total'] or 0

    pending_revenue = orders.filter(
        status__in=['pending', 'in_progress']
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

    # ========== نمودار درآمد ماهانه (6 ماه اخیر) ==========
    six_months_ago = timezone.now() - timedelta(days=180)

    monthly_revenue = orders.filter(
        status='completed',
        created_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('price')
    ).order_by('month')

    monthly_labels = []
    monthly_data = []

    for item in monthly_revenue:
        if item['month']:
            jalali_date = convert_to_jalali(item['month'])
            if jalali_date:
                monthly_labels.append(jalali_date.strftime('%B'))  # فقط اسم ماه مثل "فروردین"
                monthly_data.append(float(item['total']) if item['total'] else 0)

    # ========== نمودار تعداد سفارشات روزانه (30 روز اخیر) - مثل ویو موفق ==========
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    daily_orders = orders.filter(
        created_at__gte=last_30_days
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')

    daily_orders_labels = []
    daily_orders_data = []

    for item in daily_orders:
        if item['day']:
            jalali_date = convert_to_jalali(item['day'])
            if jalali_date:
                # فقط روز/ماه مثل "15/01" - همین ساده و تمیز
                daily_orders_labels.append(jalali_date.strftime('%d/%m'))
            else:
                daily_orders_labels.append(item['day'].strftime('%d/%m'))
            daily_orders_data.append(item['count'])

    # ========== بقیه کدها ==========
    recent_orders = orders.select_related(
        'campaign', 'team', 'service_rate'
    ).order_by('-created_at')[:10]

    active_orders = orders.filter(
        status='in_progress'
    ).select_related('campaign', 'service_rate').order_by('created_at')[:5]

    pending_approval_orders = []
    if is_manager:
        pending_approval_orders = orders.filter(
            status='pending'
        ).select_related('campaign', 'service_rate').order_by('created_at')[:5]

    recent_reviews = team.reviews.select_related(
        'advertiser', 'order'
    ).order_by('-created_at')[:5]

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]

    team_members = []
    if is_manager:
        team_members = team.members.filter(is_active=True).select_related('user')

    service_rates = []
    if is_manager:
        service_rates = ContentServiceRate.objects.filter(
            team=team,
            is_available=True
        ).select_related('service_type')

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
        'pending_revenue': pending_revenue,
        'personal_share_percent': personal_share_percent,
        'personal_earned': personal_earned,
        'total_percent_sum': total_percent_sum,
        'avg_rating': avg_rating,
        'total_reviews': total_reviews,
        'total_members': total_members,
        'wallet_balance': wallet_balance,
        'monthly_labels_json': json.dumps(monthly_labels, ensure_ascii=False),
        'monthly_data_json': json.dumps(monthly_data, ensure_ascii=False),
        'monthly_orders_labels_json': json.dumps(daily_orders_labels, ensure_ascii=False),
        'monthly_orders_data_json': json.dumps(daily_orders_data, ensure_ascii=False),
        'recent_orders': recent_orders,
        'active_orders': active_orders,
        'pending_approval_orders': pending_approval_orders,
        'recent_reviews': recent_reviews,
        'recent_transactions': recent_transactions,
        'team_members': team_members,
        'service_rates': service_rates,
        'persian_date': persian_date,
    }

    return render(request, "content_team/pages/dashboard.html", context)


@login_required
def team_members_manage(request, team_slug):
    """
    مدیریت اعضای تیم توسط مدیر تیم
    """
    new_user = None
    team = get_object_or_404(ContentTeam, slug=team_slug)

    pending_requests = TeamJoinRequest.objects.filter(team=team, status=TeamJoinRequest.Status.PENDING)
    pending_requests_count = pending_requests.count()

    try:
        current_member = ContentTeamMember.objects.get(team=team, user=request.user)
        if current_member.role != ContentTeamMember.Role.MANAGER:
            messages.error(request, 'شما دسترسی مدیریت این تیم را ندارید.')
            return redirect('home')
    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو این تیم نیستید.')
        return redirect('home')

    if request.method == 'POST' and 'add_member' in request.POST:
        user_id = request.POST.get('user_id')
        role = request.POST.get('role')
        revenue_share_percent = request.POST.get('revenue_share_percent')

        errors = []
        if not user_id:
            errors.append('کاربر را انتخاب کنید')
        if not role:
            errors.append('نقش را انتخاب کنید')
        if not revenue_share_percent:
            errors.append('درصد سهم را وارد کنید')

        if not errors:
            try:
                revenue_share_percent = int(revenue_share_percent)
                if revenue_share_percent < 0 or revenue_share_percent > 100:
                    errors.append('درصد سهم باید بین 0 تا 100 باشد')
            except ValueError:
                errors.append('درصد سهم معتبر نیست')

        if not errors:
            try:
                new_user = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                errors.append('کاربر مورد نظر یافت نشد')

        if not errors:
            if ContentTeamMember.objects.filter(team=team, user=new_user).exists():
                errors.append('این کاربر قبلاً عضو تیم است')

        if not errors:
            current_total = team.members.filter(is_active=True).aggregate(
                total=Sum('revenue_share_percent')
            )['total'] or 0

            if current_total + revenue_share_percent > 100:
                errors.append(
                    f'مجموع درصد سهام اعضای فعال از 100 بیشتر میشود. (فعلاً {current_total}% + {revenue_share_percent}% = {current_total + revenue_share_percent}%)')

        if not errors:
            ContentTeamMember.objects.create(
                team=team,
                user=new_user,
                role=role,
                revenue_share_percent=revenue_share_percent,
                is_active=True
            )
            messages.success(request, f'عضو {new_user.nickname} با موفقیت به تیم اضافه شد.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)
        else:
            for error in errors:
                messages.error(request, error)

    if request.method == 'POST' and 'edit_member' in request.POST:
        member_id = request.POST.get('member_id')
        role = request.POST.get('role')
        revenue_share_percent = request.POST.get('revenue_share_percent')

        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

        errors = []
        if not role:
            errors.append('نقش را انتخاب کنید')

        try:
            revenue_share_percent = int(revenue_share_percent)
            if revenue_share_percent < 0 or revenue_share_percent > 100:
                errors.append('درصد سهم باید بین 0 تا 100 باشد')
        except ValueError:
            errors.append('درصد سهم معتبر نیست')

        if not errors:
            other_members_total = team.members.filter(is_active=True).exclude(id=member.id).aggregate(
                total=Sum('revenue_share_percent')
            )['total'] or 0

            if other_members_total + revenue_share_percent > 100:
                errors.append(
                    f'مجموع درصد سهام از 100 بیشتر میشود. (سایر اعضا {other_members_total}% + این عضو {revenue_share_percent}% = {other_members_total + revenue_share_percent}%)')

        if not errors:
            member.role = role
            member.revenue_share_percent = revenue_share_percent
            member.save()
            messages.success(request, f'اطلاعات {member.user.nickname} با موفقیت ویرایش شد.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)
        else:
            for error in errors:
                messages.error(request, error)

    if request.method == 'POST' and 'expel_member' in request.POST:
        member_id = request.POST.get('member_id')
        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

        if member.user == request.user:
            messages.error(request, 'شما نمی‌توانید خودتان را از تیم اخراج کنید.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)

        user_nickname = member.user.nickname
        member.delete()
        messages.success(request, f'{user_nickname} از تیم اخراج شد.')
        return redirect('content_team:team_members_manage', team_slug=team.slug)

    if request.method == 'POST' and 'deactivate_member' in request.POST:
        member_id = request.POST.get('member_id')
        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

        if member.user == request.user:
            messages.error(request, 'شما نمی‌توانید خودتان را غیرفعال کنید.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)

        member.is_active = False
        member.save()
        messages.success(request, f'{member.user.nickname} غیرفعال شد.')
        return redirect('content_team:team_members_manage', team_slug=team.slug)

    if request.method == 'POST' and 'activate_member' in request.POST:
        member_id = request.POST.get('member_id')
        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

        current_total = team.members.filter(is_active=True).aggregate(
            total=Sum('revenue_share_percent')
        )['total'] or 0

        if current_total + member.revenue_share_percent > 100:
            messages.error(request,
                           f'با فعال کردن {member.user.nickname}، مجموع درصد سهام از 100 بیشتر میشود. (فعلاً {current_total}% + {member.revenue_share_percent}% = {current_total + member.revenue_share_percent}%)')
            return redirect('content_team:team_members_manage', team_slug=team.slug)

        member.is_active = True
        member.save()
        messages.success(request, f'{member.user.nickname} دوباره فعال شد.')
        return redirect('content_team:team_members_manage', team_slug=team.slug)

    members = team.members.all()
    active_members = members.filter(is_active=True)
    inactive_members = members.filter(is_active=False)

    total_percent = active_members.aggregate(total=Sum('revenue_share_percent'))['total'] or 0
    is_valid = total_percent == 100

    existing_member_ids = members.values_list('user_id', flat=True)
    available_users = CustomUser.objects.exclude(id__in=existing_member_ids).filter(is_active=True)

    context = {
        'team': team,
        'pending_requests': pending_requests,
        'pending_requests_count': pending_requests_count,
        'members': members,
        'active_members': active_members,
        'inactive_members': inactive_members,
        'total_percent': total_percent,
        'is_valid': is_valid,
        'available_users': available_users,
        'role_choices': ContentTeamMember.Role.choices,
        'current_member': current_member,
    }

    return render(request, 'content_team/forms/team_members.html', context)


@login_required
def team_orders_list(request):
    """
    ویو لیست سفارشات تیم تولید محتوا با فیلترهای پیشرفته
    """

    # بررسی عضویت کاربر در تیم
    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        user_team = team_member.team
    except ContentTeamMember.DoesNotExist:
        messages.warning(request, 'شما عضو هیچ تیم تولید محتوایی نیستید!')
        return render(request, 'content_team/pages/team_order_list.html', {
            'is_team_member': False,
        })

    # دریافت پارامترهای فیلتر از GET
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-created_at')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')

    # کوئری اصلی با بهینه‌سازی
    orders = ContentOrder.objects.filter(
        team=user_team
    ).select_related(
        'campaign',
        'campaign__advertiser',
        'campaign__advertiser__user',
        'service_rate',
        'service_rate__service_type',
        'delivery',
    ).prefetch_related(
        'brief',
        'files',
        'revisions',
    ).annotate(
        files_count=Count('files'),
        revisions_count=Count('revisions')
    ).order_by(sort_by)

    # اعمال فیلترها
    if status_filter:
        orders = orders.filter(status=status_filter)

    if search_query:
        orders = orders.filter(
            Q(campaign__name__icontains=search_query) |
            Q(campaign__advertiser__user__nickname__icontains=search_query) |
            Q(campaign__advertiser__business_name__icontains=search_query) |
            Q(brief__brand_name__icontains=search_query)
        )

    if price_min:
        orders = orders.filter(price__gte=int(price_min))
    if price_max:
        orders = orders.filter(price__lte=int(price_max))

    # آمارهای پیشرفته
    stats = {
        'total': orders.count(),
        'pending': orders.filter(status='pending').count(),
        'in_progress': orders.filter(status='in_progress').count(),
        'completed': orders.filter(status='completed').count(),
        'cancelled': orders.filter(status='cancelled').count(),
        'total_revenue': orders.filter(status='completed').aggregate(total=Sum('price'))['total'] or 0,
        'avg_rating': user_team.avg_rating or 0,
        'completed_count': user_team.completed_orders_count,
    }

    # صفحه‌بندی
    paginator = Paginator(orders, 12)  # 12 تا در هر صفحه برای نمایش بهتر
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # وضعیت‌ها برای فیلتر
    status_choices = ContentOrder.Status.choices

    context = {
        'orders': page_obj,
        'stats': stats,
        'current_status': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'price_min': price_min,
        'price_max': price_max,
        'status_choices': status_choices,
        'user_team': user_team,
        'team_member': team_member,
        'is_team_member': True,
        'page_obj': page_obj,
    }

    return render(request, 'content_team/pages/team_order_list.html', context)


@login_required
def team_order_detail(request, order_id):
    """نمایش جزئیات سفارش"""

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        user_team = team_member.team
    except ContentTeamMember.DoesNotExist:
        messages.warning(request, 'شما عضو هیچ تیم تولید محتوایی نیستید!')
        return redirect('content_team:team_orders_list')

    order = get_object_or_404(
        ContentOrder.objects.select_related(
            'campaign',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'team',
            'service_rate',
            'service_rate__service_type',
            'delivery',
        ).prefetch_related(
            'brief',
            'files',
            'revisions',
        ),
        id=order_id,
        team=user_team
    )

    revisions = order.revisions.all().order_by('-created_at')

    context = {
        'order': order,
        'team_member': team_member,
        'revisions': revisions,
        'user_team': user_team,
        'brief': getattr(order, 'brief', None),
        'delivery': getattr(order, 'delivery', None),
        'attached_files': order.files.all(),
    }

    return render(request, 'content_team/pages/team_order_detail.html', context)


@login_required
def accept_order(request, order_id):
    """
    قبول سفارش توسط تیم
    وضعیت سفارش از pending به in_progress تغییر می‌کند
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)

        if order.status != 'pending':
            return JsonResponse({'error': 'این سفارش قابل قبول نیست'}, status=400)

        order.status = 'in_progress'
        order.save()

        return JsonResponse({
            'success': True,
            'status': 'in_progress',
            'message': 'سفارش با موفقیت قبول شد'
        })

    except ContentTeamMember.DoesNotExist:
        return JsonResponse({'error': 'شما عضو تیم نیستید'}, status=403)
    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)


@login_required
def reject_order(request, order_id):
    """
    رد سفارش توسط تیم
    وضعیت سفارش از pending به cancelled تغییر می‌کند
    با جریمه امتیازی
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)

        if order.status != 'pending':
            return JsonResponse({'error': 'این سفارش قابل رد نیست'}, status=400)


        order.status = 'cancelled'
        order.save()

        return JsonResponse({
            'success': True,
            'status': 'cancelled',
            'message': 'سفارش با موفقیت رد شد',
            'penalty': True,
            'penalty_points': 10
        })

    except ContentTeamMember.DoesNotExist:
        return JsonResponse({'error': 'شما عضو تیم نیستید'}, status=403)
    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)


@login_required
def deliver_order(request, order_id):
    """
    تحویل سفارش توسط تیم - هر تحویل فقط یک فایل
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)

        if order.status != 'in_progress':
            return JsonResponse({'error': 'این سفارش قابل تحویل نیست'}, status=400)

        notes = request.POST.get('notes', '')
        file = request.FILES.get('delivery_file')  # فقط یک فایل

        if not file:
            return JsonResponse({'error': 'لطفاً یک فایل برای تحویل انتخاب کنید'}, status=400)

        existing_delivery = ContentDelivery.objects.filter(order=order).first()

        if existing_delivery:
            new_version = existing_delivery.version + 1
            existing_delivery.delete()
        else:
            new_version = 1

        delivery = ContentDelivery.objects.create(
            order=order,
            status='delivered',
            delivered_by=team_member,
            delivered_at=timezone.now(),
            notes=notes,
            version=new_version,
            file=file,
            file_name=file.name,
            file_size=file.size
        )

        order.status = 'completed'
        order.save()

        return JsonResponse({
            'success': True,
            'status': 'completed',
            'message': f'سفارش با موفقیت تحویل داده شد (نسخه {new_version})',
            'version': new_version
        })

    except ContentTeamMember.DoesNotExist:
        return JsonResponse({'error': 'شما عضو تیم نیستید'}, status=403)
    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'خطای سرور: {str(e)}'}, status=500)


@login_required
def accept_revision(request, order_id, revision_id):
    """قبول درخواست ویرایش"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user, is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)
        revision = ContentOrderRevision.objects.get(id=revision_id, order=order)

        # فقط درخواست‌های pending قابل قبول هستند
        if revision.status != 'pending':
            return JsonResponse({'error': 'این درخواست قبلاً بررسی شده'}, status=400)

        # قبول درخواست
        revision.status = 'accepted'
        revision.save()

        # ========== برگردوندن سفارش به حالت در حال انجام ==========
        order.status = 'in_progress'
        order.save()

        # آپدیت وضعیت تحویل قبلی
        if hasattr(order, 'delivery'):
            order.delivery.status = 'revision_requested'
            order.delivery.save()

        return JsonResponse({
            'success': True,
            'message': 'درخواست ویرایش قبول شد. لطفاً نسخه جدید را تحویل دهید.'
        })

    except ContentTeamMember.DoesNotExist:
        return JsonResponse({'error': 'شما عضو تیم نیستید'}, status=403)
    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def reject_revision(request, order_id, revision_id):
    """رد درخواست ویرایش"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user, is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)
        revision = ContentOrderRevision.objects.get(id=revision_id, order=order)

        if revision.status != 'pending':
            return JsonResponse({'error': 'این درخواست قبلاً بررسی شده'}, status=400)

        # رد درخواست
        revision.status = 'rejected'
        revision.save()

        # ========== برگردوندن سفارش به حالت completed ==========
        order.status = 'completed'
        order.save()

        # برگردوندن وضعیت delivery به حالت قبل
        if hasattr(order, 'delivery'):
            order.delivery.status = 'delivered'
            order.delivery.save()

        return JsonResponse({
            'success': True,
            'message': 'درخواست ویرایش رد شد'
        })

    except ContentTeamMember.DoesNotExist:
        return JsonResponse({'error': 'شما عضو تیم نیستید'}, status=403)
    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
