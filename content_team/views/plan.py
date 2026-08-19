from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from content_team.models import ContentServicePlan
from django.core.exceptions import ValidationError
from core.models import ContentServiceType
from django.http import JsonResponse
from django.contrib import messages
import traceback


@login_required
def service_plans_management(request, service_slug):
    """صفحه مدیریت پلن‌های یک خدمت خاص"""
    if not hasattr(request.user, 'team_member'):
        messages.error(request, 'شما عضو هیچ تیمی نیستید.')
        return redirect('core:home')

    team_member = request.user.team_member
    if not team_member.is_manager():
        messages.error(request, 'شما دسترسی مدیریت پلن‌ها را ندارید.')
        return redirect('accounts:dashboard_router')

    team = team_member.team

    service_type = get_object_or_404(
        ContentServiceType,
        slug=service_slug,
        is_active=True
    )

    plans = ContentServicePlan.objects.filter(
        team=team,
        service_type=service_type
    ).order_by('price')

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
    """ایجاد پلن جدید برای خدمت (API)"""
    if not hasattr(request.user, 'team_member'):
        return JsonResponse({
            'success': False,
            'error': 'شما عضو هیچ تیمی نیستید.'
        }, status=403)

    team_member = request.user.team_member
    if not team_member.is_manager():
        return JsonResponse({
            'success': False,
            'error': 'شما دسترسی مدیریت پلن‌ها را ندارید.'
        }, status=403)

    team = team_member.team
    service_type = get_object_or_404(ContentServiceType, slug=service_slug, is_active=True)

    active_plans_count = ContentServicePlan.objects.filter(
        team=team,
        service_type=service_type,
        is_active=True
    ).count()

    if active_plans_count >= 3:
        return JsonResponse({
            'success': False,
            'error': f'حداکثر ۳ پلن فعال برای هر خدمت مجاز است. (در حال حاضر {active_plans_count} پلن فعال)'
        }, status=400)

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'متود غیرمجاز'
        }, status=405)

    try:
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        features = request.POST.getlist('features')
        pricing_unit = request.POST.get('pricing_unit')

        # ========== ✅ quantity فقط برای SECOND و MINUTE ==========
        base_quantity = request.POST.get('base_quantity')
        min_quantity = request.POST.get('min_quantity')
        max_quantity = request.POST.get('max_quantity') or None

        price = request.POST.get('price', '').strip()
        delivery_type = request.POST.get('delivery_type', 'single')
        delivery_options_count = request.POST.get('delivery_options_count') or None
        estimated_delivery_days = request.POST.get('estimated_delivery_days', 5)
        is_active = request.POST.get('is_active') == 'on'

        errors = {}

        if not name:
            errors['name'] = 'نام پلن الزامی است.'

        if not price:
            errors['price'] = 'قیمت الزامی است.'
        else:
            try:
                price = int(str(price).replace(',', ''))
                if price <= 0:
                    errors['price'] = 'قیمت باید بزرگتر از ۰ باشد.'
            except ValueError:
                errors['price'] = 'قیمت باید یک عدد معتبر باشد.'

        if not pricing_unit:
            errors['pricing_unit'] = 'واحد قیمت‌گذاری الزامی است.'

        # ========== ✅ اعتبارسنجی شرطی quantity ==========
        is_time_unit = (pricing_unit in ['second', 'minute'])
        is_quantity_unit = (pricing_unit == 'quantity')

        if is_time_unit:
            # SECOND و MINUTE: quantity الزامی است
            try:
                base_quantity = int(base_quantity) if base_quantity else None
                min_quantity = int(min_quantity) if min_quantity else None

                if base_quantity is None or base_quantity <= 0:
                    errors['base_quantity'] = 'مقدار پایه الزامی و باید بزرگتر از ۰ باشد.'
                if min_quantity is None or min_quantity <= 0:
                    errors['min_quantity'] = 'حداقل مقدار الزامی و باید بزرگتر از ۰ باشد.'

                if base_quantity and min_quantity and min_quantity > base_quantity:
                    errors['min_quantity'] = 'حداقل مقدار نمی‌تواند از مقدار پایه بیشتر باشد.'

                if max_quantity:
                    try:
                        max_quantity = int(max_quantity)
                        if max_quantity < base_quantity:
                            errors['max_quantity'] = 'حداکثر مقدار نمی‌تواند از مقدار پایه کمتر باشد.'
                        if max_quantity < min_quantity:
                            errors['max_quantity'] = 'حداکثر مقدار نمی‌تواند از حداقل مقدار کمتر باشد.'
                    except ValueError:
                        errors['max_quantity'] = 'حداکثر مقدار باید عدد باشد.'

            except ValueError:
                errors['base_quantity'] = 'مقدار پایه باید عدد باشد.'
                errors['min_quantity'] = 'حداقل مقدار باید عدد باشد.'

        elif is_quantity_unit:
            # QUANTITY: quantity نباید پر شود
            if base_quantity:
                errors['base_quantity'] = 'برای واحد تعدادی، نیازی به مقدار پایه نیست.'
            if min_quantity:
                errors['min_quantity'] = 'برای واحد تعدادی، نیازی به حداقل مقدار نیست.'
            if max_quantity:
                errors['max_quantity'] = 'برای واحد تعدادی، نیازی به حداکثر مقدار نیست.'

            # QUANTITY فقط SINGLE و MULTI_CHOICE مجاز است
            if delivery_type not in ['single', 'multi_choice']:
                errors['delivery_type'] = 'برای واحد تعدادی، فقط تحویل یک فایل یا چند گزینه مجاز است.'

        # اعتبارسنجی delivery_options_count
        if delivery_type == 'multi_choice':
            if not delivery_options_count:
                errors['delivery_options_count'] = 'برای نوع تحویل "چند گزینه برای انتخاب"، تعداد گزینه‌ها الزامی است.'
            else:
                try:
                    delivery_options_count = int(delivery_options_count)
                    if delivery_options_count < 2:
                        errors['delivery_options_count'] = 'تعداد گزینه‌ها باید حداقل ۲ باشد.'
                except ValueError:
                    errors['delivery_options_count'] = 'تعداد گزینه‌ها باید عدد باشد.'

        features_list = [f for f in features if f.strip()]

        if errors:
            return JsonResponse({
                'success': False,
                'errors': errors,
                'message': 'لطفاً خطاهای فرم را برطرف کنید.'
            }, status=400)

        # ========== ساخت پلن ==========
        plan = ContentServicePlan.objects.create(
            team=team,
            service_type=service_type,
            name=name,
            description=description,
            features=features_list,
            pricing_unit=pricing_unit,
            base_quantity=base_quantity if is_time_unit else None,
            min_quantity=min_quantity if is_time_unit else None,
            max_quantity=max_quantity if is_time_unit else None,
            price=price,
            delivery_type=delivery_type,
            delivery_options_count=delivery_options_count,
            estimated_delivery_days=int(estimated_delivery_days),
            is_active=is_active
        )

        return JsonResponse({
            'success': True,
            'message': 'پلن با موفقیت ایجاد شد.',
            'plan_id': plan.id
        })

    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'errors': e.message_dict,
            'message': 'خطا در اعتبارسنجی داده‌ها.'
        }, status=400)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': 'خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.',
            'debug': str(e)
        }, status=500)


@login_required
def edit_plan(request, plan_id):
    """ویرایش پلن (API)"""
    if not hasattr(request.user, 'team_member'):
        return JsonResponse({
            'success': False,
            'error': 'شما عضو هیچ تیمی نیستید.'
        }, status=403)

    team_member = request.user.team_member
    if not team_member.is_manager():
        return JsonResponse({
            'success': False,
            'error': 'شما دسترسی مدیریت پلن‌ها را ندارید.'
        }, status=403)

    plan = get_object_or_404(ContentServicePlan, id=plan_id, team=team_member.team)

    if request.method == 'GET':
        return JsonResponse({
            'plan': {
                'id': plan.id,
                'name': plan.name,
                'description': plan.description,
                'features': plan.features,
                'pricing_unit': plan.pricing_unit,
                'base_quantity': plan.base_quantity,
                'min_quantity': plan.min_quantity,
                'max_quantity': plan.max_quantity,
                'price': str(plan.price),
                'delivery_type': plan.delivery_type,
                'delivery_options_count': plan.delivery_options_count,
                'estimated_delivery_days': plan.estimated_delivery_days,
                'is_active': plan.is_active,
            }
        })

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'متود غیرمجاز'
        }, status=405)

    try:
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        features = request.POST.getlist('features')
        pricing_unit = request.POST.get('pricing_unit')

        # ========== ✅ quantity فقط برای SECOND و MINUTE ==========
        base_quantity = request.POST.get('base_quantity')
        min_quantity = request.POST.get('min_quantity')
        max_quantity = request.POST.get('max_quantity') or None

        price = request.POST.get('price', '').strip()
        delivery_type = request.POST.get('delivery_type', 'single')
        delivery_options_count = request.POST.get('delivery_options_count') or None
        estimated_delivery_days = request.POST.get('estimated_delivery_days', 5)
        is_active = request.POST.get('is_active') == 'on'

        errors = {}

        if not name:
            errors['name'] = 'نام پلن الزامی است.'

        if not price:
            errors['price'] = 'قیمت الزامی است.'
        else:
            try:
                price = int(str(price).replace(',', ''))
                if price <= 0:
                    errors['price'] = 'قیمت باید بزرگتر از ۰ باشد.'
            except ValueError:
                errors['price'] = 'قیمت باید یک عدد معتبر باشد.'

        if not pricing_unit:
            errors['pricing_unit'] = 'واحد قیمت‌گذاری الزامی است.'

        # ========== ✅ اعتبارسنجی شرطی quantity ==========
        is_time_unit = (pricing_unit in ['second', 'minute'])
        is_quantity_unit = (pricing_unit == 'quantity')

        if is_time_unit:
            try:
                base_quantity = int(base_quantity) if base_quantity else None
                min_quantity = int(min_quantity) if min_quantity else None

                if base_quantity is None or base_quantity <= 0:
                    errors['base_quantity'] = 'مقدار پایه الزامی و باید بزرگتر از ۰ باشد.'
                if min_quantity is None or min_quantity <= 0:
                    errors['min_quantity'] = 'حداقل مقدار الزامی و باید بزرگتر از ۰ باشد.'

                if base_quantity and min_quantity and min_quantity > base_quantity:
                    errors['min_quantity'] = 'حداقل مقدار نمی‌تواند از مقدار پایه بیشتر باشد.'

                if max_quantity:
                    try:
                        max_quantity = int(max_quantity)
                        if max_quantity < base_quantity:
                            errors['max_quantity'] = 'حداکثر مقدار نمی‌تواند از مقدار پایه کمتر باشد.'
                        if max_quantity < min_quantity:
                            errors['max_quantity'] = 'حداکثر مقدار نمی‌تواند از حداقل مقدار کمتر باشد.'
                    except ValueError:
                        errors['max_quantity'] = 'حداکثر مقدار باید عدد باشد.'

            except ValueError:
                errors['base_quantity'] = 'مقدار پایه باید عدد باشد.'
                errors['min_quantity'] = 'حداقل مقدار باید عدد باشد.'

        elif is_quantity_unit:
            if base_quantity:
                errors['base_quantity'] = 'برای واحد تعدادی، نیازی به مقدار پایه نیست.'
            if min_quantity:
                errors['min_quantity'] = 'برای واحد تعدادی، نیازی به حداقل مقدار نیست.'
            if max_quantity:
                errors['max_quantity'] = 'برای واحد تعدادی، نیازی به حداکثر مقدار نیست.'

            if delivery_type not in ['single', 'multi_choice']:
                errors['delivery_type'] = 'برای واحد تعدادی، فقط تحویل یک فایل یا چند گزینه مجاز است.'

        if delivery_type == 'multi_choice':
            if not delivery_options_count:
                errors['delivery_options_count'] = 'برای نوع تحویل "چند گزینه برای انتخاب"، تعداد گزینه‌ها الزامی است.'
            else:
                try:
                    delivery_options_count = int(delivery_options_count)
                    if delivery_options_count < 2:
                        errors['delivery_options_count'] = 'تعداد گزینه‌ها باید حداقل ۲ باشد.'
                except ValueError:
                    errors['delivery_options_count'] = 'تعداد گزینه‌ها باید عدد باشد.'

        features_list = [f for f in features if f.strip()]

        if errors:
            return JsonResponse({
                'success': False,
                'errors': errors,
                'message': 'لطفاً خطاهای فرم را برطرف کنید.'
            }, status=400)

        # ========== بروزرسانی پلن ==========
        plan.name = name
        plan.description = description
        plan.features = features_list
        plan.pricing_unit = pricing_unit
        plan.base_quantity = base_quantity if is_time_unit else None
        plan.min_quantity = min_quantity if is_time_unit else None
        plan.max_quantity = max_quantity if is_time_unit else None
        plan.price = price
        plan.delivery_type = delivery_type
        plan.delivery_options_count = delivery_options_count
        plan.estimated_delivery_days = int(estimated_delivery_days)
        plan.is_active = is_active
        plan.save()

        return JsonResponse({
            'success': True,
            'message': 'پلن با موفقیت ویرایش شد.'
        })

    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'errors': e.message_dict,
            'message': 'خطا در اعتبارسنجی داده‌ها.'
        }, status=400)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': 'خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.',
            'debug': str(e)
        }, status=500)


@login_required
def delete_plan(request, plan_id):
    """حذف فیزیکی پلن (به همراه بررسی وابستگی)"""
    if not hasattr(request.user, 'team_member'):
        return JsonResponse({
            'success': False,
            'error': 'شما عضو هیچ تیمی نیستید.'
        }, status=403)

    team_member = request.user.team_member
    if not team_member.is_manager():
        return JsonResponse({
            'success': False,
            'error': 'شما دسترسی مدیریت پلن‌ها را ندارید.'
        }, status=403)

    plan = get_object_or_404(ContentServicePlan, id=plan_id, team=team_member.team)

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'متود غیرمجاز'
        }, status=405)

    try:
        if plan.orders.exists():
            return JsonResponse({
                'success': False,
                'error': f'این پلن در {plan.orders.count()} سفارش استفاده شده است و قابل حذف نیست. ابتدا آن سفارش‌ها را مدیریت کنید.'
            }, status=400)

        plan.delete()
        return JsonResponse({
            'success': True,
            'message': 'پلن با موفقیت حذف شد.'
        })

    except Exception:
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': 'خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.'
        }, status=500)
