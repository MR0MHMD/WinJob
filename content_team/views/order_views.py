from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_iranian_payment.contrib.django import services

from gamification.models import Badge
from payment.models import Transaction, Payment
from ..forms import StandaloneOrderStep1Form
from ..models import ContentOrder, ContentTeam, ContentServicePlan
from django.db.models import Q, Avg, Count
import json


@login_required
def standalone_order_step1(request):
    """
    مرحله ۱: انتخاب نوع خدمت، تیم و پلن
    با پشتیبانی از پارامترهای URL برای انتخاب خودکار
    """

    # فقط تبلیغ‌دهنده‌ها میتونن سفارش بدن
    if not hasattr(request.user, 'advertiser_profile'):
        messages.error(request, 'شما دسترسی به این بخش ندارید.')
        return redirect('home')

    # ========== دریافت پارامترهای URL برای انتخاب خودکار ==========
    selected_service = request.GET.get('selected_service')
    selected_team = request.GET.get('selected_team')
    selected_plan = request.GET.get('selected_plan')
    return_to = request.GET.get('return_to')  # برای تشخیص برگشت از صفحه جزئیات

    # داده‌های قبلی از سشن (برای برگشت کاربر)
    step1_data = request.session.get('standalone_order_step1', {})

    if request.method == 'POST':
        form = StandaloneOrderStep1Form(request.POST)

        if form.is_valid():
            service_type = form.cleaned_data['service_type']
            team = form.cleaned_data['team']
            plan = form.cleaned_data['plan']
            order_name = form.cleaned_data['name']

            # ========== ۱. ایجاد سفارش با وضعیت DRAFT ==========
            order = ContentOrder.objects.create(
                name=order_name,
                team=team,
                plan=plan,
                price=plan.price,
                status=ContentOrder.Status.DRAFT,
                is_standalone=True,
                standalone_user=request.user,
            )

            # ========== ۲. ذخیره در سشن ==========
            request.session['standalone_order_step1'] = {
                'name': order_name,
                'service_type_id': service_type.id,
                'team_id': team.id,
                'plan_id': plan.id,
                'order_id': order.id,
            }

            messages.success(request, 'مرحله اول با موفقیت تکمیل شد. حالا اطلاعات سفارش رو وارد کنید.')
            return redirect('content_team:standalone_order_step2')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')

    else:
        # پر کردن فرم با داده‌های سشن یا پارامترهای URL
        initial = {}

        # اولویت ۱: پارامترهای URL
        if selected_service:
            initial['service_type'] = selected_service
        elif step1_data.get('service_type_id'):
            initial['service_type'] = step1_data.get('service_type_id')

        if selected_team:
            initial['team'] = selected_team
        elif step1_data.get('team_id'):
            initial['team'] = step1_data.get('team_id')

        if selected_plan:
            initial['plan'] = selected_plan
        elif step1_data.get('plan_id'):
            initial['plan'] = step1_data.get('plan_id')

        form = StandaloneOrderStep1Form(initial=initial)

    context = {
        'form': form,
        'step': 1,
        'total_steps': 3,
        'title': 'انتخاب خدمت و تیم تولید محتوا',
        # ========== اضافه شده برای انتخاب خودکار ==========
        'selected_service': selected_service,
        'selected_team': selected_team,
        'selected_plan': selected_plan,
        'return_to': return_to,
    }
    return render(request, 'content_team/forms/order/standalone_order_step1.html', context)


@login_required
@require_http_methods(["GET"])
def load_teams_by_service(request):
    """
    بارگذاری تیم‌های دارای پلن فعال برای یک سرویس خاص
    با پشتیبانی از جستجو و صفحه‌بندی
    """
    service_type_id = request.GET.get('service_type_id')
    search_query = request.GET.get('search', '').strip()
    page_number = request.GET.get('page', 1)

    if not service_type_id:
        return JsonResponse({'teams': [], 'total_pages': 0, 'current_page': 1, 'total_count': 0})

    try:
        team_ids = ContentServicePlan.objects.filter(
            service_type_id=service_type_id,
            is_active=True
        ).values_list('team_id', flat=True).distinct()

        teams = ContentTeam.objects.filter(
            id__in=team_ids,
            is_active=True
        )

        if search_query:
            teams = teams.filter(
                Q(name__icontains=search_query) |
                Q(slug__icontains=search_query)
            )

        teams = teams.annotate(
            _avg_rating=Avg('reviews__rating'),
            _completed_orders_count=Count('orders', filter=Q(orders__status='completed')),
            _members_count=Count('members', filter=Q(members__is_active=True)),
            _total_reviews=Count('reviews'),
        ).select_related('score', 'score__badge')

        paginator = Paginator(teams, 21)
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        teams_list = []
        for team in page_obj:
            avg_rating = team._avg_rating
            completed_orders_count = team._completed_orders_count or 0
            members_count = team._members_count or 0
            total_reviews = team._total_reviews or 0

            # ========== ✅ اطلاعات گیمیفیکیشن (مشابه gamification_status) ==========
            # ۱. امتیاز و نشان فعلی
            points = 0
            current_badge = None

            if hasattr(team, 'score') and team.score:
                points = team.score.points or 0
                current_badge = team.score.badge

            # ۲. اگر نشان فعلی معتبر نیست، اولین نشان فعال رو بگیر
            if not current_badge or not current_badge.is_active:
                # دنبال نشان چوبی بگرد، اگه نبود اولین نشان فعال رو بگیر
                current_badge = Badge.objects.filter(
                    is_active=True,
                    slug='wood'
                ).first()

                if not current_badge:
                    current_badge = Badge.objects.filter(is_active=True).order_by('min_points').first()

            # ۳. ساخت اطلاعات نشان
            badge_info = {
                'name': current_badge.name if current_badge else 'شروع',
                'slug': current_badge.slug if current_badge else 'start',
                'icon': current_badge.icon.url if (current_badge and current_badge.icon) else None,
                'min_points': current_badge.min_points if current_badge else 0,
            }

            members = team.members.filter(is_active=True).values('role').annotate(count=Count('id'))
            members_roles = {m['role']: m['count'] for m in members}

            team_dict = {
                'id': team.id,
                'name': team.name,
                'slug': team.slug,
                'logo': team.logo.url if team.logo else None,
                'description': team.description or '',
                'avg_rating': round(float(avg_rating), 1) if avg_rating is not None else None,
                'completed_orders_count': completed_orders_count,
                'members_count': members_count,
                'total_reviews': total_reviews,
                'is_active': team.is_active,
                'badge': badge_info,  # ✅ اطلاعات کامل نشان
                'members_roles': members_roles,
                'has_logo': bool(team.logo),
                'has_description': bool(team.description),
                'rating_display': f"{round(float(avg_rating), 1)}/5" if avg_rating else 'بدون امتیاز',
            }
            teams_list.append(team_dict)

        return JsonResponse({
            'teams': teams_list,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'total_count': paginator.count,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'teams': [],
            'total_pages': 0,
            'current_page': 1,
            'total_count': 0,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def load_plans_by_team(request):
    """
    بارگذاری پلن‌های فعال یک تیم برای یک سرویس خاص
    با تمام اطلاعات مورد نیاز برای کارت‌های پلن
    """
    service_type_id = request.GET.get('service_type_id')
    team_id = request.GET.get('team_id')

    if not service_type_id or not team_id:
        return JsonResponse({'plans': []})

    try:
        plans = ContentServicePlan.objects.filter(
            service_type_id=service_type_id,
            team_id=team_id,
            is_active=True
        ).select_related('service_type')

        plans_list = []
        for plan in plans:
            # محاسبه میانگین امتیاز این پلن
            avg_rating = plan.orders.filter(
                status__in=['completed', 'done'],
                review__isnull=False
            ).aggregate(avg=Avg('review__rating'))['avg']
            avg_rating = round(avg_rating, 1) if avg_rating else None

            # تعداد سفارشات تکمیل شده این پلن
            completed_count = plan.orders.filter(
                status__in=['completed', 'done']
            ).count()

            # ویژگی‌ها
            features = plan.features
            if isinstance(features, str):
                try:
                    features = json.loads(features)
                except:
                    features = []
            elif not isinstance(features, list):
                features = []

            # واحدهای قیمت‌گذاری
            unit_labels = {
                'second': 'ثانیه',
                'minute': 'دقیقه',
                'quantity': 'عدد'
            }
            pricing_unit_display = unit_labels.get(plan.pricing_unit, plan.pricing_unit)

            # نمایش مقدار
            quantity_display = None
            if plan.pricing_unit in ['second', 'minute']:
                if plan.min_quantity and plan.max_quantity and plan.min_quantity != plan.max_quantity:
                    quantity_display = f"{plan.min_quantity} تا {plan.max_quantity} {pricing_unit_display}"
                elif plan.base_quantity:
                    quantity_display = f"{plan.base_quantity} {pricing_unit_display}"
            elif plan.pricing_unit == 'quantity':
                if plan.delivery_options_count:
                    quantity_display = f"{plan.delivery_options_count} گزینه"
                else:
                    quantity_display = "تعدادی"

            plan_dict = {
                'id': plan.id,
                'name': plan.name,
                'description': plan.description or '',
                'price': int(plan.price),
                'price_display': f"{int(plan.price):,}",
                'pricing_unit': plan.pricing_unit,
                'pricing_unit_display': pricing_unit_display,
                'base_quantity': plan.base_quantity,
                'min_quantity': plan.min_quantity,
                'max_quantity': plan.max_quantity,
                'quantity_display': quantity_display,
                'delivery_type': plan.delivery_type,
                'delivery_type_display': plan.delivery_type_display,
                'delivery_options_count': plan.delivery_options_count,
                'estimated_delivery_days': plan.estimated_delivery_days or 5,
                'features': features,
                'avg_rating': avg_rating,
                'completed_orders_count': completed_count,
                'is_most_popular': completed_count > 5,
                'service_type_icon': plan.service_type.icon or 'fi-star',
                'service_type_name': plan.service_type.name,
            }
            plans_list.append(plan_dict)

        return JsonResponse({'plans': plans_list})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'plans': [], 'error': str(e)}, status=500)


# content_team/views/order_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.http import JsonResponse

from ..forms import StandaloneOrderStep2Form
from ..models import ContentOrder, ContentOrderDescription, ContentOrderFile
from campaigns.models import CampaignContent


@login_required
def standalone_order_step2(request):
    """
    مرحله ۲: پر کردن بریف و آپلود فایل‌های پیوست
    کاملاً مشابه بخش بریف در create_campaign_step3_team
    """
    # ========== دریافت سفارش از سشن ==========
    step1_data = request.session.get('standalone_order_step1', {})
    order_id = step1_data.get('order_id')

    if not order_id:
        messages.error(request, 'لطفاً ابتدا مرحله اول را تکمیل کنید.')
        return redirect('content_team:standalone_order_step1')

    order = get_object_or_404(
        ContentOrder,
        id=order_id,
        standalone_user=request.user,
        status=ContentOrder.Status.DRAFT,
        is_standalone=True
    )

    # ========== دریافت اطلاعات موجود ==========
    existing_brief = None
    if hasattr(order, 'brief'):
        existing_brief = order.brief

    attachments = order.files.all()

    # ========== پردازش POST ==========
    if request.method == 'POST':
        brief_form = StandaloneOrderStep2Form(
            request.POST,
            request.FILES,
            order=order,
            instance=existing_brief
        )

        if brief_form.is_valid():
            with transaction.atomic():
                # ========== ۱. ذخیره بریف ==========
                brief = brief_form.save(commit=False)
                brief.order = order
                brief.save()


                # ========== ۳. ذخیره فایل‌های پیوست ==========

                files = request.FILES.getlist('attachments')
                descriptions_json = request.POST.get('attachment_descriptions', '[]')
                import json
                try:
                    descriptions = json.loads(descriptions_json)
                except:
                    descriptions = []

                # حذف فایل‌های قدیمی که کاربر علامت زده
                deleted_ids_json = request.POST.get('deleted_attachments', '[]')
                try:
                    deleted_ids = json.loads(deleted_ids_json)
                    if deleted_ids:
                        ContentOrderFile.objects.filter(
                            id__in=deleted_ids,
                            order=order
                        ).delete()
                except:
                    pass

                # ذخیره فایل‌های جدید
                for idx, file in enumerate(files):
                    desc = descriptions[idx] if idx < len(descriptions) else ''
                    ContentOrderFile.objects.create(
                        order=order,
                        file=file,
                        original_name=file.name,
                        description=desc,
                        file_size=file.size,
                        file_type=ContentOrderFile.FileType.OTHER
                    )

                # ========== ۵. پاک کردن سشن ==========
                # سشن مرحله ۱ رو نگه میداریم برای مرحله ۳
                request.session['standalone_order_step2'] = {
                    'brief_id': brief.id,
                    'order_id': order.id,
                }

                messages.success(request, '✅ بریف سفارش با موفقیت ثبت شد. حالا به مرحله تایید و پرداخت بروید.')
                return redirect('content_team:standalone_order_step3')

        else:
            # نمایش خطاها
            for field, errors in brief_form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')

    else:
        # ========== GET: مقداردهی اولیه فرم ==========
        initial = {}
        if existing_brief:
            initial = {
                'goal': existing_brief.goal,
                'goal_description': existing_brief.goal_description,
                'tone': existing_brief.tone,
                'brand_name': existing_brief.brand_name,
                'hashtags': existing_brief.hashtags,
                'reference_links': existing_brief.reference_links,
                'target_audience': existing_brief.target_audience,
                'description': existing_brief.description,
                'do_not_include': existing_brief.do_not_include,
            }

        brief_form = StandaloneOrderStep2Form(
            initial=initial,
            order=order
        )

    # ========== محاسبه قیمت برای نمایش ==========
    plan_price = order.plan.price if order.plan else 0
    plan_name = order.plan.name if order.plan else '-'
    team_name = order.team.name if order.team else '-'

    # ========== Context ==========
    context = {
        'order': order,
        'brief_form': brief_form,
        'attachments': attachments,
        'plan_price': plan_price,
        'plan_name': plan_name,
        'team_name': team_name,
        'step': 2,
        'total_steps': 3,
        'title': 'جزئیات سفارش تولید محتوا',
        'subtitle': f'تیم: {team_name} | پلن: {plan_name}',
    }

    return render(request, 'content_team/forms/order/standalone_order_step2.html', context)


# content_team/views/order_views.py

from payment.services.create_invoice import create_standalone_invoice


@login_required
def standalone_order_step3(request):
    """
    مرحله ۳: تایید نهایی و پرداخت سفارش مستقل تولید محتوا
    """
    # ========== دریافت سفارش ==========
    step2_data = request.session.get('standalone_order_step2', {})
    order_id = step2_data.get('order_id')

    if not order_id:
        messages.error(request, 'لطفاً ابتدا مراحل قبل را تکمیل کنید.')
        return redirect('content_team:standalone_order_step1')

    order = get_object_or_404(
        ContentOrder,
        id=order_id,
        standalone_user=request.user,
        status=ContentOrder.Status.DRAFT,
        is_standalone=True
    )

    # ========== ساخت فاکتور ==========
    invoice = create_standalone_invoice(order)
    wallet = request.user.wallet

    # ========== پردازش POST (پرداخت) ==========
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'gateway')

        # ===== پرداخت از کیف پول =====
        if payment_method == 'wallet':
            if wallet.balance < invoice.payable_amount:
                messages.error(request, 'موجودی کیف پول کافی نیست.')
                return redirect('content_team:standalone_order_step3')

            with transaction.atomic():
                # کسر از کیف پول
                wallet.balance -= invoice.payable_amount
                wallet.save(update_fields=['balance'])

                # ثبت تراکنش
                Transaction.objects.create(
                    user=request.user,
                    amount=invoice.payable_amount,
                    type=Transaction.Type.CONTENT_ORDER_PAYMENT,  # باید به Type اضافه کنی
                    status=Transaction.Status.SUCCESS,
                    invoice=invoice,
                    description=f'پرداخت سفارش مستقل تولید محتوا #{order.id}',
                    reference_id=f'STANDALONE_WALLET_{order.id}_{timezone.now().timestamp()}'
                )

                # ثبت پرداخت
                Payment.objects.create(
                    user=request.user,
                    invoice=invoice,
                    amount=invoice.payable_amount,
                    status=Payment.Status.SUCCESS,
                    payment_method=Payment.Method.WALLET
                )

                # آپدیت فاکتور
                invoice.is_paid = True
                invoice.paid_at = timezone.now()
                invoice.save(update_fields=['is_paid', 'paid_at'])

                # تغییر وضعیت سفارش
                order.status = ContentOrder.Status.PENDING
                order.save(update_fields=['status'])

                # پاک کردن سشن
                request.session.pop('standalone_order_step1', None)
                request.session.pop('standalone_order_step2', None)

                # ====== ارسال نوتیف به کاربر ======
                from notifications.utils import create_notification
                create_notification(
                    user=request.user,
                    notification_type='new_content_order',
                    title='✅ سفارش شما با موفقیت ثبت شد',
                    message=f'سفارش تولید محتوا شما با شناسه #{order.id} با موفقیت ثبت شد.\n'
                            f'تیم «{order.team.name}» به زودی سفارش شما را بررسی میکند.',
                    link=f'/content_team/team/orders/{order.id}',
                    related_object_id=order.id,
                    related_content_type='ContentOrder'
                )

                # ====== ارسال نوتیف به تیم محتوا ======
                from notifications.utils import notify_content_team_new_order
                active_members = order.team.members.filter(is_active=True).select_related('user')
                for member in active_members:
                    notify_content_team_new_order(member.user, order)

                messages.success(request, '✅ سفارش شما با موفقیت ثبت و پرداخت شد.')
                return redirect('content_team:content_order_detail', order_id=order.id)

        # ===== پرداخت از درگاه =====
        else:
            try:
                # شروع فرآیند پرداخت
                payment_result, redirect_url = services.start_payment(
                    slug="zarinpal",
                    amount=invoice.payable_amount,
                    callback_url=request.build_absolute_uri(
                        reverse('payment:standalone_order_payment_callback')
                    ),
                    order_id=f"standalone_{order.id}_{int(timezone.now().timestamp())}",
                    description=f"پرداخت سفارش تولید محتوا #{order.id} - مبلغ {invoice.payable_amount:,} تومان",
                    mobile=request.user.phone_number,
                    email=request.user.email or '',
                )

                # ذخیره در سشن
                request.session['standalone_payment_authority'] = payment_result.authority
                request.session['standalone_payment_order_id'] = order.id
                request.session['standalone_payment_amount'] = invoice.payable_amount
                request.session['standalone_payment_invoice_id'] = invoice.id

                return redirect(redirect_url)

            except Exception as e:
                messages.error(request, f'خطا در اتصال به درگاه پرداخت: {str(e)}')
                return redirect('content_team:standalone_order_step3')

    # ========== GET: نمایش صفحه ==========
    context = {
        'order': order,
        'invoice': invoice,
        'wallet': wallet,
        'step': 3,
        'total_steps': 3,
        'title': 'تایید و پرداخت سفارش تولید محتوا',
        'plan_price': order.plan.price,
        'plan_name': order.plan.name,
        'team_name': order.team.name,
    }

    return render(request, 'content_team/forms/order/standalone_order_step3.html', context)