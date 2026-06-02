from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Count, Q
from content_team.models import ContentServiceType, ContentServicePlan


@login_required
def plans_dashboard(request):
    """
    صفحه داشبورد مدیریت پلن‌ها - نمایش لیست خدمات به صورت کارتی
    """
    if not hasattr(request.user, 'team_member'):
        messages.error(request, 'شما عضو هیچ تیمی نیستید.')
        return redirect('dashboard')

    team_member = request.user.team_member
    if not team_member.is_manager():
        messages.error(request, 'شما دسترسی مدیریت پلن‌ها را ندارید.')
        return redirect('team:dashboard')

    team = team_member.team

    # دریافت همه خدمات فعال با تعداد پلن‌های فعال هر تیم
    service_types = ContentServiceType.objects.filter(
        is_active=True
    ).annotate(
        plans_count=Count(
            'plans',
            filter=Q(plans__team=team, plans__is_active=True)
        )
    ).order_by('display_order', 'name')

    # برای هر خدمت، پلن‌های فعال رو بگیر (حداکثر ۳ تا برای نمایش)
    for service in service_types:
        service.active_plans = ContentServicePlan.objects.filter(
            team=team,
            service_type=service,
            is_active=True
        )[:3]

    # محاسبه آمارهای مورد نیاز
    total_services = service_types.count()
    services_with_plans = service_types.filter(plans_count__gt=0).count()
    services_without_plans = service_types.filter(plans_count=0).count()
    total_plans = sum(service.plans_count for service in service_types)

    context = {
        'team': team,
        'service_types': service_types,
        'max_plans_per_service': 3,
        # آمارهای جدید
        'total_services': total_services,
        'services_with_plans': services_with_plans,
        'services_without_plans': services_without_plans,
        'total_plans': total_plans,
    }

    return render(request, 'content_team/plans/plans_dashboard.html', context)


def plan_detail(request, plan_id):
    plan = get_object_or_404(
        ContentServicePlan.objects.select_related('team', 'service_type'),
        id=plan_id, is_active=True
    )
    team = plan.team
    from_campaign = request.GET.get('from') == 'create_campaign'

    page = request.GET.get('page', '1')

    context = {
        'plan': plan,
        'team': team,
        'completed_orders_count': team.orders.filter(status='completed').count(),
        'portfolio_items': team.portfolio_items.filter(is_active=True)[:6],
        'members': team.members.filter(is_active=True),
        'reviews': team.reviews.select_related('advertiser__user').all()[:5],
        'from_campaign': from_campaign,
        'page': page,
    }
    return render(request, 'content_team/pages/plan_detail.html', context)


@login_required
def service_plans_management(request, service_slug):
    """
    صفحه مدیریت پلن‌های یک خدمت خاص
    """
    # بررسی دسترسی
    if not hasattr(request.user, 'team_member'):
        messages.error(request, 'شما عضو هیچ تیمی نیستید.')
        return redirect('dashboard')

    team_member = request.user.team_member
    if not team_member.is_manager():
        messages.error(request, 'شما دسترسی مدیریت پلن‌ها را ندارید.')
        return redirect('team:dashboard')

    team = team_member.team

    # دریافت نوع خدمت
    service_type = get_object_or_404(
        ContentServiceType,
        slug=service_slug,
        is_active=True
    )

    # دریافت پلن‌های فعال این تیم برای این خدمت
    plans = ContentServicePlan.objects.filter(
        team=team,
        service_type=service_type
    ).order_by('price_per_unit')

    # بررسی اینکه چند پلن فعال دیگه میتونه بسازه
    active_plans_count = plans.filter(is_active=True).count()
    can_add_plan = active_plans_count < 3

    context = {
        'team': team,
        'service_type': service_type,
        'plans': plans,
        'active_plans_count': active_plans_count,
        'can_add_plan': can_add_plan,
        'max_plans': 3,
    }

    return render(request, 'content_team/plans/service_plans_management.html', context)


@login_required
def create_plan(request, service_slug):
    """
    ایجاد پلن جدید برای خدمت
    """
    if not hasattr(request.user, 'team_member'):
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)

    team_member = request.user.team_member
    if not team_member.is_manager():
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)

    team = team_member.team
    service_type = get_object_or_404(ContentServiceType, slug=service_slug, is_active=True)

    # بررسی تعداد پلن‌های فعال
    active_plans_count = ContentServicePlan.objects.filter(
        team=team,
        service_type=service_type,
        is_active=True
    ).count()

    if active_plans_count >= 3:
        return JsonResponse({'error': 'حداکثر ۳ پلن فعال برای هر خدمت مجاز است.'}, status=400)

    if request.method == 'POST':
        # پردازش فرم
        name = request.POST.get('name')
        description = request.POST.get('description')
        features = request.POST.getlist('features')  # آرایه از ویژگی‌ها
        price_per_unit = request.POST.get('price_per_unit')
        estimated_delivery_days = request.POST.get('estimated_delivery_days')
        is_active = request.POST.get('is_active') == 'on'

        # اعتبارسنجی ساده
        if not name or not price_per_unit:
            return JsonResponse({'error': 'نام و قیمت الزامی هستند.'}, status=400)

        # تبدیل features به لیست
        features_list = [f for f in features if f.strip()]

        plan = ContentServicePlan.objects.create(
            team=team,
            service_type=service_type,
            name=name,
            description=description,
            features=features_list,
            price_per_unit=price_per_unit,
            estimated_delivery_days=estimated_delivery_days or 5,
            is_active=is_active
        )

        return JsonResponse({
            'success': True,
            'message': 'پلن با موفقیت ایجاد شد.',
            'plan_id': plan.id
        })

    return JsonResponse({'error': 'متود غیرمجاز'}, status=405)


@login_required
def edit_plan(request, plan_id):
    """
    ویرایش پلن
    """
    if not hasattr(request.user, 'team_member'):
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)

    team_member = request.user.team_member
    if not team_member.is_manager():
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)

    plan = get_object_or_404(ContentServicePlan, id=plan_id, team=team_member.team)

    if request.method == 'POST':
        plan.name = request.POST.get('name', plan.name)
        plan.description = request.POST.get('description', plan.description)
        features = request.POST.getlist('features')
        plan.features = [f for f in features if f.strip()]
        plan.price_per_unit = request.POST.get('price_per_unit', plan.price_per_unit)
        plan.estimated_delivery_days = request.POST.get('estimated_delivery_days', plan.estimated_delivery_days)
        plan.is_active = request.POST.get('is_active') == 'on'
        plan.save()

        return JsonResponse({
            'success': True,
            'message': 'پلن با موفقیت ویرایش شد.'
        })

    return JsonResponse({'plan': {
        'id': plan.id,
        'name': plan.name,
        'description': plan.description,
        'features': plan.features,
        'price_per_unit': str(plan.price_per_unit),
        'estimated_delivery_days': plan.estimated_delivery_days,
        'is_active': plan.is_active,
    }})


@login_required
def delete_plan(request, plan_id):
    """
    حذف فیزیکی پلن (به همراه بررسی وابستگی)
    """
    if not hasattr(request.user, 'team_member'):
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)

    team_member = request.user.team_member
    if not team_member.is_manager():
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)

    plan = get_object_or_404(ContentServicePlan, id=plan_id, team=team_member.team)

    if request.method == 'POST':
        # بررسی اینکه پلن در سفارشی استفاده شده باشد
        if plan.orders.exists():
            return JsonResponse({
                'error': 'این پلن در سفارش(هایی) استفاده شده است و قابل حذف نیست. ابتدا آن سفارش‌ها را مدیریت کنید.'
            }, status=400)

        plan.delete()
        return JsonResponse({
            'success': True,
            'message': 'پلن با موفقیت حذف شد.'
        })

    return JsonResponse({'error': 'متود غیرمجاز'}, status=405)
