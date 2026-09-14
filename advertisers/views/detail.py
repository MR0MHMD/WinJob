from content_team.models import ContentOrder, ContentDelivery, ContentOrderRevision
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from campaigns.models import Campaign, CampaignClick
from django.db.models.functions import TruncDate
from django.db.models import Count, Q, Prefetch
from core.utils.utils import convert_to_jalali
from influencers.models import ChannelBooking
from django.contrib import messages
from django.utils import timezone
from jdatetime import timedelta
from django.http import Http404
import json


@login_required
def campaign_detail(request, campaign_id):
    campaign = get_object_or_404(
        Campaign.objects.select_related(
            "platform",
            "content_type",
            "ad_type",
            "content_service_type",
            "invoice",
            "content",
        ),
        id=campaign_id,
        advertiser=request.user.advertiser_profile
    )

    channels = campaign.influencer_bookings.all()
    channels_count = channels.count()

    # ========== MULTI_CHOICE: دریافت دلیوری‌های با گزینه ==========
    content_order = campaign.content_orders.last() if campaign.content_orders.exists() else None
    multi_choice_deliveries = []
    is_multi_choice = False
    selected_option = None
    has_selected_file = False

    if content_order and content_order.plan and content_order.plan.delivery_type == 'multi_choice':
        is_multi_choice = True

        # ========== ✅ استفاده از متد has_selected_file ==========
        has_selected_file = content_order.has_selected_file()

        # دریافت همه دلیوری‌ها با فایل‌های گزینه‌دار
        deliveries = content_order.deliveries.prefetch_related('files').all()

        for delivery in deliveries:
            # فایل‌های گزینه‌دار این تحویل
            option_files = delivery.files.filter(is_option=True)
            for file_obj in option_files:
                multi_choice_deliveries.append({
                    'delivery': delivery,
                    'file': file_obj,
                    'option_number': file_obj.option_number,
                    'file_name': file_obj.file_name,
                    'file_size_display': file_obj.file_size_display,
                    'file_url': file_obj.file.url if file_obj.file else None,
                    'is_selected': file_obj.is_selected,
                })

                # پیدا کردن گزینه انتخاب شده
                if file_obj.is_selected:
                    selected_option = file_obj.option_number

        # ========== ✅ اگر فایلی انتخاب نشده، از CampaignContent چک کن (سازگاری با نسخه‌های قدیمی) ==========
        if not has_selected_file and campaign.content and campaign.content.media:
            campaign_media_url = campaign.content.media.url if campaign.content.media else None
            for item in multi_choice_deliveries:
                if item['file'] and campaign_media_url and item['file_url'] == campaign_media_url:
                    selected_option = item['option_number']
                    has_selected_file = True
                    break

    # ========== ۱. وضعیت رد شدن توسط اینفلوئنسرها ==========
    rejected_influencers = channels.filter(status=ChannelBooking.Status.REJECTED)
    has_rejected = rejected_influencers.exists()

    # ========== ۲. وضعیت رد شدن توسط تیم محتوا ==========
    all_content_orders_cancelled = content_order and content_order.status == ContentOrder.Status.CANCELLED
    has_ready_content = hasattr(campaign, 'content') and campaign.content and campaign.content.media

    show_content_team_rejected = (
            campaign.status == Campaign.Status.REVISION_NEEDED and
            all_content_orders_cancelled and
            not has_ready_content
    )

    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    # ========== کلیک‌های ۳۰ روز اخیر ==========
    if campaign.is_free:
        total_clicks_per_day = CampaignClick.objects.filter(
            tracking_link__campaign_influencer__campaign=campaign,
            created_at__gte=last_30_days
        ).annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            total=Count('id')
        ).order_by('day')

        daily_labels = []
        daily_data = []
        for item in total_clicks_per_day:
            d = item['day']
            jalali_date = convert_to_jalali(d)
            if jalali_date:
                daily_labels.append(jalali_date.strftime('%d/%m'))
            else:
                daily_labels.append(d.strftime('%d/%m'))
            daily_data.append(item['total'])

        datasets = [{
            'label': 'کلیک کل',
            'data': daily_data,
            'borderColor': '#fd5631',
            'backgroundColor': 'rgba(253, 86, 49, 0.1)',
            'borderWidth': 2,
            'fill': True,
            'tension': 0.3,
        }]
        has_click_data = len(daily_data) > 0

    else:
        clicks_qs = CampaignClick.objects.filter(
            tracking_link__campaign_influencer__campaign=campaign,
            created_at__gte=last_30_days
        ).annotate(
            day=TruncDate('created_at')
        ).values(
            'day',
            'tracking_link__campaign_influencer__channel__channel_name'
        ).annotate(
            count=Count('id')
        ).order_by('day')

        data_by_day = {}
        channels_set = set()
        for item in clicks_qs:
            day = item['day']
            channel_name = item['tracking_link__campaign_influencer__channel__channel_name']
            count = item['count']
            channels_set.add(channel_name)
            if day not in data_by_day:
                data_by_day[day] = {}
            data_by_day[day][channel_name] = count

        sorted_days = sorted(data_by_day.keys())
        daily_labels = []
        for d in sorted_days:
            jalali_date = convert_to_jalali(d)
            daily_labels.append(jalali_date.strftime('%d/%m') if jalali_date else d.strftime('%d/%m'))

        channels_list = sorted(channels_set)
        color_palette = ['#fd5631', '#5d3cf2', '#ffc107', '#28a745', '#17a2b8',
                         '#6f42c1', '#e83e8c', '#20c997', '#fd7e14', '#6610f2']
        datasets = []
        for idx, ch_name in enumerate(channels_list):
            color = color_palette[idx % len(color_palette)]
            data_array = [data_by_day.get(day, {}).get(ch_name, 0) for day in sorted_days]
            datasets.append({
                'label': ch_name,
                'data': data_array,
                'borderColor': color,
                'backgroundColor': f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.3,
                'pointBackgroundColor': color,
                'pointBorderColor': '#fff',
                'pointRadius': 3,
                'pointHoverRadius': 5,
            })
        has_click_data = len(datasets) > 0 and len(daily_labels) > 0

    context = {
        "campaign": campaign,
        "channels": channels,
        "channels_count": channels_count,
        "daily_labels_json": json.dumps(daily_labels, ensure_ascii=False),
        "daily_datasets_json": json.dumps(datasets, ensure_ascii=False),
        "has_click_data": has_click_data,
        "is_free_campaign": campaign.is_free,

        # ========== فیلدهای جدید ==========
        "has_rejected": has_rejected,
        "rejected_influencers": rejected_influencers,
        "show_content_team_rejected": show_content_team_rejected,
        "content_order": content_order,

        # ========== MULTI_CHOICE ==========
        "is_multi_choice": is_multi_choice,
        "multi_choice_deliveries": multi_choice_deliveries,
        "selected_option": selected_option,
        "has_selected_file": has_selected_file,
    }
    return render(request, "advertisers/pages/campaign_detail.html", context)

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
            return redirect('advertisers:content_orders_list')
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

    return render(request, 'advertisers/pages/content_order_detail.html', context)
