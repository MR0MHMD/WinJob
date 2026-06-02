from campaigns.models import Campaign, CampaignClick, CampaignTrackingLink, CampaignInvoice, CampaignContent, \
    CampaignInfluencer
from django.shortcuts import render, get_object_or_404, redirect
from content_team.models import ContentOrder, ContentTeamMember
from django.contrib.auth.decorators import login_required
from content_team.models import ContentOrderRevision
from django.template.loader import render_to_string
from django.db.models.functions import TruncDate
from influencers.models import InfluencerChannel
from accounts.models import Wallet, Transaction
from django.db.models import Sum, Count, Avg
from django.core.paginator import Paginator
from core.utils import convert_to_jalali
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import json


@login_required
def campaigns_list(request):
    advertiser = request.user.advertiser_profile

    status_filter = request.GET.get("status", "all")

    # campaigns base queryset
    campaigns_qs = Campaign.objects.filter(
        advertiser=advertiser
    ).select_related(
        "platform",
        "content_type",
        "ad_type",
        "content_service_type",
        "invoice"
    )

    available_statuses = (
        campaigns_qs
        .values_list("status", flat=True)
        .distinct()
    )

    # convert to structure compatible with template
    filtered_status_choices = [
        (value, label)
        for value, label in Campaign.Status.choices
        if value in available_statuses
    ]

    campaigns = campaigns_qs
    if status_filter != "all":
        campaigns = campaigns.filter(status=status_filter)

    campaigns = campaigns.order_by("-created_at")

    # paginator
    paginator = Paginator(campaigns, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "campaigns": page_obj,
        "status_filter": status_filter,
        "statuses": filtered_status_choices,
    }

    # AJAX response
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string(
            "advertisers/partials/campaign_cards.html",
            context,
            request=request
        )
        return JsonResponse({"html": html})

    return render(request, "advertisers/pages/campaign_list.html", context)


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

    # progress based on campaign status
    progress_map = {
        "draft": 10,
        "pending": 20,
        "approved": 40,
        "running": 70,
        "completed": 100,
        "cancelled": 0,
    }

    progress_percent = progress_map.get(campaign.status, 0)

    # dynamic color from red to green
    r = int(255 - (progress_percent * 2.55))
    g = int(progress_percent * 2.55)
    b = 0

    progress_color = f"rgb({r}, {g}, {b})"

    # وضعیت پرداخت
    payment_status = False
    try:
        payment_status = campaign.invoice.is_paid
    except:
        pass

    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    # گرفتن کلیک‌های ۳۰ روز اخیر این کمپین
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
        if jalali_date:
            daily_labels.append(jalali_date.strftime('%d/%m'))
        else:
            daily_labels.append(d.strftime('%d/%m'))

    channels_list = sorted(channels_set)
    datasets = []
    color_palette = [
        '#fd5631', '#5d3cf2', '#ffc107', '#28a745', '#17a2b8',
        '#6f42c1', '#e83e8c', '#20c997', '#fd7e14', '#6610f2'
    ]

    for idx, channel in enumerate(channels_list):
        color = color_palette[idx % len(color_palette)]
        data_array = []
        for day in sorted_days:
            data_array.append(data_by_day.get(day, {}).get(channel, 0))
        datasets.append({
            'label': channel,
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

    context = {
        "campaign": campaign,
        "channels": channels,
        "channels_count": channels_count,
        "progress_percent": progress_percent,
        "payment_status": payment_status,
        "progress_color": progress_color,
        'daily_labels_json': json.dumps(daily_labels, ensure_ascii=False),
        'daily_datasets_json': json.dumps(datasets, ensure_ascii=False),
        'has_click_data': len(datasets) > 0 and len(daily_labels) > 0,
    }

    return render(request, "advertisers/pages/campaign_detail.html", context)


@login_required
def advertiser_dashboard(request):
    if not hasattr(request.user, 'advertiser_profile'):
        messages.error(request, "شما دسترسی به این صفحه ندارید.")
        return redirect('core:home')

    advertiser = request.user.advertiser_profile
    campaigns = Campaign.objects.filter(advertiser=advertiser)
    campaign_ids = campaigns.values_list('id', flat=True)

    total_campaigns = campaigns.count()
    active_campaigns = campaigns.filter(status='running').count()
    completed_campaigns = campaigns.filter(status='completed').count()

    total_spent = CampaignInvoice.objects.filter(
        campaign__advertiser=advertiser,
        is_paid=True
    ).aggregate(total=Sum('payable_amount'))['total'] or 0

    tracking_links = CampaignTrackingLink.objects.filter(
        campaign_influencer__campaign_id__in=campaign_ids
    )
    total_clicks = tracking_links.aggregate(total=Sum('clicks'))['total'] or 0
    total_unique_clicks = tracking_links.aggregate(total=Sum('unique_clicks'))['total'] or 0

    avg_cost_per_click = int(total_spent / total_clicks) if total_clicks > 0 else 0

    wallet_balance = advertiser.user.wallet.balance

    import jdatetime
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

    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    daily_spending = CampaignInvoice.objects.filter(
        campaign__advertiser=advertiser,
        is_paid=True,
        created_at__gte=last_30_days
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        total=Sum('payable_amount')
    ).order_by('day')

    daily_spending_labels = []
    daily_spending_data = []

    for item in daily_spending:
        if item['day']:
            jalali_date = convert_to_jalali(item['day'])
            if jalali_date:
                daily_spending_labels.append(jalali_date.strftime('%d/%m'))
                daily_spending_data.append(float(item['total']) if item['total'] else 0)

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:4]

    recent_campaigns = campaigns.order_by('-created_at')[:5]

    top_channels = InfluencerChannel.objects.filter(
        campaign_bookings__campaign_id__in=campaign_ids,
        campaign_bookings__status='completed'
    ).annotate(
        total_bookings=Count('campaign_bookings'),
        _avg_rating=Avg('reviews__rating')
    ).order_by('-total_bookings', '-_avg_rating')[:3]

    expiring_soon = campaigns.filter(
        status='running',
        end_date__gte=now,
        end_date__lte=now + timedelta(days=3)
    ).order_by('end_date')

    pending_review_bookings = CampaignInfluencer.objects.filter(
        campaign__advertiser=advertiser,
        status=CampaignInfluencer.Status.COMPLETED,
        review__isnull=True
    ).select_related('campaign', 'channel', 'channel__platform').order_by('-created_at')

    pending_review_orders = ContentOrder.objects.filter(
        campaign__advertiser=advertiser,
        status=ContentOrder.Status.COMPLETED,
        review__isnull=True
    ).select_related('campaign', 'team').order_by('-created_at')

    context = {
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'completed_campaigns': completed_campaigns,
        'pending_review_bookings': pending_review_bookings,
        'pending_review_orders': pending_review_orders,
        'total_pending_review': pending_review_orders.count() + pending_review_bookings.count(),
        'total_spent': total_spent,
        'total_clicks': total_clicks,
        'total_unique_clicks': total_unique_clicks,
        'avg_cost_per_click': avg_cost_per_click,
        'wallet_balance': wallet_balance,
        'persian_date': persian_date,
        'daily_spending_labels_json': json.dumps(daily_spending_labels, ensure_ascii=False),
        'daily_spending_data_json': json.dumps(daily_spending_data, ensure_ascii=False),
        'recent_campaigns': recent_campaigns,
        'recent_transactions': recent_transactions,
        'top_channels': top_channels,
        'expiring_soon': expiring_soon,
        'advertiser': advertiser,
        'gamification': advertiser.gamification_status,
    }

    return render(request, "advertisers/pages/dashboard.html", context)


@login_required
def request_revision(request, order_id):
    """
    درخواست ویرایش سفارش توسط تبلیغ‌دهنده - با یک فایل مرجع
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        order = ContentOrder.objects.get(
            id=order_id,
            campaign__advertiser=request.user.advertiser_profile
        )

        # فقط سفارشات completed قابل ویرایش هستند
        if order.status != 'completed':
            return JsonResponse({'error': 'این سفارش قابل ویرایش نیست'}, status=400)

        # چک کردن اینکه قبلاً درخواست pending وجود نداشته باشه
        if order.revisions.filter(status='pending').exists():
            return JsonResponse({'error': 'شما قبلاً یک درخواست ویرایش ثبت کرده‌اید'}, status=400)

        feedback = request.POST.get('feedback', '')
        if not feedback or not feedback.strip():
            return JsonResponse({'error': 'لطفاً توضیحات ویرایش را وارد کنید'}, status=400)

        file = request.FILES.get('revision_file')

        from campaigns.services.campaigns_notifications import create_revision_request_service
        create_revision_request_service(
            order=order,
            requested_by=request.user,
            feedback=feedback,
            file=file
        )

        return JsonResponse({
            'success': True,
            'message': 'درخواست ویرایش با موفقیت ثبت شد. در انتظار بررسی تیم تولید محتوا.',
            'new_status': 'review_pending'
        })

    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def final_accept_order(request, order_id):
    """
    تأیید نهایی سفارش توسط تبلیغ‌دهنده
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        order = ContentOrder.objects.get(
            id=order_id,
            campaign__advertiser=request.user.advertiser_profile
        )

        if order.status != 'completed':
            return JsonResponse({'error': 'این سفارش قابل تأیید نیست'}, status=400)

        if not hasattr(order, 'delivery') or order.delivery.status != 'delivered':
            return JsonResponse({'error': 'این سفارش قبلاً تأیید شده یا در وضعیت مناسبی نیست'}, status=400)

        content_cost = order.campaign.invoice.content_cost if hasattr(order.campaign, 'invoice') and order.campaign.invoice else 0

        if content_cost <= 0:
            return JsonResponse({'error': 'مبلغ تولید محتوا معتبر نیست'}, status=400)

        # گرفتن اعضای تیم همراه با یوزرها برای جلوگیری از N+1
        team_members = ContentTeamMember.objects.filter(
            team=order.team,
            is_active=True
        ).select_related('user')

        if not team_members.exists():
            return JsonResponse({'error': 'هیچ عضو فعالی در تیم وجود ندارد'}, status=400)

        total_percent = sum(member.revenue_share_percent for member in team_members)

        if total_percent != 100:
            return JsonResponse({'error': f'مجموع درصد سهام اعضای تیم باید ۱۰۰ باشد (در حال حاضر: {total_percent}%)'},
                                status=400)

        from campaigns.services.campaigns_notifications import accept_content_order_delivery
        accept_content_order_delivery(
            order=order,
            content_cost=content_cost,
            team_members=team_members
        )

        return JsonResponse({
            'success': True,
            'message': f'✅ سفارش با موفقیت تأیید شد!\n💰 مبلغ {content_cost:,} تومان بین {team_members.count()} عضو تیم تقسیم شد.\n📁 فایل نهایی در کمپین ذخیره گردید.',
            'content_cost': content_cost,
            'members_count': team_members.count(),
            'file_saved': True
        })

    except ContentOrder.DoesNotExist:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'خطای سرور: {str(e)}'}, status=500)
