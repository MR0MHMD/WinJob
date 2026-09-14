from campaigns.models import Campaign, CampaignTrackingLink
from django.contrib.auth.decorators import login_required
from influencers.models import Channel, ChannelBooking
from payment.models import Transaction, Invoice
from django.db.models.functions import TruncDate
from core.utils.utils import convert_to_jalali
from django.shortcuts import render, redirect
from django.db.models import Sum, Count, Avg
from content_team.models import ContentOrder
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import jdatetime
import json


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

    total_spent = Invoice.objects.filter(
        user=request.user,
        is_paid=True,
        payments__payment_method='gateway',
    ).aggregate(total=Sum('payable_amount'))['total'] or 0

    tracking_links = CampaignTrackingLink.objects.filter(
        campaign_influencer__campaign_id__in=campaign_ids
    )
    total_clicks = tracking_links.aggregate(total=Sum('clicks'))['total'] or 0
    total_unique_clicks = tracking_links.aggregate(total=Sum('unique_clicks'))['total'] or 0

    avg_cost_per_click = int(total_spent / total_clicks) if total_clicks > 0 else 0

    wallet_balance = advertiser.user.wallet.balance

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

    daily_spending = Invoice.objects.filter(
        user=request.user,
        is_paid=True,
        payments__payment_method='gateway',
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
    ).order_by('-created_at')[:10]

    recent_campaigns = campaigns.order_by('-created_at')[:10]

    top_channels = Channel.objects.filter(
        campaign_bookings__campaign_id__in=campaign_ids,
        campaign_bookings__status='completed'
    ).annotate(
        total_bookings=Count('campaign_bookings'),
        _avg_rating=Avg('reviews__rating')
    ).order_by('-total_bookings', '-_avg_rating')[:10]

    expiring_soon = campaigns.filter(
        status='running',
        end_date__gte=now,
        end_date__lte=now + timedelta(days=3)
    ).order_by('end_date')

    pending_review_bookings = ChannelBooking.objects.filter(
        campaign__advertiser=advertiser,
        status=ChannelBooking.Status.COMPLETED,
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