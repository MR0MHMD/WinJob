from campaigns.models import Campaign, AdType, CampaignInfluencer, CampaignTrackingLink, Coupon
from django.db.models import Sum, Q, Value, IntegerField, FloatField, Avg, Count, Prefetch
from campaigns.services.campaigns_notifications import submit_influencer_report_service
from .models import InfluencerServiceRate, InfluencerChannel, InfluencerReview
from django.shortcuts import render, get_object_or_404, redirect
from .services.verification_service import VerificationService
from django.db.models.functions import TruncDate, Coalesce
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .api_views import trigger_n8n_verification
from datetime import timedelta, datetime, time
from django.db import IntegrityError, models
from django.core.paginator import Paginator
from .forms import InfluencerChannelForm
from accounts.models import Transaction
from plat_form.models import Platform
from location.models import Province
from django.contrib import messages
from django.utils import timezone
from core.models import Category
from django.conf import settings
from threading import Thread
import jdatetime
import json


@login_required
def influencer_channels_view(request, pk=None):
    """
    نمایش، افزودن و ویرایش کانال‌ها در یک صفحه (بدون AJAX)
    """
    if not hasattr(request.user, "influencer_profile"):
        messages.error(request, "دسترسی شما به این بخش مجاز نیست.")
        return redirect('home')  # یا هر مسیری که صلاح می‌دونی

    influencer = request.user.influencer_profile
    instance = None

    if pk:
        instance = get_object_or_404(InfluencerChannel, pk=pk, influencer=influencer)

    if request.method == "POST":
        form = InfluencerChannelForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            try:
                channel = form.save(commit=False)
                channel.influencer = influencer
                channel.save()

                if pk:
                    messages.success(request, f"کانال ({channel.channel_name}) با موفقیت ویرایش شد.")
                else:
                    messages.success(request, f"کانال ({channel.channel_name}) با موفقیت اضافه شد.")

                return redirect('influencers:influencer_channels')

            except IntegrityError:
                messages.error(request, "این پلتفرم و آیدی قبلاً ثبت شده است.")
        else:
            messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")
    else:
        form = InfluencerChannelForm(instance=instance)

    channels = influencer.channels.select_related("platform").all()

    return render(request, "influencers/pages/channels.html", {
        "form": form,
        "channels": channels,
        "edit_mode": pk is not None,
        "instance": instance
    })


@login_required
def delete_channel_view(request, pk):
    """حذف کانال و ریدایرکت به لیست"""
    if request.method == "POST":
        channel = get_object_or_404(InfluencerChannel, pk=pk, influencer__user=request.user)
        name = channel.channel_name
        channel.delete()
        messages.success(request, f"کانال {name} با موفقیت حذف شد.")

    return redirect('influencers:influencer_channels')


@login_required
def service_rates_view(request):
    """مدیریت تعرفه‌های خدمات - نمایش کارت‌بندی"""
    try:
        influencer = request.user.influencer_profile
    except:
        messages.error(request, 'پروفایل اینفلوئنسر یافت نشد')
        return redirect('influencers:dashboard')

    existing_rates = InfluencerServiceRate.objects.filter(
        channel__influencer=influencer
    ).select_related('channel', 'ad_type')

    rates_map = {
        (r.channel_id, r.ad_type_id): r
        for r in existing_rates
    }

    channels_data = []
    active_channels = influencer.channels.filter(is_active=True).select_related('platform')

    for channel in active_channels:
        ad_types = AdType.objects.filter(platform=channel.platform)
        rows = []
        for ad_type in ad_types:
            rate = rates_map.get((channel.id, ad_type.id))
            rows.append({
                'ad_type': ad_type,
                'rate': rate,
                'channel_status': channel.status,
            })
        channels_data.append({
            'channel': channel,
            'rows': rows,
        })

    for item in channels_data:
        filled = sum(1 for row in item['rows'] if row['rate'] is not None)
        total = len(item['rows'])
        item['filled_count'] = filled
        item['fill_percent'] = round((filled / total) * 100) if total > 0 else 0

    context = {
        'channels_data': channels_data,
    }
    return render(request, 'influencers/pages/service_rates.html', context)


@login_required
def order_list(request):
    user = request.user
    if not hasattr(user, "influencer_profile"):
        orders = CampaignInfluencer.objects.none()
    else:
        influencer = user.influencer_profile
        orders = CampaignInfluencer.objects.select_related(
            "campaign",
            "channel",
            "campaign__content",
            "service_rate",
            "campaign__advertiser",
        ).filter(channel__influencer=influencer).exclude(
            campaign__status__in=[Campaign.Status.DRAFT, Campaign.Status.PENDING]
        ).filter(
            Q(campaign__content_type__slug__isnull=True) |
            ~Q(campaign__content_type__slug='content-production-team') |
            Q(campaign__content_orders__delivery__status='final_accepted')
        ).distinct()

        # ========== فیلترها ==========
        # فیلتر بر اساس نام کمپین
        q = request.GET.get('q')
        if q:
            orders = orders.filter(campaign__name__icontains=q)

        # فیلتر بر اساس پلتفرم
        platform_slug = request.GET.get('platform')
        if platform_slug:
            orders = orders.filter(channel__platform__slug=platform_slug)

        # فیلتر بر اساس رایگان بودن
        free_filter = request.GET.get('free')
        if free_filter == 'yes':
            orders = orders.filter(campaign__is_free=True)
        elif free_filter == 'no':
            orders = orders.filter(campaign__is_free=False)

        # فیلتر بر اساس وضعیت سفارش
        status_filter = request.GET.get('status')
        if status_filter in ['pending', 'accepted', 'completed', 'rejected']:
            orders = orders.filter(status=status_filter)

        # ========== مرتب‌سازی ==========
        sort_by = request.GET.get('sort')
        if sort_by == 'oldest':
            orders = orders.order_by('created_at')
        else:  # پیش‌فرض جدیدترین
            orders = orders.order_by('-created_at')

    # صفحه‌بندی
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)

    context = {
        'orders': orders,
        'filter_q': request.GET.get('q', ''),
        'filter_platform': request.GET.get('platform', ''),
        'filter_free': request.GET.get('free', ''),
        'filter_status': request.GET.get('status', ''),
        'filter_sort': request.GET.get('sort', 'newest'),
        'platforms': Platform.objects.filter(is_active=True),
    }
    return render(request, 'influencers/pages/orders_list.html', context)


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        CampaignInfluencer.objects
        .select_related(
            "campaign",
            "campaign__platform",
            "campaign__content_type",
            "campaign__ad_type",
            "campaign__advertiser",
            "campaign__advertiser__category",
            "campaign__influencer_coupon",
            "campaign__content_team_coupon",
            "campaign__platform_coupon",
            "campaign__content",
            "channel",
            "channel__platform",
            "channel__category",
            "channel__province",
            "channel__influencer",
            "channel__influencer__user",
            "service_rate",
            "service_rate__ad_type",
            "tracking_link",
        )
        .prefetch_related(
            "channel__service_rates",
            "tracking_link__click_logs",
        ),
        id=order_id
    )

    if request.user != order.channel.influencer.user:
        raise PermissionDenied("شما دسترسی به این صفحه ندارید.")

    if not order.is_seen:
        order.is_seen = True
        order.save(update_fields=["is_seen"])

    campaign = order.campaign
    channel = order.channel
    advertiser = campaign.advertiser
    content = campaign.content

    try:
        tracking_link = order.tracking_link
        clicks = tracking_link.clicks
        unique_clicks = tracking_link.unique_clicks
    except CampaignTrackingLink.DoesNotExist:
        clicks = None
        unique_clicks = None

    utm_link = None
    if content and content.utm_enabled and content.link:
        utm_link = content.get_utm_link(order)

    other_orders = CampaignInfluencer.objects.filter(
        channel=channel
    ).exclude(
        id=order.id
    ).select_related(
        'campaign'
    )[:5]

    target_timestamp = None
    if order.status == 'accepted' and not hasattr(order, 'report'):
        # تبدیل تاریخ جلالی به میلادی (به دست آوردن datetime.date معمولی)
        gregorian_date = campaign.start_date.togregorian()
        # ترکیب با ساعت 00:00:00
        start_datetime = datetime.combine(gregorian_date, time.min)
        # منطقه‌دار کردن با زمان تهران
        start_datetime = timezone.make_aware(start_datetime, timezone.get_current_timezone())
        # تایم‌استمپ بر حسب ثانیه (نه میلی‌ثانیه)
        target_timestamp = int(start_datetime.timestamp())

    context = {
        "order": order,
        "campaign": campaign,
        "advertiser": advertiser,
        "channel": channel,
        "content": content,
        "service_rate": order.service_rate,
        "utm_link": utm_link,
        "clicks": clicks,
        "unique_clicks": unique_clicks,
        "now": timezone.now(),
        "other_orders_of_influencer": other_orders,
        "channel_rates": channel.service_rates.filter(is_active=True),
        "start_date": campaign.start_date,
        "end_date": campaign.end_date,
        "status": order.status,
        "campaign_status": campaign.status,
        "target_timestamp": target_timestamp,
        "is_campaign_editable": campaign.is_editable,
        "channel_location": channel.get_full_location() if hasattr(channel, "get_full_location") else None,
        "advertiser_location": advertiser.get_full_location() if hasattr(advertiser, "get_full_location") else None,
    }

    return render(request, "influencers/pages/order_detail.html", context)


@login_required
def influencer_respond(request, order_id):
    """
    ویو برای قبول یا رد سفارش توسط اینفلوئنسر
    """
    order = get_object_or_404(
        CampaignInfluencer.objects.select_related(
            'channel__influencer__user',
            'campaign'
        ),
        id=order_id
    )

    if request.user != order.channel.influencer.user:
        messages.error(request, "شما دسترسی به این عملیات ندارید.")
        return redirect('influencers:order_detail', order_id=order.id)

    if order.status != 'pending':
        messages.error(request, "این سفارش قبلاً پاسخ داده شده است و قابل تغییر نیست.")
        return redirect('influencers:order_detail', order_id=order.id)

    action = request.POST.get('action')

    if action in ['accept', 'reject']:
        from campaigns.services.campaigns_notifications import respond_to_influencer_order_service
        respond_to_influencer_order_service(order, action)

        if action == 'accept':
            messages.success(request, "🎉 سفارش با موفقیت پذیرفته شد. منتظر جزئیات بیشتر از سمت تبلیغ‌دهنده باشید.")
        else:
            # ========== پیام اختصاصی برای رد ==========
            if order.campaign.is_free:
                messages.info(request, "❌ سفارش کمپین خیریه رد شد. امتیازی کسر نشد.")
            else:
                messages.success(request, "❌ سفارش رد شد. مبلغ مربوطه به کیف پول تبلیغ‌دهنده برگشت داده شد.")
    else:
        messages.error(request, "عملیات نامعتبر است.")
        return redirect('influencers:order_detail', order_id=order.id)

    return redirect('influencers:order_detail', order_id=order.id)



@login_required
def submit_report(request, order_id):
    order = get_object_or_404(
        CampaignInfluencer.objects.select_related(
            'campaign',
            'channel__influencer__user',
            'campaign__advertiser'
        ),
        id=order_id
    )

    if request.user != order.channel.influencer.user:
        raise PermissionDenied("شما دسترسی به این صفحه ندارید.")

    if order.status != CampaignInfluencer.Status.ACCEPTED:
        messages.error(request, "فقط سفارش‌های پذیرفته شده قابلیت گزارش دارند.")
        return redirect('influencers:order_detail', order_id=order.id)

    if hasattr(order, 'report'):
        messages.error(request, "شما قبلاً گزارش خود را ثبت کرده‌اید.")
        return redirect('influencers:order_detail', order_id=order.id)

    campaign = order.campaign
    now = timezone.now()

    if campaign.status == Campaign.Status.COMPLETED:
        messages.error(request, "این کمپین به پایان رسیده و دیگر قابلیت ثبت گزارش ندارد.")
        return redirect('influencers:order_detail', order_id=order.id)

    # بررسی زمان شروع
    gregorian_date = campaign.start_date.togregorian()
    start_datetime = datetime.combine(gregorian_date, time.min)
    start_datetime = timezone.make_aware(start_datetime, timezone.get_current_timezone())

    if now < start_datetime:
        messages.error(request,
                       f"امکان ثبت گزارش از ساعت ۰۰:۰۰ روز {campaign.start_date.strftime('%Y/%m/%d')} فراهم می‌شود.")
        return redirect('influencers:order_detail', order_id=order.id)

    if request.method == 'POST':
        post_link = request.POST.get('post_link')
        screenshot = request.FILES.get('screenshot')

        if not post_link or not screenshot:
            messages.error(request, "لطفاً تمام فیلدها را پر کنید.")
            return redirect('influencers:submit_report', order_id=order.id)

        # ۱. در هر دو حالت گزارش باید در دیتابیس ثبت بشه
        submit_influencer_report_service(order, post_link, screenshot)

        # ۲. بررسی فلگ ستینگ برای استفاده از اتوماسیون n8n
        if getattr(settings, 'USE_N8N_VERIFICATION', False):
            # گرفتن گزارش ثبت شده
            report = order.report

            # گرفتن متن مورد انتظار (کپشن کمپین)
            expected_caption = ""
            if hasattr(campaign, 'content') and campaign.content:
                expected_caption = campaign.content.caption or ""

            # اضافه کردن لینک ردیابی به انتهای متن انتظاری
            tracking_link = order.uniq_url() or ""
            if tracking_link:
                expected_caption = expected_caption.rstrip() + "\r\n\r\n" + tracking_link

            # لینک ردیابی اختصاصی اینفلوئنسر
            tracking_link = order.uniq_url() or ""

            # تریگر n8n در ترد جداگانه (به همراه اسلاگ پلتفرم که اضافه کرده بودیم)
            Thread(
                target=trigger_n8n_verification,
                args=(
                    report.id,
                    post_link,
                    expected_caption,
                    tracking_link,
                    order.channel.platform.slug
                ),
                daemon=True
            ).start()

            messages.success(request, "گزارش شما با موفقیت ثبت شد. در حال بررسی خودکار، نتیجه به زودی اعلام می‌شود.")
        else:
            # ۳. فلو قدیمی: بررسی دستی توسط ادمین
            messages.success(request, "گزارش شما با موفقیت ثبت شد و در انتظار بررسی توسط مدیریت است.")

        return redirect('influencers:order_detail', order_id=order.id)

    else:
        context = {
            'order': order,
            'campaign': campaign,
            'advertiser': campaign.advertiser,
            'channel': order.channel,
            'can_submit': True,
        }
        return render(request, "influencers/forms/submit_report.html", context)


@login_required
def influencer_dashboard(request):
    if not hasattr(request.user, 'influencer_profile'):
        messages.error(request, "شما دسترسی به این صفحه ندارید.")
        return redirect('core:home')

    influencer = request.user.influencer_profile

    channels = InfluencerChannel.objects.filter(influencer=influencer, is_active=True)
    channel_ids = channels.values_list('id', flat=True)
    channels_count = channels.count()

    campaign_bookings = CampaignInfluencer.objects.filter(
        channel_id__in=channel_ids
    ).exclude(
        campaign__status__in=[Campaign.Status.DRAFT, Campaign.Status.PENDING]
    ).filter(
        Q(campaign__content_type__slug__isnull=True) |
        ~Q(campaign__content_type__slug='content-production-team') |
        Q(campaign__content_orders__delivery__status='final_accepted')
    ).distinct()

    booking_ids = campaign_bookings.values_list('id', flat=True)

    total_bookings = campaign_bookings.count()
    pending_bookings = campaign_bookings.filter(status='pending').count()
    accepted_bookings = campaign_bookings.filter(status='accepted').count()
    completed_bookings = campaign_bookings.filter(status='completed').count()

    total_earned = campaign_bookings.filter(
        status='completed'
    ).aggregate(total=Sum('price'))['total'] or 0

    pending_earnings = campaign_bookings.filter(
        status__in=['accepted', 'pending']
    ).aggregate(total=Sum('price'))['total'] or 0

    wallet = request.user.wallet
    wallet_balance = wallet.balance

    # گرفتن ۳ کد تخفیف آخر اینفلوئنسر
    latest_coupons = Coupon.objects.filter(
        channel__influencer=influencer,
        is_active=True
    ).order_by('-id')[:3]

    tracking_links = CampaignTrackingLink.objects.filter(
        campaign_influencer_id__in=booking_ids
    )
    total_clicks = tracking_links.aggregate(total=Sum('clicks'))['total'] or 0
    total_unique_clicks = tracking_links.aggregate(total=Sum('unique_clicks'))['total'] or 0

    total_followers = channels.aggregate(total=Sum('followers_count'))['total'] or 1
    avg_ctr = round((total_clicks / total_followers) * 100, 2) if total_followers > 0 else 0

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

    daily_earnings = campaign_bookings.filter(
        status='completed',
        created_at__gte=last_30_days
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        total=Sum('price')
    ).order_by('day')

    daily_earnings_labels = []
    daily_earnings_data = []

    for item in daily_earnings:
        if item['day']:
            daily_earnings_labels.append(item['day'].strftime('%d/%m'))
            daily_earnings_data.append(float(item['total']) if item['total'] else 0)

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]

    recent_bookings = campaign_bookings.select_related(
        'campaign', 'channel'
    ).filter(campaign__status="approved").order_by('-created_at')[:5]

    active_orders = campaign_bookings.filter(
        status='accepted'
    ).select_related('campaign', 'channel')[:5]

    channels_data = []
    total_filled_rates = 0
    total_possible_rates = 0

    for channel in channels:
        if channel.status != 'approved':
            continue

        ad_types_for_channel = AdType.objects.filter(
            is_active=True,
            platform=channel.platform
        )
        total_ad_types_count = ad_types_for_channel.count()

        existing_rates = InfluencerServiceRate.objects.filter(
            channel=channel,
            ad_type__is_active=True,
            ad_type__platform=channel.platform
        )

        rows = []
        filled_count = 0

        for ad_type in ad_types_for_channel:
            rate = existing_rates.filter(ad_type=ad_type).first()
            if rate and rate.price is not None:
                filled_count += 1
                total_filled_rates += 1
            rows.append({
                'ad_type': ad_type,
                'rate': rate,
            })
            total_possible_rates += 1

        fill_percent = round((filled_count / total_ad_types_count) * 100) if total_ad_types_count > 0 else 0

        channels_data.append({
            'channel': channel,
            'rows': rows,
            'filled_count': filled_count,
            'fill_percent': fill_percent,
            'total_ad_types': total_ad_types_count,
        })

    global_fill_percent = round((total_filled_rates / total_possible_rates) * 100) if total_possible_rates > 0 else 0

    channels_without_rates = []
    for item in channels_data:
        channel = item['channel']
        if channel.status == 'approved' and item['filled_count'] == 0:
            channels_without_rates.append(channel)

    channels_without_rates_count = len(channels_without_rates)
    first_channel_without_rate = channels_without_rates[0] if channels_without_rates else None

    # ========== سفارشات در حال انجام که زمان گزارششان رسیده ==========
    today_gregorian = timezone.now().date()

    orders_missing_report = campaign_bookings.filter(
        status='accepted',
        report__isnull=True
    ).select_related('campaign').order_by('campaign__start_date')

    orders_due_for_report = []
    for booking in orders_missing_report:
        start_date = booking.campaign.start_date

        start_date_gregorian = start_date.togregorian()
        if start_date_gregorian <= today_gregorian:
            orders_due_for_report.append(booking)

    orders_due_for_report_count = len(orders_due_for_report)

    pending_report_orders = orders_due_for_report[:5]

    free_orders = campaign_bookings.filter(campaign__is_free=True)
    free_total_orders = free_orders.count()
    free_pending_orders = free_orders.filter(status='pending').count()
    free_completed_orders = free_orders.filter(status='completed').count()

    # ========== میانگین امتیازات گیمیفیکیشن کانال‌ها ==========
    from gamification.models import Badge  # اضافه کردن import در ابتدای فایل

    total_points = 0
    active_channels_count = 0

    for channel in channels:
        if channel.status == 'approved' and channel.is_active:
            # دریافت امتیاز کانال (در صورت وجود)
            if hasattr(channel, 'score') and channel.score:
                points = channel.score.points
            else:
                points = 0
            total_points += points
            active_channels_count += 1

    avg_points = total_points // active_channels_count if active_channels_count > 0 else 0

    # پیدا کردن نشان متناسب با میانگین امتیاز
    badges = Badge.objects.filter(is_active=True).order_by('min_points')
    current_badge = None
    next_badge = None

    if badges.exists():
        # نشان فعلی: بزرگترین min_points که کمتر یا مساوی avg_points باشد
        for badge in badges:
            if badge.min_points <= avg_points:
                current_badge = badge
            else:
                next_badge = badge
                break
        # اگر همه نشان‌ها کوچک‌تر بودند (به آخر رسیدیم)
        if next_badge is None and current_badge:
            # در بالاترین سطح هستیم
            pass
    else:
        # اگر هیچ نشان فعالی وجود نداشت، یک نشان پیش‌فرض
        current_badge = None

    # محاسبه درصد پیشرفت به سمت نشان بعدی
    progress_percent = 0
    points_needed = 0
    is_max_level = False

    if current_badge and next_badge:
        points_for_current = current_badge.min_points
        points_for_next = next_badge.min_points
        range_size = points_for_next - points_for_current
        if range_size > 0:
            progress = avg_points - points_for_current
            progress_percent = (progress / range_size) * 100
        points_needed = points_for_next - avg_points
    elif current_badge and not next_badge:
        is_max_level = True
        progress_percent = 100
    else:
        # اگر هیچ نشان فعلی نبود (امتیاز کمتر از پایین‌ترین نشان)
        if badges.exists():
            first_badge = badges.first()
            points_needed = first_badge.min_points - avg_points
            progress_percent = (avg_points / first_badge.min_points) * 100 if first_badge.min_points > 0 else 0
            current_badge = None
            next_badge = first_badge
        else:
            points_needed = 0
            progress_percent = 0

    # ساخت دیکشنری اطلاعات گیمیفیکیشن برای قالب
    gamification_data = {
        'current_points': avg_points,
        'current_badge_name': current_badge.name if current_badge else 'بدون سطح',
        'current_badge_icon': current_badge.icon.url if current_badge and current_badge.icon else None,
        'current_badge_code': current_badge.slug if current_badge else None,
        'next_badge_name': next_badge.name if next_badge else 'بالاترین سطح',
        'points_needed_for_next': points_needed,
        'progress_percent': round(progress_percent, 2),
        'is_max_level': is_max_level,
        'active_channels_count': active_channels_count,
    }

    context = {
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'accepted_bookings': accepted_bookings,
        'completed_bookings': completed_bookings,
        'total_earned': total_earned,
        'pending_earnings': pending_earnings,
        'wallet_balance': wallet_balance,
        'latest_coupons': latest_coupons,
        'total_clicks': total_clicks,
        'total_unique_clicks': total_unique_clicks,
        'avg_ctr': avg_ctr,
        'persian_date': persian_date,
        'daily_earnings_labels_json': json.dumps(daily_earnings_labels, ensure_ascii=False),
        'daily_earnings_data_json': json.dumps(daily_earnings_data, ensure_ascii=False),
        'recent_transactions': recent_transactions,
        'recent_bookings': recent_bookings,
        'active_orders': active_orders,
        'influencer': influencer,
        'channels': channels,
        'channels_count': channels_count,
        'channels_data': channels_data,
        'global_fill_percent': global_fill_percent,
        'total_filled_rates': total_filled_rates,
        'total_possible_rates': total_possible_rates,
        'channels_without_rates_count': channels_without_rates_count,
        'first_channel_without_rate': first_channel_without_rate,
        'pending_report_orders': pending_report_orders,
        'orders_due_for_report_count': orders_due_for_report_count,
        'orders_due_for_report': orders_due_for_report[:5],
        'has_missing_report': orders_due_for_report_count > 0,
        'free_total_orders': free_total_orders,
        'free_pending_orders': free_pending_orders,
        'free_completed_orders': free_completed_orders,
        'gamification': gamification_data,
    }

    return render(request, "influencers/pages/dashboard.html", context)


def channel_list(request):
    """
    صفحه لیست کانال‌های اینفلوئنسرها با فیلتر حرفه‌ای
    """

    # کوئری اصلی - اصلاح شده با output_field
    channels = InfluencerChannel.objects.filter(
        is_active=True,
        status="approved",
        influencer__is_active=True
    ).select_related(
        'platform',
        'province',
        'category',
        'influencer'
    ).prefetch_related(
        'service_rates',
        'service_rates__ad_type',
    ).annotate(
        # میانگین امتیاز - از reviews خود channel (نه influencer)
        _avg_rating=Coalesce(
            Avg('reviews__rating', output_field=FloatField()),
            Value(0.0, output_field=FloatField())
        ),
        # تعداد نظرات
        total_reviews=Count('reviews'),
        # حداقل قیمت
        min_price=Coalesce(
            models.Min('service_rates__price', output_field=IntegerField()),
            Value(0, output_field=IntegerField())
        )
    )

    # ========== فیلترها ==========

    # فیلتر بر اساس پلتفرم
    platform_slug = request.GET.get('platform')
    if platform_slug:
        channels = channels.filter(platform__slug=platform_slug)

    # فیلتر بر اساس استان
    province_id = request.GET.get('province')
    if province_id:
        channels = channels.filter(province_id=province_id)

    # فیلتر بر اساس دسته‌بندی محتوایی
    category_id = request.GET.get('category')
    if category_id:
        channels = channels.filter(category_id=category_id)

    # فیلتر بر اساس محدوده فالوور
    followers_min = request.GET.get('followers_min')
    followers_max = request.GET.get('followers_max')
    if followers_min and followers_min.isdigit():
        channels = channels.filter(followers_count__gte=int(followers_min))
    if followers_max and followers_max.isdigit():
        channels = channels.filter(followers_count__lte=int(followers_max))

    # فیلتر بر اساس نوع تبلیغ
    ad_type_slug = request.GET.get('ad_type')
    if ad_type_slug:
        channels = channels.filter(
            service_rates__ad_type__slug=ad_type_slug,
            service_rates__is_active=True
        )

    # فیلتر بر اساس محدوده قیمت
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    if price_min and price_min.isdigit():
        channels = channels.filter(service_rates__price__gte=int(price_min))
    if price_max and price_max.isdigit():
        channels = channels.filter(service_rates__price__lte=int(price_max))

    # فیلتر بر اساس امتیاز (حداقل ۴ ستاره)
    min_rating = request.GET.get('min_rating')
    if min_rating and min_rating.isdigit():
        channels = channels.filter(influencer__reviews__rating__gte=int(min_rating))

    # فیلتر جستجوی متن
    search_query = request.GET.get('q')
    if search_query:
        channels = channels.filter(
            Q(channel_name__icontains=search_query) |
            Q(channel_id__icontains=search_query) |
            Q(influencer__full_name__icontains=search_query)
        )

    # ========== مرتب‌سازی ==========
    sort_by = request.GET.get('sort', '-followers_count')
    valid_sorts = {
        'followers_count': 'followers_count',
        '-followers_count': '-followers_count',
        'min_price': 'min_price',
        '-min_price': '-min_price',
        'avg_rating': 'avg_rating',
        '-avg_rating': '-avg_rating',
        'created_at': '-created_at',
    }
    sort_by = valid_sorts.get(sort_by, '-followers_count')
    channels = channels.order_by(sort_by).distinct()

    # ========== دیتا برای فیلترها (نمایش در سایدبار) ==========
    platforms = Platform.objects.filter(
        is_active=True,
        influencer_channels__is_active=True
    ).distinct()

    provinces = Province.objects.filter(
        influencers__is_active=True
    ).distinct()

    categories = Category.objects.filter(
        influencer_channel__is_active=True
    ).distinct()

    ad_types = AdType.objects.filter(
        is_active=True,
        influencer_rates__is_active=True
    ).distinct()

    # محدوده فالوور برای اسلایدر
    from django.db.models import Max, Min
    followers_range = InfluencerChannel.objects.filter(
        is_active=True
    ).aggregate(
        min_followers=Min('followers_count'),
        max_followers=Max('followers_count')
    )

    # ========== صفحه‌بندی ==========
    paginator = Paginator(channels, 21)
    page_number = request.GET.get('page')
    channels = paginator.get_page(page_number)

    context = {
        'channels': channels,
        'platforms': platforms,
        'provinces': provinces,
        'categories': categories,
        'ad_types': ad_types,
        'followers_range': followers_range,
        'selected_filters': {
            'platform': platform_slug,
            'province': province_id,
            'category': category_id,
            'followers_min': followers_min,
            'followers_max': followers_max,
            'ad_type': ad_type_slug,
            'price_min': price_min,
            'price_max': price_max,
            'min_rating': min_rating,
            'sort': sort_by,
            'q': search_query,
        }
    }

    return render(request, 'influencers/pages/channel_list.html', context)


def channel_detail(request, channel_id):
    channel = get_object_or_404(
        InfluencerChannel.objects.select_related(
            'platform', 'province', 'category', 'influencer'
        ).prefetch_related(
            'service_rates__ad_type',
            Prefetch(
                'reviews',
                queryset=InfluencerReview.objects.select_related(
                    'advertiser__user'
                ).order_by('-created_at')
            )
        ).annotate(
            _avg_rating=Avg('reviews__rating'),
            _total_reviews=Count('reviews'),
            _completed_campaigns=Count(
                'campaign_bookings',
                filter=Q(campaign_bookings__status='completed')
            )
        ),
        id=channel_id,
        is_active=True,
        influencer__is_active=True
    )

    cooldown_active = False
    cooldown_hours = 0
    if channel.status == 'rejected' and channel.rejected_at:
        cooldown_active = VerificationService.is_cooldown_active(channel)
        cooldown_hours = VerificationService.get_cooldown_remaining(channel)

    select_rate_param = request.GET.get('select_rate')
    from_campaign = select_rate_param is not None
    selectable_rate_id = int(select_rate_param) if select_rate_param and select_rate_param.isdigit() else None

    # influencers/views.py (قسمت منطق ثبت نظر)
    # ========== منطق ثبت نظر ==========
    can_submit_review = False
    pending_bookings = []

    if request.user.is_authenticated and hasattr(request.user, 'advertiser_profile'):
        advertiser = request.user.advertiser_profile

        # ۱. کمپین‌های تکمیل شده بدون نظر
        pending_bookings = list(CampaignInfluencer.objects.filter(
            campaign__advertiser=advertiser,
            channel=channel,
            status=CampaignInfluencer.Status.COMPLETED,
            review__isnull=True
        ).select_related('campaign').order_by('-created_at'))

        # ۲. بررسی آیا کاربر قبلاً نظری (حتی عمومی) ثبت کرده؟
        has_any_review = InfluencerReview.objects.filter(
            channel=channel,
            advertiser=advertiser
        ).exists()

        if not has_any_review:
            # کاربر هیچ نظری ندارد → می‌تواند یک نظر عمومی ثبت کند
            can_submit_review = True
        elif pending_bookings:
            # کاربر نظر دارد ولی کمپین بدون نظر وجود دارد
            can_submit_review = True

    # مرتب‌سازی نظرات: نظر کاربر فعلی اول، سپس بقیه بر اساس تاریخ نزولی
    all_reviews = list(channel.reviews.all())
    if request.user.is_authenticated and hasattr(request.user, 'advertiser_profile'):
        user_reviews = [r for r in all_reviews if r.advertiser.user == request.user]
        other_reviews = [r for r in all_reviews if r.advertiser.user != request.user]
        # مرتب کردن سایر نظرات بر اساس تاریخ (جدیدترین اول)
        other_reviews_sorted = sorted(other_reviews, key=lambda x: x.created_at, reverse=True)
        sorted_reviews = user_reviews + other_reviews_sorted
    else:
        sorted_reviews = sorted(all_reviews, key=lambda x: x.created_at, reverse=True)

    context = {
        'channel': channel,
        'avg_rating': channel.avg_rating,
        'total_reviews': channel._total_reviews,
        'completed_campaigns': channel._completed_campaigns,
        'service_rates': channel.service_rates.filter(is_active=True),
        'reviews': sorted_reviews,  # نظرات مرتب شده
        'gamification': channel.gamification_status,
        'from_campaign': from_campaign,
        'selectable_rate_id': selectable_rate_id,
        'can_submit_review': can_submit_review,
        'pending_bookings': pending_bookings,
        'use_n8n': settings.USE_N8N_VERIFICATION,
        'cooldown_active': cooldown_active,
        'cooldown_hours': cooldown_hours,
    }

    return render(request, 'influencers/pages/channel_detail.html', context)


@login_required
def influencer_coupons(request):
    """نمایش و مدیریت کدهای تخفیف ناشر"""
    if not hasattr(request.user, 'influencer_profile'):
        messages.error(request, "شما دسترسی به این صفحه ندارید.")
        return redirect('core:home')

    influencer = request.user.influencer_profile

    # گرفتن کانال‌های فعال ناشر
    channels = InfluencerChannel.objects.filter(
        influencer=influencer,
        is_active=True
    )

    # گرفتن همه کدهای تخفیف این ناشر (از طریق کانال‌هاش)
    coupons = Coupon.objects.filter(
        channel__influencer=influencer
    ).select_related('channel', 'channel__platform').order_by('-id')

    # آمار
    total_coupons = coupons.count()
    active_coupons = coupons.filter(is_active=True).count()
    total_used = coupons.aggregate(total=models.Sum('used_count'))['total'] or 0

    # فیلتر پیشرفته
    channel_id = request.GET.get('channel')
    status = request.GET.get('status')
    used_min = request.GET.get('used_min')
    used_max = request.GET.get('used_max')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if channel_id:
        coupons = coupons.filter(channel_id=channel_id)

    if status == 'active':
        coupons = coupons.filter(is_active=True)
    elif status == 'inactive':
        coupons = coupons.filter(is_active=False)

    if used_min:
        coupons = coupons.filter(used_count__gte=int(used_min))

    if used_max:
        coupons = coupons.filter(used_count__lte=int(used_max))

    if date_from:
        try:
            parts = date_from.split('/')
            jd = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            gd = jd.togregorian()
            coupons = coupons.filter(expires_at__gte=gd)
        except:
            pass

    if date_to:
        try:
            parts = date_to.split('/')
            jd = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            gd = jd.togregorian()
            coupons = coupons.filter(expires_at__lte=gd)
        except:
            pass

    context = {
        'coupons': coupons,
        'channels': channels,
        'total_coupons': total_coupons,
        'active_coupons': active_coupons,
        'total_used': total_used,
        'influencer': influencer,
    }

    return render(request, 'influencers/forms/coupons.html', context)


@login_required
def coupon_create(request):
    """ساخت کد تخفیف جدید"""
    if request.method != 'POST':
        return redirect('influencers:coupon_list')

    if not hasattr(request.user, 'influencer_profile'):
        messages.error(request, "شما دسترسی به این صفحه ندارید.")
        return redirect('core:home')

    code = request.POST.get('code', '').strip().upper()
    scope = 'influencer'
    discount_type = request.POST.get('discount_type')
    value = request.POST.get('value', '0')
    value = value.replace(',', '')
    channel_id = request.POST.get('channel')
    max_uses = request.POST.get('max_uses')
    expires_at = request.POST.get('expires_at')

    # اعتبارسنجی
    if not all([code, scope, discount_type, value, channel_id]):
        messages.error(request, "لطفاً تمام فیلدهای ضروری را پر کنید.")
        return redirect('influencers:coupon_list')

    # چک کردن تکراری نبودن کد
    if Coupon.objects.filter(code=code).exists():
        messages.error(request, "این کد تخفیف قبلاً استفاده شده است.")
        return redirect('influencers:coupon_list')

    # چک کردن مالکیت کانال
    try:
        channel = InfluencerChannel.objects.get(
            id=channel_id,
            influencer=request.user.influencer_profile,
            is_active=True
        )
    except InfluencerChannel.DoesNotExist:
        messages.error(request, "کانال انتخاب شده معتبر نیست.")
        return redirect('influencers:coupon_list')

    # ساخت کد تخفیف
    coupon = Coupon(
        code=code,
        scope=scope,
        channel=channel,
        discount_type=discount_type,
        value=value,
        max_uses=int(max_uses) if max_uses else None,
        is_active=True
    )

    # تاریخ انقضا
    # تاریخ انقضا
    expires_date = request.POST.get('expires_date', '').strip()
    expires_time = request.POST.get('expires_time', '00:00').strip()

    if expires_date:
        try:
            import jdatetime
            from datetime import datetime as dt

            # پارس تاریخ شمسی: 1405/02/06
            date_parts = expires_date.split('/')
            time_parts = expires_time.split(':') if expires_time else ['00', '00']

            jyear = int(date_parts[0])
            jmonth = int(date_parts[1])
            jday = int(date_parts[2])
            hour = int(time_parts[0]) if time_parts else 0
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            # تبدیل به میلادی با jdatetime
            jalali_date = jdatetime.date(jyear, jmonth, jday)
            gregorian_date = jalali_date.togregorian()

            expires_at = dt.combine(gregorian_date, dt.min.time())
            expires_at = expires_at.replace(hour=hour, minute=minute)

            coupon.expires_at = expires_at

        except (ValueError, IndexError, Exception) as e:
            messages.error(request, "فرمت تاریخ نامعتبر است. لطفاً به صورت ۱۴۰۵/۰۲/۰۶ وارد کنید.")
            return redirect('influencers:coupon_list')

    coupon.save()

    messages.success(request, f"کد تخفیف {code} با موفقیت ساخته شد! 🎉")
    return redirect('influencers:coupon_list')


@login_required
def coupon_edit(request, coupon_id):
    """ویرایش کد تخفیف"""
    if request.method != 'POST':
        return redirect('influencers:coupon_list')

    if not hasattr(request.user, 'influencer_profile'):
        messages.error(request, "شما دسترسی ندارید.")
        return redirect('core:home')

    influencer = request.user.influencer_profile

    # پیدا کردن کد تخفیف
    coupon = get_object_or_404(Coupon, id=coupon_id, channel__influencer=influencer)

    # دریافت داده‌ها
    code = request.POST.get('code', '').strip().upper()
    discount_type = request.POST.get('discount_type')
    value = request.POST.get('value', '0')
    value = value.replace(',', '')
    channel_id = request.POST.get('channel')
    max_uses = request.POST.get('max_uses')
    is_active = request.POST.get('is_active') == 'on'
    expires_date = request.POST.get('expires_date', '').strip()
    expires_time = request.POST.get('expires_time', '00:00').strip()

    # اعتبارسنجی
    if not all([code, discount_type, value, channel_id]):
        messages.error(request, "لطفاً تمام فیلدهای ضروری را پر کنید.")
        return redirect('influencers:coupon_list')

    # چک کردن تکراری نبودن کد (به جز خودش)
    if Coupon.objects.filter(code=code).exclude(id=coupon_id).exists():
        messages.error(request, "این کد تخفیف قبلاً استفاده شده است.")
        return redirect('influencers:coupon_list')

    # چک کردن مالکیت کانال
    try:
        channel = InfluencerChannel.objects.get(
            id=channel_id,
            influencer=influencer,
            is_active=True
        )
    except InfluencerChannel.DoesNotExist:
        messages.error(request, "کانال انتخاب شده معتبر نیست.")
        return redirect('influencers:coupon_list')

    # آپدیت فیلدها
    coupon.code = code
    coupon.discount_type = discount_type
    coupon.value = value
    coupon.channel = channel
    coupon.max_uses = int(max_uses) if max_uses else None
    coupon.is_active = is_active

    # مدیریت تاریخ
    if expires_date:
        try:
            import jdatetime
            from datetime import datetime as dt

            date_parts = expires_date.split('/')
            time_parts = expires_time.split(':') if expires_time else ['00', '00']

            jyear, jmonth, jday = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            hour = int(time_parts[0]) if time_parts else 0
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            jalali_date = jdatetime.date(jyear, jmonth, jday)
            gregorian_date = jalali_date.togregorian()

            expires_at = dt.combine(gregorian_date, dt.min.time())
            expires_at = expires_at.replace(hour=hour, minute=minute)

            coupon.expires_at = expires_at
        except:
            messages.error(request, "فرمت تاریخ نامعتبر است.")
            return redirect('influencers:coupon_list')
    else:
        coupon.expires_at = None

    coupon.save()
    messages.success(request, f"کد تخفیف {code} با موفقیت ویرایش شد! ✏️")
    return redirect('influencers:coupon_list')


@login_required
def coupon_delete(request, coupon_id):
    """حذف کد تخفیف"""
    if request.method != 'POST':
        return redirect('influencers:coupon_list')

    if not hasattr(request.user, 'influencer_profile'):
        messages.error(request, "شما دسترسی ندارید.")
        return redirect('core:home')

    coupon = get_object_or_404(Coupon, id=coupon_id, channel__influencer=request.user.influencer_profile)

    code = coupon.code
    coupon.delete()

    messages.success(request, f"کد تخفیف {code} با موفقیت حذف شد! 🗑️")
    return redirect('influencers:coupon_list')
