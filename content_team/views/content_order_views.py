from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from ..models import ContentOrder, ContentDelivery, ContentOrderRevision
from django.db.models import Q, Prefetch
from django.http import Http404


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

    return render(request, 'content_team/content_orders/content_orders_list.html', context)


@login_required
def content_order_detail(request, order_id):
    """
    صفحه جزئیات سفارش تولید محتوا
    - مستقل (standalone_user=request.user, is_standalone=True)
    - کمپینی (campaign__advertiser=request.user.advertiser_profile)

    URL params: هیچ
    """

    # ========== پیدا کردن سفارش با چک مالکیت ==========
    # کاربر یا باید سفارش‌دهنده مستقل باشه، یا تبلیغ‌دهنده صاحب کمپین
    order = ContentOrder.objects.filter(
        Q(id=order_id, standalone_user=request.user, is_standalone=True) |
        Q(id=order_id, campaign__advertiser=request.user.advertiser_profile)
    ).select_related(
        'campaign',
        'campaign__advertiser',
        'campaign__advertiser__user',
        'campaign__invoice',  # ← فاکتور کمپین (اگه هست)
        'campaign__invoice__user',
        'standalone_user',
        'team',
        'plan',
        'plan__service_type',
    ).prefetch_related(
        'files',
        Prefetch('brief'),
        Prefetch('deliveries', queryset=ContentDelivery.objects.prefetch_related('files').order_by('-version')),
        Prefetch('revisions',
                 queryset=ContentOrderRevision.objects.select_related('requested_by').order_by('-created_at')),
    ).first()

    if not order:
        # شاید سفارش هست ولی کاربر دسترسی نداره → 403 بهتر از 404
        exists = ContentOrder.objects.filter(id=order_id).exists()
        if exists:
            messages.error(request, 'شما به این سفارش دسترسی ندارید.')
            return redirect('content_team:content_orders_list')
        raise Http404("سفارش یافت نشد")

    # ========== تشخیص نوع سفارش ==========
    is_standalone = order.is_standalone and order.standalone_user_id == request.user.id
    is_campaign = order.campaign is not None

    # ========== فاکتور ==========
    invoice = None
    if is_standalone and hasattr(order, 'invoice'):
        invoice = order.invoice
    elif is_campaign and hasattr(order.campaign, 'invoice'):
        invoice = order.campaign.invoice

    # ========== محاسبه کمیسیون تیم محتوا (فقط برای کمپینی) ==========
    # در کمپین، کمیسیون کل شامل ناشران + محتواست، ولی توی این صفحه
    # فقط سهم مربوط به تیم محتوا رو نشون میدیم
    content_commission = 0
    if is_campaign and invoice and invoice.content_cost:
        # ۱۵٪ از هزینه تولید محتوا
        content_commission = int(invoice.content_cost * 0.15)

    # ========== بریف ==========
    brief = getattr(order, 'brief', None)

    # ========== فایل‌های پیوست ==========
    attachments = order.files.all()

    # ========== تحویل‌ها ==========
    deliveries = order.deliveries.all()  # به لطف Prefetch، از قبل sort شده

    # ========== ویرایش‌ها ==========
    revisions = order.revisions.all()

    # ========== بررسی فایل انتخاب شده ==========
    has_selected_file = order.has_selected_file()
    selected_file = None
    if has_selected_file:
        for delivery in deliveries:
            selected_file = delivery.files.filter(is_selected=True).first()
            if selected_file:
                break

    # ========== وضعیت‌ها ==========
    status_display = dict(ContentOrder.Status.choices).get(order.status, order.status)

    status_class_map = {
        'draft': 'secondary',
        'pending': 'warning',
        'review_pending': 'info',
        'in_progress': 'primary',
        'done': 'info',
        'completed': 'success',
        'cancelled': 'danger',
    }
    status_class = status_class_map.get(order.status, 'secondary')

    # ========== تعیین نوع تحویل ==========
    is_multi_choice = (
            order.plan and
            order.plan.delivery_type == 'multi_choice'
    )

    # ========== دکمه‌ها ==========
    # آیا کاربر می‌تونه ویرایش کنه؟ (فقط draft و pending)
    can_edit = order.status in ['draft', 'pending'] and is_standalone

    # آیا کاربر می‌تونه به مرحله پرداخت بره؟ (فقط مستقل + draft + بریف کامل)
    can_pay = (
            is_standalone
            and order.status == 'draft'
            and brief is not None
    )

    # آیا دکمه درخواست ویرایش نمایش داده بشه؟ (done + هنوز تأیید نشده)
    can_request_revision = (
            order.status == 'done'
            and not has_selected_file
    )

    # آیا دکمه تأیید نهایی نمایش داده بشه؟
    # - برای مستقل: همیشه (اگه done و تأیید نشده)
    # - برای کمپینی single: همیشه
    # - برای کمپینی multi_choice: نه (چون از دکمه select-option استفاده میشه)
    can_final_accept = (
            order.status == 'done'
            and not has_selected_file
            and not (is_campaign and is_multi_choice)
    )

    # آیا دکمه «انتخاب گزینه» نمایش داده بشه؟ (فقط کمپینی multi_choice)
    can_select_option = (
            is_campaign
            and is_multi_choice
            and order.status == 'done'
            and not has_selected_file
    )

    # ========== اطلاعات کاربر سفارش‌دهنده ==========
    if is_campaign:
        ordering_user = order.campaign.advertiser.user
        ordering_user_type = 'campaign'
        ordering_display_name = order.campaign.name
    elif is_standalone:
        ordering_user = order.standalone_user
        ordering_user_type = 'standalone'
        ordering_display_name = f'سفارش مستقل #{order.id}'
    else:
        ordering_user = None
        ordering_user_type = 'unknown'
        ordering_display_name = f'سفارش #{order.id}'

    # ========== Context ==========
    context = {
        'order': order,
        'invoice': invoice,
        'brief': brief,
        'attachments': attachments,
        'deliveries': deliveries,
        'revisions': revisions,
        'has_selected_file': has_selected_file,
        'selected_file': selected_file,

        # نوع سفارش
        'is_standalone': is_standalone,
        'is_campaign': is_campaign,
        'is_multi_choice': is_multi_choice,

        # مالی
        'content_commission': content_commission,

        # دکمه‌ها
        'can_edit': can_edit,
        'can_pay': can_pay,
        'can_request_revision': can_request_revision,
        'can_final_accept': can_final_accept,
        'can_select_option': can_select_option,

        # وضعیت
        'status_display': status_display,
        'status_class': status_class,

        # کاربر سفارش‌دهنده
        'ordering_user': ordering_user,
        'ordering_user_type': ordering_user_type,
        'ordering_display_name': ordering_display_name,

        # عنوان
        'title': f'جزئیات سفارش #{order.id}',
    }

    return render(request, 'content_team/content_orders/content_order_detail.html', context)


@login_required
def delete_content_order(request, order_id):
    """حذف سفارش پیش‌نویس (فقط برای مستقل)"""
    if request.method != 'POST':
        return redirect('content_team:content_orders_list')

    order = get_object_or_404(
        ContentOrder,
        id=order_id,
        standalone_user=request.user,
        is_standalone=True,
        status=ContentOrder.Status.DRAFT
    )

    order.delete()
    messages.success(request, '✅ سفارش پیش‌نویس با موفقیت حذف شد.')
    return redirect('content_team:content_orders_list')
