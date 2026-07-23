from content_team.models import ContentOrder, ContentTeamMember, ContentDelivery, ContentDeliveryFile
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from payment.models import Transaction, CampaignInvoice
from django.template.loader import render_to_string
from django.db.models.functions import TruncDate
from influencers.models import InfluencerChannel
from django.db.models import Sum, Count, Avg
from django.core.paginator import Paginator
from core.utils import convert_to_jalali
from plat_form.models import Platform
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import jdatetime
import json
from campaigns.models import (
    Campaign,
    CampaignClick,
    CampaignTrackingLink,
    CampaignInfluencer,
    CampaignContent,
    AdType
)


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
    print(campaign.content_orders.all())
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
    rejected_influencers = channels.filter(status=CampaignInfluencer.Status.REJECTED)
    has_rejected = rejected_influencers.exists()

    # ========== ۲. وضعیت رد شدن توسط تیم محتوا ==========
    all_content_orders_cancelled = content_order and content_order.status == ContentOrder.Status.CANCELLED
    has_ready_content = hasattr(campaign, 'content') and campaign.content and campaign.content.media

    show_content_team_rejected = (
            campaign.status == Campaign.Status.REVISION_NEEDED and
            all_content_orders_cancelled and
            not has_ready_content
    )

    # progress based on campaign status
    progress_map = {
        "draft": 10,
        "pending": 20,
        "approved": 40,
        "running": 70,
        "completed": 100,
        "cancelled": 0,
        "revision_needed": 15,
    }
    progress_percent = progress_map.get(campaign.status, 0)
    r = int(255 - (progress_percent * 2.55))
    g = int(progress_percent * 2.55)
    progress_color = f"rgb({r}, {g}, 0)"

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
        "progress_percent": progress_percent,
        "progress_color": progress_color,
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
def select_multi_choice_option(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        delivery_file_id = request.POST.get('delivery_file_id')
        if not delivery_file_id:
            return JsonResponse({'error': 'شناسه فایل یافت نشد'}, status=400)

        delivery_file = ContentDeliveryFile.objects.get(
            id=delivery_file_id,
            delivery__order__campaign__advertiser=request.user.advertiser_profile,
            is_option=True
        )

        # ✅ چک کن که فایل وجود داره
        if not delivery_file.file:
            return JsonResponse({'error': 'فایل مورد نظر وجود ندارد'}, status=400)

        order = delivery_file.delivery.order
        campaign = order.campaign

        if order.status != 'done':
            return JsonResponse({'error': 'این سفارش قابل انتخاب نیست'}, status=400)

        # ========== ✅ ۱. ریست کردن انتخاب‌های قبلی ==========
        all_deliveries = ContentDelivery.objects.filter(order=order)
        for delivery in all_deliveries:
            for file_obj in delivery.files.all():
                if file_obj.is_selected:
                    file_obj.is_selected = False
                    file_obj.save(update_fields=['is_selected'])

        # ========== ✅ ۲. انتخاب فایل جدید ==========
        delivery_file.is_selected = True
        delivery_file.save(update_fields=['is_selected'])

        # ========== ۳. به‌روزرسانی محتوای کمپین ==========
        campaign_content, created = CampaignContent.objects.get_or_create(
            campaign=campaign,
            defaults={
                'media': delivery_file.file,
                'caption': f'گزینه {delivery_file.option_number} انتخاب شده',
                'notes': f'فایل تحویلی نسخه {delivery_file.delivery.version} - گزینه {delivery_file.option_number}'
            }
        )

        if not created:
            campaign_content.media = delivery_file.file
            campaign_content.notes = f'فایل تحویلی نسخه {delivery_file.delivery.version} - گزینه {delivery_file.option_number}'
            campaign_content.save(update_fields=['media', 'notes'])

        # ========== ۴. انجام عملیات تایید نهایی ==========
        content_cost = campaign.invoice.content_cost if hasattr(campaign, 'invoice') and campaign.invoice else 0

        if content_cost > 0:
            team_members = ContentTeamMember.objects.filter(
                team=order.team,
                is_active=True
            ).select_related('user')

            if team_members.exists():
                total_percent = sum(member.revenue_share_percent for member in team_members)

                if total_percent == 100:
                    from campaigns.services.campaigns_notifications import accept_content_order_delivery
                    accept_content_order_delivery(
                        order=order,
                        content_cost=content_cost,
                        team_members=team_members,
                        primary_delivery=delivery_file.delivery
                    )

        return JsonResponse({
            'success': True,
            'message': f'گزینه {delivery_file.option_number} با موفقیت انتخاب و سفارش تأیید شد.',
            'option_number': delivery_file.option_number,
            'is_final_accepted': True
        })

    except ContentDeliveryFile.DoesNotExist:
        return JsonResponse({'error': 'فایل مورد نظر یافت نشد'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


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
    ).order_by('-created_at')[:10]

    recent_campaigns = campaigns.order_by('-created_at')[:10]

    top_channels = InfluencerChannel.objects.filter(
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

        # فقط سفارشات done قابل ویرایش هستند
        if order.status != 'done':
            return JsonResponse({'error': 'این سفارش قابل ویرایش نیست'}, status=400)

        # ✅ چک کردن اینکه آیا فایلی انتخاب شده
        if order.has_selected_file():
            return JsonResponse({
                'error': 'شما قبلاً یک فایل را انتخاب کرده‌اید و سفارش نهایی شده است. امکان درخواست ویرایش وجود ندارد.'
            }, status=400)

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

        if order.status != 'done':
            return JsonResponse({'error': 'این سفارش قابل تأیید نیست'}, status=400)

        last_delivery = order.deliveries.first()
        if not last_delivery or last_delivery.status != 'delivered':
            return JsonResponse({'error': 'این سفارش قبلاً تأیید شده یا در وضعیت مناسبی نیست'}, status=400)

        content_cost = order.campaign.invoice.content_cost if hasattr(order.campaign,
                                                                      'invoice') and order.campaign.invoice else 0

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
            team_members=team_members,
            primary_delivery=last_delivery  # ✅ آخرین تحویل رو به عنوان primary می‌فرستیم
        )

        order.status = ContentOrder.Status.COMPLETED
        order.save(update_fields=['status'])

        return JsonResponse({
            'success': True,
            'message': f'سفارش با موفقیت تأیید شد!\n این فایل به عنوان فایل اصلی کمپین در نظر گرفته شد',
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
