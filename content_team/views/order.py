from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Prefetch, Sum
from django.core.paginator import Paginator
from campaigns.models import Campaign
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from campaigns.services.campaigns_notifications import (
    reject_revision_service,
    accept_revision_service,
    accept_content_order_service,
    reject_content_order_service,
    deliver_content_order_service,
)
from content_team.models import (
    ContentOrder,
    ContentDelivery,
    ContentTeamMember,
    ContentServicePlan,
    ContentDeliveryFile,
    ContentOrderRevision
)


@login_required
def team_orders_list(request):
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

    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-created_at')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    show_current_only = request.GET.get('current') == '1'

    # ========== کوئری پایه ==========
    # همه سفارش‌های تیم (بدون فیلتر اولیه)
    orders = ContentOrder.objects.filter(team=user_team).exclude(status='draft')

    # ========== فیلتر کمپین‌های پیش‌نویس ==========
    # فقط سفارش‌هایی که کمپین دارند و وضعیت کمپین DRAFT یا PENDING نباشند
    # یا سفارش‌های مستقل که کمپین ندارند
    from django.db.models import Q
    orders = orders.filter(
        Q(campaign__isnull=True) |  # سفارش‌های مستقل
        ~Q(campaign__status__in=[Campaign.Status.DRAFT, Campaign.Status.PENDING])  # کمپین‌های معتبر
    )

    if show_current_only:
        orders = orders.exclude(status__in=['completed', 'cancelled'])

    # ========== انتخاب فیلدهای مرتبط ==========
    orders = orders.select_related(
        'campaign',
        'campaign__advertiser',
        'campaign__advertiser__user',
        'standalone_user',          # ✅ اضافه شد
        'plan',
        'plan__service_type',
    ).prefetch_related(
        'brief',
        'files',
        'revisions',
        'deliveries__files',
    ).annotate(
        files_count=Count('files'),
        revisions_count=Count('revisions')
    ).order_by(sort_by)

    # ========== اعمال فیلترها ==========
    if status_filter:
        orders = orders.filter(status=status_filter)

    if search_query:
        orders = orders.filter(
            Q(campaign__name__icontains=search_query) |
            Q(campaign__advertiser__user__nickname__icontains=search_query) |
            Q(campaign__advertiser__business_name__icontains=search_query) |
            Q(standalone_user__nickname__icontains=search_query) |      # ✅ جدید
            Q(standalone_user__phone_number__icontains=search_query) |  # ✅ جدید
            Q(brief__brand_name__icontains=search_query)
        )

    if price_min:
        orders = orders.filter(price__gte=int(price_min))
    if price_max:
        orders = orders.filter(price__lte=int(price_max))

    # ========== آمار ==========
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

    # ========== صفحه‌بندی ==========
    paginator = Paginator(orders, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'orders': page_obj,
        'stats': stats,
        'current_status': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'price_min': price_min,
        'price_max': price_max,
        'status_choices': ContentOrder.Status.choices,
        'user_team': user_team,
        'team_member': team_member,
        'is_team_member': True,
        'page_obj': page_obj,
    }

    return render(request, 'content_team/pages/team_order_list.html', context)


@login_required
def team_order_detail(request, order_id):
    """نمایش جزئیات سفارش (پشتیبانی از سفارش‌های مستقل)"""

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        user_team = team_member.team
    except ContentTeamMember.DoesNotExist:
        messages.warning(request, 'شما عضو هیچ تیم تولید محتوایی نیستید!')
        return redirect('content_team:team_orders_list')

    # ========== دریافت سفارش با prefetch کامل ==========
    order = get_object_or_404(
        ContentOrder.objects.select_related(
            'campaign',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'team',
            'plan',
            'plan__service_type',
            'standalone_user',          # ✅ اضافه شد
        ).prefetch_related(
            'brief',
            'files',
            'revisions',
            Prefetch(
                'deliveries',
                queryset=ContentDelivery.objects.prefetch_related('files').all()
            ),
        ),
        id=order_id,
        team=user_team
    )

    # ========== تعیین کاربر سفارش‌دهنده (تبلیغ‌دهنده یا مستقل) ==========
    if order.campaign:
        # حالت کمپین: کاربر از طریق campaign.advertiser.user
        ordering_user = order.campaign.advertiser.user
        ordering_user_type = 'campaign'
    elif order.standalone_user:
        # حالت مستقل: کاربر مستقیم
        ordering_user = order.standalone_user
        ordering_user_type = 'content_orders'
    else:
        ordering_user = None
        ordering_user_type = 'unknown'

    # ========== بقیه منطق (بدون تغییر) ==========
    show_count_down = False
    if order.status in ["in_progress", "review_pending"]:
        show_count_down = True

    revisions = order.revisions.all().order_by('-created_at')

    # پیدا کردن فایل انتخاب شده
    selected_file = None
    for delivery in order.deliveries.all():
        selected_file = delivery.files.filter(is_selected=True).first()
        if selected_file:
            break

    # تعداد فایل‌های مورد نیاز برای تحویل
    if order.plan.delivery_type == 'single':
        required_file_count = 1
    else:
        if order.plan.pricing_unit == 'quantity':
            required_file_count = order.plan.delivery_options_count or 2
        else:
            required_file_count = 1

    # ========== اطلاعات وضعیت ==========
    status_info = {
        'pending': {
            'badge_class': 'bg-warning bg-opacity-10 text-warning',
            'icon': 'fi-clock',
            'text': 'در انتظار تایید'
        },
        'in_progress': {
            'badge_class': 'bg-primary bg-opacity-10 text-primary',
            'icon': 'fi-settings',
            'text': 'در حال انجام'
        },
        'review_pending': {
            'badge_class': 'bg-info bg-opacity-10 text-info',
            'icon': 'fi-edit',
            'text': 'در انتظار ویرایش'
        },
        'completed': {
            'badge_class': 'bg-success bg-opacity-10 text-success',
            'icon': 'fi-check-circle',
            'text': 'تکمیل شده'
        },
        'done': {
            'badge_class': 'bg-success bg-opacity-10 text-success',
            'icon': 'fi-check-circle',
            'text': 'تحویل داده شد'
        },
        'cancelled': {
            'badge_class': 'bg-danger bg-opacity-10 text-danger',
            'icon': 'fi-x-circle',
            'text': 'لغو شده'
        }
    }
    current_status_info = status_info.get(order.status, status_info['pending'])

    context = {
        'order': order,
        'team_member': team_member,
        'revisions': revisions,
        'user_team': user_team,
        'show_count_down': show_count_down,
        'brief': getattr(order, 'brief', None),
        'attached_files': order.files.all(),
        'current_status_info': current_status_info,
        'selected_file': selected_file,
        'required_file_count': required_file_count,
        # ========== متغیرهای جدید برای تمپلیت ==========
        'ordering_user': ordering_user,
        'ordering_user_type': ordering_user_type,  # 'campaign' یا 'content_orders'
        'is_standalone': order.is_standalone,
    }

    return render(request, 'content_team/pages/team_order_detail.html', context)


@login_required
def accept_order(request, order_id):
    order = None
    if request.method != 'POST':
        messages.error(request, "روش ارسال نامعتبر است.")
        return redirect('content_team:team_order_detail', order_id=order_id)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        order = ContentOrder.objects.select_related('plan').get(id=order_id, team=team_member.team)

        if order.status != 'pending':
            messages.error(request, 'این سفارش قابل قبول نیست')
            return redirect(order)

        estimated_days = order.plan.estimated_delivery_days
        deadline = timezone.now() + timedelta(days=estimated_days)

        order.deadline = deadline
        order.deadline_timestamp = int(deadline.timestamp() * 1000)
        order.status = 'in_progress'
        order.save(update_fields=['deadline', 'deadline_timestamp', 'status'])

        accept_content_order_service(order)

        messages.success(request, f'✅ سفارش #{order.id} با موفقیت قبول شد.')

    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو تیم نیستید')
    except ContentOrder.DoesNotExist:
        messages.error(request, 'سفارش یافت نشد')
    except Exception as e:
        messages.error(request, f'خطا: {str(e)}')
    return redirect(order)


@login_required
def reject_order(request, order_id):
    order = None
    if request.method != 'POST':
        messages.error(request, "روش ارسال نامعتبر است.")
        return redirect('content_team:team_order_detail', order_id=order_id)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)

        if order.status != 'pending':
            messages.error(request, 'این سفارش قابل رد نیست')
            return redirect(order)

        reject_content_order_service(order)

        messages.warning(request, f'⚠️ سفارش #{order.id} رد شد. ۵۰ امتیاز منفی برای تیم ثبت شد!')

    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو تیم نیستید')
    except ContentOrder.DoesNotExist:
        messages.error(request, 'سفارش یافت نشد')
    except Exception as e:
        messages.error(request, f'خطا: {str(e)}')

    return redirect(order)


@login_required
def deliver_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'روش ارسال نامعتبر است.'}, status=405)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user,
            is_active=True
        )
        order = ContentOrder.objects.select_related('plan').get(id=order_id, team=team_member.team)

        if order.status != 'in_progress':
            return JsonResponse({'error': 'این سفارش قابل تحویل نیست'}, status=400)

        delivery_type = order.plan.delivery_type
        notes = request.POST.get('notes', '')

        # ========== تشخیص نوع تحویل ==========
        if delivery_type == ContentServicePlan.DeliveryType.SINGLE:
            files_list = request.FILES.getlist('delivery_file')
            if not files_list:
                return JsonResponse({'error': 'لطفاً یک فایل برای تحویل انتخاب کنید'}, status=400)

            file_obj = files_list[0]
            if isinstance(file_obj, list):
                file_obj = file_obj[0] if file_obj else None
            if not file_obj:
                return JsonResponse({'error': 'فایل انتخاب شده معتبر نیست'}, status=400)

            files_to_upload = [file_obj]
            is_multi_choice = False

        elif delivery_type == ContentServicePlan.DeliveryType.MULTI_CHOICE:
            if order.plan.pricing_unit == 'quantity':
                required_count = order.plan.delivery_options_count or 2
            else:
                required_count = 1

            uploaded_files = request.FILES.getlist('delivery_files')
            if len(uploaded_files) != required_count:
                return JsonResponse({
                    'error': f'این پلن نیاز به تحویل {required_count} فایل دارد. شما {len(uploaded_files)} فایل ارسال کردید.'
                }, status=400)

            files_to_upload = uploaded_files
            is_multi_choice = True
        else:
            return JsonResponse({'error': f'نوع تحویل "{delivery_type}" پشتیبانی نمی‌شود.'}, status=400)

        # ========== مدیریت دلیوری‌های قبلی ==========
        existing_deliveries = ContentDelivery.objects.filter(order=order)

        if existing_deliveries.exists():
            last_version = existing_deliveries.order_by('-version').first().version
            new_version = last_version + 1

            for delivery in existing_deliveries:
                delivery_files = delivery.files.all()
                for delivery_file in delivery_files:
                    if delivery_file.file:
                        try:
                            delivery_file.file.delete(save=False)
                        except Exception as e:
                            print(f"Error deleting file: {e}")

                    delivery_file.file = None
                    delivery_file.file_name = f"[پاک شده] {delivery_file.file_name}" if delivery_file.file_name else "[پاک شده]"
                    delivery_file.file_size = None
                    delivery_file.save(update_fields=['file', 'file_name', 'file_size'])

                delivery.status = ContentDelivery.DeliveryStatus.REVISION_REQUESTED
                delivery.save(update_fields=['status'])
        else:
            new_version = 1

        # ========== ایجاد دلیوری جدید ==========
        delivery = ContentDelivery.objects.create(
            order=order,
            status=ContentDelivery.DeliveryStatus.DELIVERED,
            delivered_by=team_member,
            delivered_at=timezone.now(),
            notes=notes,
            version=new_version
        )

        # ========== ایجاد فایل‌های تحویل جدید ==========
        delivery_files = []
        for index, file_obj in enumerate(files_to_upload):
            if isinstance(file_obj, list):
                file_obj = file_obj[0] if file_obj else None
            if not file_obj:
                continue

            delivery_file = ContentDeliveryFile.objects.create(
                delivery=delivery,
                file=file_obj,
                file_name=file_obj.name,
                file_size=file_obj.size,
                is_option=is_multi_choice,
                option_number=index + 1 if is_multi_choice else None
            )
            delivery_files.append(delivery_file)

        # ========== تغییر وضعیت سفارش ==========
        order.status = ContentOrder.Status.DONE
        order.save(update_fields=['status'])

        deliver_content_order_service(order=order, primary_delivery=delivery)

        return JsonResponse({
            'success': True,
            'message': f'✅ سفارش #{order.id} با موفقیت تحویل داده شد (نسخه {new_version})',
            'version': new_version,
            'files_count': len(delivery_files)
        })

    except ContentTeamMember.DoesNotExist:
        return JsonResponse({'error': 'شما عضو تیم نیستید'}, status=403)
    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'خطا: {str(e)}'}, status=500)


@login_required
def accept_revision(request, order_id, revision_id):
    order = None

    if request.method != 'POST':
        messages.error(request, "روش ارسال نامعتبر است.")
        return redirect('content_team:team_order_detail', order_id=order_id)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user, is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)
        revision = ContentOrderRevision.objects.get(id=revision_id, order=order)

        if revision.status != 'pending':
            messages.error(request, 'این درخواست قبلاً بررسی شده')
            return redirect(order)

        accept_revision_service(order, revision)

        order.status = 'in_progress'
        order.save()

        messages.success(request, '✅ درخواست ویرایش قبول شد. لطفاً نسخه جدید را تحویل دهید.')

    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو تیم نیستید')
    except ContentOrder.DoesNotExist:
        messages.error(request, 'سفارش یافت نشد')
    except Exception as e:
        messages.error(request, f'خطا: {str(e)}')

    return redirect(order)


@login_required
def reject_revision(request, order_id, revision_id):
    order = None

    if request.method != 'POST':
        messages.error(request, "روش ارسال نامعتبر است.")
        return redirect('content_team:team_order_detail', order_id=order_id)

    try:
        team_member = ContentTeamMember.objects.select_related('team').get(
            user=request.user, is_active=True
        )
        order = ContentOrder.objects.get(id=order_id, team=team_member.team)
        revision = ContentOrderRevision.objects.get(id=revision_id, order=order)

        if revision.status != 'pending':
            messages.error(request, 'این درخواست قبلاً بررسی شده')
            return redirect(order)

        reject_revision_service(order, revision)

        messages.info(request, 'ℹ️ درخواست ویرایش رد شد. سفارش به حالت انجام شده بازگشت.')

    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو تیم نیستید')
    except ContentOrder.DoesNotExist:
        messages.error(request, 'سفارش یافت نشد')
    except Exception as e:
        messages.error(request, f'خطا: {str(e)}')

    return redirect(order)
