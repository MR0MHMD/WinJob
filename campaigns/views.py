from collections import defaultdict

from django.urls import reverse

from notifications.utils import notify_influencer_new_campaign_orders
from .models import CampaignClick, CampaignInfluencer, Campaign, Payment
from django.shortcuts import redirect, get_object_or_404, render
from content_team.models import ContentOrder, ContentOrderFile, ContentTeam
from django.contrib.auth.decorators import login_required
from influencers.models import InfluencerServiceRate
from accounts.models import Transaction
from .services.campaigns_notifications import submit_campaign_for_review, approve_campaign_by_admin
from .services.create_invoice import create_campaign_invoice
from .services.free_campaign import create_free_campaign_bookings
from .utils import _detect_file_type
from django.db.models import Prefetch, Count, Sum
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Case, When, Value, IntegerField, Q
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce
from .forms import *
import json


@login_required
def campaign_create_step1(request, campaign_id=None):
    editing_campaign = None
    minutes_value = None  # متغیر برای ذخیره دقیقه‌ها

    if campaign_id:
        editing_campaign = get_object_or_404(
            Campaign,
            id=campaign_id,
            advertiser=request.user.advertiser_profile,
            status=Campaign.Status.DRAFT
        )
        request.session['campaign_draft_id'] = editing_campaign.id

        # دریافت دقیقه از order در صورت وجود
        if editing_campaign.content_service_type and editing_campaign.content_service_type.unit == 'minute':
            order = editing_campaign.content_orders.first()
            if order and order.minutes:
                minutes_value = order.minutes
                request.session['content_minutes'] = minutes_value
            else:
                request.session.pop('content_minutes', None)
        else:
            request.session.pop('content_minutes', None)

    if request.method == 'POST':
        form = CampaignStep1Form(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            if editing_campaign:
                editing_campaign.platform = cd['platform']
                editing_campaign.content_type = cd['content_type']
                editing_campaign.ad_type = cd['ad_type']
                editing_campaign.content_service_type = cd.get('content_service_type')
                editing_campaign.name = cd['name']
                editing_campaign.start_date = cd['start_date']
                editing_campaign.end_date = cd['end_date']
                editing_campaign.is_free = cd["is_free"]
                editing_campaign.save()
                campaign = editing_campaign
            else:
                campaign = Campaign.objects.create(
                    advertiser=request.user.advertiser_profile,
                    platform=cd['platform'],
                    content_type=cd['content_type'],
                    ad_type=cd['ad_type'],
                    content_service_type=cd.get('content_service_type'),
                    name=cd['name'],
                    start_date=cd['start_date'],
                    end_date=cd['end_date'],
                    status=Campaign.Status.DRAFT,
                    is_free=cd["is_free"]
                )
            request.session['content_minutes'] = cd.get('minutes')
            request.session['campaign_draft_id'] = campaign.id
            return redirect('campaigns:campaign_create_step2')
    else:
        initial = {}
        if editing_campaign:
            initial = {
                'platform': editing_campaign.platform,
                'content_type': editing_campaign.content_type,
                'ad_type': editing_campaign.ad_type,
                'content_service_type': editing_campaign.content_service_type,
                'name': editing_campaign.name,
                'start_date': editing_campaign.start_date,
                'end_date': editing_campaign.end_date,
                'is_free': editing_campaign.is_free
            }
            if minutes_value:
                initial['minutes'] = minutes_value
        form = CampaignStep1Form(initial=initial)

    context = {
        'form': form,
        'step': 1,
        'total_steps': 4,
        'step_name': 'اطلاعات پایه کمپین',
        'edit_mode': bool(editing_campaign),
        'campaign': editing_campaign,
    }

    if editing_campaign:
        context.update({
            'edit_content_type_id': editing_campaign.content_type_id,
            'edit_ad_type_id': editing_campaign.ad_type_id,
            'edit_service_type_id': editing_campaign.content_service_type_id,
            'edit_minutes': minutes_value,  # استفاده از متغیر قبلی
        })

    return render(request, 'campaigns/forms/create_campaign_step1.html', context)


@login_required
def campaign_create_step2(request):
    campaign_id = request.session.get('campaign_draft_id')

    # ========== بررسی حالت جایگزینی ==========
    is_replacement_mode = request.GET.get('replacement_mode') == 'true'
    replacement_campaign_id = request.GET.get('campaign_id')

    # اگه حالت جایگزینی فعال باشه، کمپین رو از پارامتر میگیریم
    if is_replacement_mode and replacement_campaign_id:
        campaign = get_object_or_404(
            Campaign,
            id=replacement_campaign_id,
            advertiser=request.user.advertiser_profile,
            status=Campaign.Status.REVISION_NEEDED,  # تغییر: بررسی وضعیت REVISION_NEEDED
            replacement_mode=True  # تغییر: بررسی replacement_mode
        )
        request.session['replacement_campaign_id'] = campaign.id
        request.session['replacement_mode'] = True
    else:
        campaign_id = request.session.get('campaign_draft_id')
        if not campaign_id:
            return redirect('campaigns:campaign_create_step1')
        campaign = get_object_or_404(
            Campaign,
            id=campaign_id,
            advertiser=request.user.advertiser_profile
        )
        request.session.pop('replacement_campaign_id', None)
        request.session.pop('replacement_mode', None)

    # ========== اگر کمپین رایگان باشه ==========
    if campaign.is_free and not is_replacement_mode:
        created_count = create_free_campaign_bookings(campaign)
        if created_count == 0:
            messages.error(request, "هیچ کانال فعال و معتبری برای این پلتفرم و نوع تبلیغ وجود ندارد.")
            return redirect('campaigns:campaign_create_step1')
        return redirect('campaigns:campaign_create_step3_ready')

    platform = campaign.platform
    ad_type = campaign.ad_type

    # ========== موجودی کیف پول کاربر ==========
    wallet_balance = request.user.wallet.balance

    base_queryset = (
        InfluencerServiceRate.objects
        .filter(
            channel__platform=platform,
            ad_type=ad_type,
            channel__is_active=True,
            channel__influencer__is_active=True,
            is_active=True
        )
        .select_related(
            'channel',
            'channel__influencer',
            'channel__platform',
            'channel__province',
            'channel__category'
        )
    )

    filter_form = InfluencerFilterForm(request.GET or None)

    rates = base_queryset

    # ========== در حالت جایگزینی ==========
    if is_replacement_mode:
        # 1. کانال‌های رد شده رو از لیست حذف کن (اونا رو جایگزین میکنیم)
        rejected_ids = campaign.influencer_bookings.filter(
            status=CampaignInfluencer.Status.REJECTED
        ).values_list('service_rate_id', flat=True)
        rates = rates.exclude(id__in=rejected_ids)

        # 2. کانال‌هایی که قبلاً انتخاب شدن (و رد نشدن) رو هم حذف کن
        existing_ids = campaign.influencer_bookings.exclude(
            status=CampaignInfluencer.Status.REJECTED
        ).values_list('service_rate_id', flat=True)
        rates = rates.exclude(id__in=existing_ids)

        # 3. **فقط کانال‌هایی که قیمتشون <= موجودی کیف پول باشه**
        rates = rates.filter(price__lte=wallet_balance)

    # ========== اعمال فیلترها ==========
    if filter_form.is_valid():
        search = filter_form.cleaned_data.get("search")
        category = filter_form.cleaned_data.get("category")
        province = filter_form.cleaned_data.get("province")
        followers_min = filter_form.cleaned_data.get("followers_min")
        followers_max = filter_form.cleaned_data.get("followers_max")
        price_min = filter_form.cleaned_data.get("price_min")
        price_max = filter_form.cleaned_data.get("price_max")

        if search:
            rates = rates.filter(
                Q(channel__channel_name__icontains=search) |
                Q(channel__channel_id__icontains=search)
            )

        if category:
            rates = rates.filter(channel__category=category)

        if province:
            rates = rates.filter(channel__province=province)

        if followers_min is not None:
            rates = rates.filter(channel__followers_count__gte=followers_min)

        if followers_max is not None:
            rates = rates.filter(channel__followers_count__lte=followers_max)

        if price_min is not None:
            rates = rates.filter(price__gte=price_min)

        if price_max is not None:
            rates = rates.filter(price__lte=price_max)

    # ========== اولویت بندی ==========
    advertiser = request.user.advertiser_profile
    advertiser_category_id = advertiser.category_id if advertiser.category_id else None
    advertiser_province_id = request.user.province_id if request.user.province_id else None

    priority_case = Case(
        When(
            Q(channel__category_id=advertiser_category_id) & Q(channel__province_id=advertiser_province_id),
            then=Value(1, output_field=IntegerField())
        ),
        When(
            Q(channel__category_id=advertiser_category_id),
            then=Value(2, output_field=IntegerField())
        ),
        When(
            Q(channel__province_id=advertiser_province_id),
            then=Value(3, output_field=IntegerField())
        ),
        default=Value(4, output_field=IntegerField()),
    )

    rates = rates.annotate(
        channel_points=Coalesce(F('channel__score__points'), Value(0)),
        priority=priority_case
    )

    rates = rates.order_by('priority', '-channel_points', '-channel__followers_count')

    # ========== صفحه‌بندی ==========
    paginator = Paginator(rates, 21)
    page_number = request.GET.get('page')
    rates = paginator.get_page(page_number)

    # ========== انتخاب‌های قبلی ==========
    if is_replacement_mode:
        # فقط کانال‌های رد شده رو به عنوان قبلی در نظر بگیر
        prev_selected = list(
            campaign.influencer_bookings.filter(
                status=CampaignInfluencer.Status.REJECTED
            ).values_list('service_rate_id', flat=True)
        )
        rejected_bookings = campaign.influencer_bookings.filter(
            status=CampaignInfluencer.Status.REJECTED
        )
        total_rejected_price = rejected_bookings.aggregate(
            total=Sum('price')
        )['total'] or 0
    else:
        prev_selected = list(
            campaign.influencer_bookings
            .values_list('service_rate_id', flat=True)
        )
        rejected_bookings = None
        total_rejected_price = 0

    # ========== پردازش POST ==========
    if request.method == "POST":
        selected_rates = request.POST.getlist("rates")

        if not selected_rates:
            messages.error(request, "حداقل یک سرویس اینفلوئنسر انتخاب کنید.")
        else:
            selected_rates_qs = base_queryset.filter(id__in=selected_rates)
            total_selected_price = selected_rates_qs.aggregate(
                total=Sum('price')
            )['total'] or 0

            if not selected_rates_qs.exists():
                messages.error(request, "انتخاب نامعتبر است.")
                return redirect(request.path)

            with transaction.atomic():
                if is_replacement_mode:
                    # ========== حالت جایگزینی ==========

                    # ========== ۱. هزینه‌های فعلی و جدید ==========
                    # ✅ تبدیل به int
                    current_influencer_cost = int(campaign.influencer_bookings.exclude(
                        status__in=[CampaignInfluencer.Status.REJECTED, CampaignInfluencer.Status.REPLACED]
                    ).aggregate(total=Sum('price'))['total'] or 0)

                    new_influencer_cost = int(total_selected_price)

                    content_cost = 0
                    if hasattr(campaign, 'invoice') and campaign.invoice:
                        content_cost = int(campaign.invoice.content_cost)  # ✅ تبدیل به int

                    # ========== ۲. کمیسیون قبلی ==========
                    old_commission = 0
                    if hasattr(campaign, 'invoice') and campaign.invoice:
                        old_commission = int(campaign.invoice.commission)  # ✅ تبدیل به int
                    else:
                        from campaigns.services.create_invoice import PLATFORM_COMMISSION
                        old_subtotal = current_influencer_cost + content_cost
                        old_commission = int(old_subtotal * PLATFORM_COMMISSION)

                    # ========== ۳. کمیسیون جدید ==========
                    from campaigns.services.create_invoice import PLATFORM_COMMISSION
                    new_total_influencer_cost = current_influencer_cost + new_influencer_cost
                    new_subtotal = new_total_influencer_cost + content_cost
                    new_commission = int(new_subtotal * PLATFORM_COMMISSION)

                    # ========== ۴. مابه‌التفاوت ==========
                    commission_to_pay = max(new_commission - old_commission, 0)
                    total_deduct = total_selected_price + commission_to_pay

                    # ========== ۵. بررسی موجودی کیف پول ==========
                    if total_deduct > wallet_balance:
                        messages.error(
                            request,
                            f"موجودی کیف پول شما ({wallet_balance:,} تومان) کافی نیست. "
                            f"هزینه کانال‌های جدید: {total_selected_price:,} تومان + مابه‌التفاوت حق العمل: {commission_to_pay:,} تومان = {total_deduct:,} تومان"
                        )
                        return redirect(request.path)

                    # ========== ۶. رزروهای رد شده به REPLACED ==========
                    rejected_bookings.update(
                        status=CampaignInfluencer.Status.REPLACED
                    )

                    # ========== ۷. اضافه کردن رزروهای جدید ==========
                    for rate in selected_rates_qs:
                        CampaignInfluencer.objects.create(
                            campaign=campaign,
                            channel=rate.channel,
                            service_rate=rate,
                            price=rate.price,
                            status=CampaignInfluencer.Status.PENDING
                        )

                    # ========== ۸. کسر مبلغ از کیف پول ==========
                    if total_deduct > 0:
                        wallet = request.user.wallet
                        wallet.balance -= total_deduct
                        wallet.save(update_fields=['balance'])

                        # تراکنش برای هزینه کانال‌های جدید
                        Transaction.objects.create(
                            user=request.user,
                            amount=total_selected_price,
                            type=Transaction.Type.CAMPAIGN_PAYMENT,
                            status=Transaction.Status.SUCCESS,
                            campaign=campaign,
                            description=f"پرداخت کانال‌های جایگزین در کمپین {campaign.name} (جمعاً {selected_rates_qs.count()} کانال)",
                            reference_id=f"REPLACEMENT_INFLUENCER_{campaign.id}_{timezone.now().timestamp()}"
                        )

                        # تراکنش برای مابه‌التفاوت حق العمل
                        if commission_to_pay > 0:
                            Transaction.objects.create(
                                user=request.user,
                                amount=commission_to_pay,
                                type=Transaction.Type.CAMPAIGN_PAYMENT,
                                status=Transaction.Status.SUCCESS,
                                campaign=campaign,
                                description=f"پرداخت مابه‌التفاوت حق العمل به دلیل افزایش هزینه ناشران (از {old_commission:,} به {new_commission:,} تومان)",
                                reference_id=f"COMMISSION_DIFF_INFLUENCER_{campaign.id}_{timezone.now().timestamp()}"
                            )

                    # ========== ۹. به‌روزرسانی فاکتور ==========
                    invoice = create_campaign_invoice(campaign)

                    # اگر کمیسیون جدید کمتر از قبلی بود، مقدار قبلی رو حفظ کن
                    if invoice.commission < old_commission:
                        invoice.commission = old_commission
                        invoice.total_amount = invoice.influencer_cost + invoice.content_cost + invoice.commission
                        invoice.payable_amount = max(invoice.total_amount - invoice.discount_amount, 0)
                        invoice.save(update_fields=['commission', 'total_amount', 'payable_amount'])

                    # ========== ۱۰. تغییر وضعیت کمپین ==========
                    campaign.status = Campaign.Status.APPROVED
                    campaign.replacement_mode = False
                    campaign.save(update_fields=['status', 'replacement_mode'])

                    request.session.pop('replacement_campaign_id', None)
                    request.session.pop('replacement_mode', None)

                    # ========== ۱۱. پیام موفقیت ==========
                    if commission_to_pay > 0:
                        messages.success(
                            request,
                            f"✅ کانال‌های جایگزین با موفقیت انتخاب شدند. مبلغ {total_deduct:,} تومان از کیف پول شما کسر شد. "
                            f"(هزینه کانال‌ها: {total_selected_price:,} تومان + مابه‌التفاوت حق العمل: {commission_to_pay:,} تومان)"
                        )
                    else:
                        messages.success(
                            request,
                            f"✅ کانال‌های جایگزین با موفقیت انتخاب شدند. مبلغ {total_selected_price:,} تومان از کیف پول شما کسر شد."
                        )

                    return redirect('advertisers:campaign_detail', campaign_id=campaign.id)
                else:
                    # ========== حالت عادی ==========
                    CampaignInfluencer.objects.filter(campaign=campaign).delete()
                    for rate in selected_rates_qs:
                        CampaignInfluencer.objects.create(
                            campaign=campaign,
                            channel=rate.channel,
                            service_rate=rate,
                            price=rate.price
                        )
                    return redirect('campaigns:campaign_create_step3')

    context = {
        "campaign": campaign,
        "rates": rates,
        "prev_selected": prev_selected,
        "platform": platform,
        "filter_form": filter_form,
        "step": 2,
        "total_steps": 4,
        "is_replacement_mode": is_replacement_mode,
        "rejected_bookings": rejected_bookings,
        "total_rejected_price": total_rejected_price,
        "wallet_balance": wallet_balance,
    }

    return render(request, "campaigns/forms/create_campaign_step2.html", context)


@login_required
def campaign_create_step3_team(request):
    # ------------------------ Helper functions ------------------------
    def safe_load_json(value):
        try:
            return json.loads(value) if value else []
        except json.JSONDecodeError:
            return []

    def save_brief(order, brief_form):
        brief_data = brief_form.cleaned_data
        brief, _ = ContentOrderDescription.objects.get_or_create(order=order)

        brief_fields = ['goal', 'goal_description', 'tone', 'brand_name', 'hashtags',
                        'reference_links', 'target_audience', 'description', 'do_not_include']
        for field in brief_fields:
            if field in brief_data:
                setattr(brief, field, brief_data[field])
        brief.save()

    def save_campaign_content(campaign, brief_form):
        ad_caption = brief_form.cleaned_data.get('ad_caption', '')
        ad_link = brief_form.cleaned_data.get('ad_link', '')

        campaign_content, created = CampaignContent.objects.get_or_create(
            campaign=campaign,
            defaults={
                'caption': ad_caption,
                'link': ad_link or '',
                'notes': 'محتوای سفارش داده شده از طریق بریف تیم تولید محتوا',
            }
        )
        if not created:
            campaign_content.caption = ad_caption
            campaign_content.link = ad_link or ''
            campaign_content.save()
        return campaign_content

    def handle_deleted_files(post):
        deleted_ids = safe_load_json(post.get("deleted_attachments"))
        if deleted_ids:
            ContentOrderFile.objects.filter(id__in=deleted_ids).delete()

    def handle_new_files(request, order):
        files = request.FILES.getlist("attachments")
        descriptions = safe_load_json(request.POST.get("attachment_descriptions"))

        if len(files) > 5:
            messages.error(request, "حداکثر می‌توانید ۵ فایل پیوست اضافه کنید.")
            return False

        for i, file in enumerate(files):
            ContentOrderFile.objects.create(
                order=order,
                file=file,
                file_type=_detect_file_type(file),
                description=descriptions[i] if i < len(descriptions) else "",
                original_name=file.name,
                file_size=file.size,
            )
        return True

    def copy_brief_to_new_order(old_order, new_order):
        """
        کپی کردن بریف از سفارش قدیمی به سفارش جدید
        """
        if old_order and hasattr(old_order, 'brief'):
            old_brief = old_order.brief

            # ایجاد بریف جدید با اطلاعات بریف قبلی
            new_brief = ContentOrderDescription.objects.create(
                order=new_order,
                goal=old_brief.goal,
                goal_description=old_brief.goal_description,
                tone=old_brief.tone,
                brand_name=old_brief.brand_name,
                hashtags=old_brief.hashtags,
                reference_links=old_brief.reference_links,
                target_audience=old_brief.target_audience,
                description=old_brief.description,
                do_not_include=old_brief.do_not_include,
            )
            return new_brief
        return None

    def copy_attachments_to_new_order(old_order, new_order):
        """
        کپی کردن فایل‌های پیوست از سفارش قدیمی به سفارش جدید
        (فقط ارجاع به فایل‌ها کپی میشه، خود فایل کپی نمیشه)
        """
        if old_order:
            for old_file in old_order.files.all():
                # فقط اگه فایل هنوز وجود داره
                if old_file.file:
                    ContentOrderFile.objects.create(
                        order=new_order,
                        file=old_file.file,
                        file_type=old_file.file_type,
                        original_name=old_file.original_name,
                        description=old_file.description,
                        file_size=old_file.file_size,
                    )

    def copy_campaign_content(campaign, old_order=None):
        """
        کپی کردن محتوای تبلیغ از سفارش قدیمی یا استفاده از موجود
        """
        # اگر از قبل CampaignContent وجود داره، ازش استفاده کن
        campaign_content, created = CampaignContent.objects.get_or_create(
            campaign=campaign
        )

        # اگر سفارش قدیمی وجود داره و بریف داره، از اون استفاده کن
        if old_order and hasattr(old_order, 'brief'):
            old_brief = old_order.brief
            # فقط اگه قبلاً محتوایی تنظیم نشده باشه
            if not campaign_content.caption and hasattr(old_brief, 'ad_caption'):
                campaign_content.caption = old_brief.ad_caption
                campaign_content.link = old_brief.ad_link or ''
                campaign_content.save()

        return campaign_content

    # ========== بررسی حالت جایگزینی ==========
    is_replacement_mode = request.GET.get('replacement_mode') == 'true'
    replacement_campaign_id = request.GET.get('campaign_id')

    campaign_id = request.session.get("campaign_draft_id")

    # اگه حالت جایگزینی فعال باشه، کمپین رو از پارامتر میگیریم
    if is_replacement_mode and replacement_campaign_id:
        campaign = get_object_or_404(
            Campaign,
            id=replacement_campaign_id,
            advertiser=request.user.advertiser_profile,
            status=Campaign.Status.REVISION_NEEDED,
            replacement_mode=True
        )
        request.session['replacement_campaign_id'] = campaign.id
        request.session['replacement_mode_team'] = True

        service_type = campaign.content_service_type
        if not service_type:
            messages.error(request, "نوع خدمت تولید محتوا مشخص نشده است.")
            return redirect("campaigns:campaign_create_step1")

        existing_order = campaign.content_orders.first()
        minutes = existing_order.minutes if existing_order else request.session.get("content_minutes")
        rejected_team_id = existing_order.team_id if existing_order else None

        existing_brief = existing_order.brief if existing_order and hasattr(existing_order, 'brief') else None
        existing_content = campaign.content if hasattr(campaign, 'content') else None

    else:
        campaign_id = request.session.get("campaign_draft_id")
        if not campaign_id:
            return redirect("campaigns:campaign_create_step1")
        campaign = get_object_or_404(
            Campaign,
            id=campaign_id,
            advertiser=request.user.advertiser_profile
        )
        service_type = campaign.content_service_type
        if not service_type:
            messages.error(request, "نوع خدمت تولید محتوا مشخص نشده است.")
            return redirect("campaigns:campaign_create_step1")
        minutes = request.session.get("content_minutes")
        rejected_team_id = None

        request.session.pop('replacement_campaign_id', None)
        request.session.pop('replacement_mode_team', None)

        existing_brief = None
        existing_content = None

    # ========== موجودی کیف پول (فقط برای حالت جایگزینی) ==========
    wallet_balance = request.user.wallet.balance

    # ========== ادامه کدهای قبلی ==========

    existing_order = ContentOrder.objects.filter(campaign=campaign).select_related("plan", "team", "brief").first()
    attachments = existing_order.files.all() if existing_order else []

    # ------------------------ Teams with active plans ------------------------
    teams_with_plans = (
        ContentTeam.objects.filter(
            service_plans__service_type=service_type,
            service_plans__is_active=True,
            is_active=True
        )
        .distinct()
        .prefetch_related(
            Prefetch(
                'service_plans',
                queryset=ContentServicePlan.objects.filter(
                    service_type=service_type, is_active=True
                ).select_related('service_type').order_by('price_per_unit'),
                to_attr='active_plans_for_service'
            )
        )
        .annotate(
            total_points=Coalesce('score__points', Value(0, output_field=IntegerField())),
            total_completed_orders=Count('orders', filter=Q(orders__status='completed'), distinct=True)
        )
        .order_by('-total_points', '-total_completed_orders')
    )

    # ========== حذف همه تیم‌های رد شده (فقط در حالت جایگزینی) ==========
    if is_replacement_mode:
        # دریافت همه تیم‌هایی که تا الان رد شده‌اند (وضعیت CANCELLED دارند)
        rejected_team_ids = list(
            campaign.content_orders.filter(
                status=ContentOrder.Status.CANCELLED
            ).values_list('team_id', flat=True)
        )

        # اضافه کردن rejected_team_id از پارامتر (اگه وجود داشته باشه)
        if rejected_team_id and rejected_team_id not in rejected_team_ids:
            rejected_team_ids.append(rejected_team_id)

        # حذف تیم‌های رد شده از لیست
        if rejected_team_ids:
            teams_with_plans = teams_with_plans.exclude(id__in=rejected_team_ids)

    # ========== فیلتر بر اساس موجودی کیف پول (فقط در حالت جایگزینی) ==========
    if is_replacement_mode:
        # لیست تیم‌های رد شده رو دوباره محاسبه می‌کنیم (برای اطمینان)
        rejected_team_ids = list(
            campaign.content_orders.filter(
                status=ContentOrder.Status.CANCELLED
            ).values_list('team_id', flat=True)
        )
        if rejected_team_id and rejected_team_id not in rejected_team_ids:
            rejected_team_ids.append(rejected_team_id)

        filtered_teams = []
        for team in teams_with_plans:
            # رد کردن تیم‌هایی که قبلاً رد شدن
            if team.id in rejected_team_ids:
                continue

            plans = getattr(team, 'active_plans_for_service', [])
            valid_plans = []
            for plan in plans:
                if service_type.unit == "minute" and minutes:
                    total_price = int(plan.price_per_unit) * int(minutes)
                else:
                    total_price = int(plan.price_per_unit)

                if total_price <= wallet_balance:
                    valid_plans.append(plan)

            if valid_plans:
                team.active_plans_for_service = valid_plans
                filtered_teams.append(team)

        teams_with_plans = filtered_teams

    paginator = Paginator(teams_with_plans, 21)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ------------------------ Pre-selection logic ------------------------
    preselect_plan_id = request.GET.get('selected_plan')
    preselect_team_id = None
    if preselect_plan_id:
        try:
            plan_id_int = int(preselect_plan_id)
            plan = ContentServicePlan.objects.filter(id=plan_id_int, is_active=True).select_related('team').first()
            if plan:
                preselect_team_id = plan.team.id
        except (ValueError, TypeError):
            pass
    elif request.GET.get('selected_team'):
        try:
            preselect_team_id = int(request.GET.get('selected_team'))
        except (ValueError, TypeError):
            pass

    if not preselect_plan_id and not preselect_team_id and existing_order:
        preselect_plan_id = existing_order.plan.id
        preselect_team_id = existing_order.team.id

    # ------------------------ Build teams_data ------------------------
    teams_data = []
    for team in page_obj:
        plans = getattr(team, 'active_plans_for_service', [])
        if plans:
            plan_prices = []
            for plan in plans:
                if service_type.unit == "minute" and minutes:
                    total_price = int(plan.price_per_unit) * int(minutes)
                else:
                    total_price = int(plan.price_per_unit)

                features = plan.features
                if isinstance(features, str):
                    try:
                        features = json.loads(features)
                    except:
                        features = []
                elif not isinstance(features, list):
                    features = []

                icon = plan.service_type.icon or 'fi-star'

                plan_prices.append({
                    'id': plan.id,
                    'name': plan.name,
                    'price': int(total_price),
                    'price_per_unit': int(plan.price_per_unit),
                    'description': plan.description,
                    'delivery_days': plan.estimated_delivery_days,
                    'features': features,
                    'service_type_icon': icon,
                })
            teams_data.append({
                'team': team,
                'plans': plan_prices,
                'plans_json': json.dumps(plan_prices, ensure_ascii=False),
                'first_plan_id': plan_prices[0]['id'] if plan_prices else None
            })

    # ========== پردازش POST ==========
    if request.method == "POST":
        if is_replacement_mode:
            # ========== دریافت اطلاعات ==========
            selected_plan_id = request.POST.get('selected_plan')

            if not selected_plan_id:
                messages.error(request, "لطفاً یک پلن تولید محتوا انتخاب کنید.")
                return redirect(request.path)

            try:
                selected_plan = ContentServicePlan.objects.get(id=selected_plan_id, is_active=True)
            except ContentServicePlan.DoesNotExist:
                messages.error(request, "پلن انتخاب شده معتبر نیست.")
                return redirect(request.path)

            # ========== محاسبه قیمت جدید ==========
            if service_type.unit == "minute" and minutes:
                new_price = int(selected_plan.price_per_unit) * int(minutes)
            else:
                new_price = int(selected_plan.price_per_unit)

            # ========== دریافت اطلاعات قدیمی ==========
            old_order = campaign.content_orders.first()
            old_price = old_order.price if old_order else 0
            wallet = request.user.wallet

            # ========== محاسبه کمیسیون قبلی و جدید ==========
            from campaigns.services.create_invoice import PLATFORM_COMMISSION

            # ۱. محاسبه هزینه ناشران (ثابت میمونه)
            influencer_cost = sum(booking.price for booking in campaign.influencer_bookings.all())

            # ۲. دریافت کمیسیون قبلی از فاکتور (نه محاسبه مجدد)
            old_commission = 0
            if hasattr(campaign, 'invoice') and campaign.invoice:
                old_commission = campaign.invoice.commission
            else:
                # اگر فاکتور وجود نداشت، محاسبه کن
                old_subtotal = influencer_cost + old_price
                old_commission = int(old_subtotal * PLATFORM_COMMISSION)

            # ۳. محاسبه کمیسیون جدید بر اساس کل مبلغ (هزینه ناشران + هزینه جدید)
            new_subtotal = influencer_cost + new_price
            new_commission = int(new_subtotal * PLATFORM_COMMISSION)

            # ۴. محاسبه مابه‌التفاوت حق العمل (فقط اگر مثبت باشد)
            commission_to_pay = max(new_commission - old_commission, 0)

            # ۵. محاسبه کل مبلغی که باید از کیف پول کم بشه
            total_deduct = new_price + commission_to_pay

            # ========== بررسی موجودی کیف پول ==========
            if wallet.balance < total_deduct:
                messages.error(
                    request,
                    f"موجودی کیف پول شما ({wallet.balance:,} تومان) کافی نیست. "
                    f"هزینه تیم جدید: {new_price:,} تومان + مابه‌التفاوت حق العمل: {commission_to_pay:,} تومان = {total_deduct:,} تومان"
                )
                return redirect(request.path)

            # ========== اجرای تراکنش اتمیک ==========
            with transaction.atomic():
                # ۱. کسر مبلغ کل از کیف پول
                wallet.balance -= total_deduct
                wallet.save(update_fields=['balance'])

                # ۲. ثبت تراکنش برای هزینه جدید تیم محتوا
                Transaction.objects.create(
                    user=request.user,
                    amount=new_price,
                    type=Transaction.Type.CAMPAIGN_PAYMENT,
                    status=Transaction.Status.SUCCESS,
                    campaign=campaign,
                    description=f"پرداخت تیم تولید محتوای جدید ({selected_plan.team.name}) در کمپین {campaign.name} (جایگزینی)",
                    reference_id=f"TEAM_NEW_PAYMENT_{campaign.id}_{timezone.now().timestamp()}"
                )

                # ۳. اگر مابه‌التفاوت حق العمل مثبت بود، تراکنش جداگانه ثبت کن
                if commission_to_pay > 0:
                    Transaction.objects.create(
                        user=request.user,
                        amount=commission_to_pay,
                        type=Transaction.Type.CAMPAIGN_PAYMENT,
                        status=Transaction.Status.SUCCESS,
                        campaign=campaign,
                        description=f"پرداخت مابه‌التفاوت حق العمل به دلیل افزایش هزینه تولید محتوا (از {old_price:,} به {new_price:,} تومان)",
                        reference_id=f"COMMISSION_DIFF_{campaign.id}_{timezone.now().timestamp()}"
                    )

                # ۴. نگه‌داشتن سفارش قدیمی با وضعیت CANCELLED
                if old_order:
                    if old_order.status != ContentOrder.Status.CANCELLED:
                        old_order.status = ContentOrder.Status.CANCELLED
                        old_order.save(update_fields=['status'])

                # ۵. ایجاد سفارش جدید
                new_order = ContentOrder.objects.create(
                    campaign=campaign,
                    team=selected_plan.team,
                    plan=selected_plan,
                    price=new_price,
                    minutes=int(minutes) if minutes else None,
                    status=ContentOrder.Status.PENDING
                )

                # ۶. ثبت جایگزینی
                old_order.replaced_by = new_order
                old_order.replaced_at = timezone.now()
                old_order.save(update_fields=['replaced_by', 'replaced_at'])

                # ۷. کپی بریف از سفارش قدیمی به جدید
                if old_order and hasattr(old_order, 'brief'):
                    old_brief = old_order.brief
                    ContentOrderDescription.objects.create(
                        order=new_order,
                        goal=old_brief.goal,
                        goal_description=old_brief.goal_description,
                        tone=old_brief.tone,
                        brand_name=old_brief.brand_name,
                        hashtags=old_brief.hashtags,
                        reference_links=old_brief.reference_links,
                        target_audience=old_brief.target_audience,
                        description=old_brief.description,
                        do_not_include=old_brief.do_not_include,
                    )

                # ۸. کپی فایل‌های پیوست
                if old_order:
                    for old_file in old_order.files.all():
                        if old_file.file:
                            ContentOrderFile.objects.create(
                                order=new_order,
                                file=old_file.file,
                                file_type=old_file.file_type,
                                original_name=old_file.original_name,
                                description=old_file.description,
                                file_size=old_file.file_size,
                            )

                # ۹. اطمینان از وجود CampaignContent
                campaign_content, created = CampaignContent.objects.get_or_create(
                    campaign=campaign
                )
                if old_order and hasattr(old_order, 'brief') and not campaign_content.caption:
                    old_brief = old_order.brief
                    if hasattr(old_brief, 'ad_caption'):
                        campaign_content.caption = old_brief.ad_caption
                        campaign_content.link = old_brief.ad_link or ''
                        campaign_content.save(update_fields=['caption', 'link'])

                # ========== ۱۰. به‌روزرسانی فاکتور با حفظ کمیسیون قدیمی ==========
                if hasattr(campaign, 'invoice'):
                    from campaigns.services.create_invoice import create_campaign_invoice
                    # فاکتور رو با مقادیر جدید محاسبه کن
                    invoice = create_campaign_invoice(campaign)

                    # اگر کمیسیون جدید از کمیسیون قبلی کمتر بود، مقدار قبلی رو حفظ کن
                    if invoice.commission < old_commission:
                        invoice.commission = old_commission
                        # محاسبه مجدد total_amount و payable_amount با کمیسیون جدید
                        invoice.total_amount = invoice.influencer_cost + invoice.content_cost + invoice.commission
                        invoice.payable_amount = max(invoice.total_amount - invoice.discount_amount, 0)
                        invoice.save(update_fields=['commission', 'total_amount', 'payable_amount'])

                # ۱۱. تغییر وضعیت کمپین
                campaign.status = Campaign.Status.APPROVED
                campaign.replacement_mode = False
                campaign.content_team_rejected = False
                campaign.save(update_fields=['status', 'replacement_mode', 'content_team_rejected'])

                # ۱۲. پاک کردن session
                request.session.pop('replacement_campaign_id', None)
                request.session.pop('replacement_mode_team', None)

                # ۱۳. پیام موفقیت
                if commission_to_pay > 0:
                    messages.success(
                        request,
                        f"✅ تیم تولید محتوا با موفقیت تغییر کرد. مبلغ {total_deduct:,} تومان از کیف پول شما کسر شد. "
                        f"(هزینه تیم جدید: {new_price:,} تومان + مابه‌التفاوت حق العمل: {commission_to_pay:,} تومان)"
                    )
                else:
                    messages.success(
                        request,
                        f"✅ تیم تولید محتوا با موفقیت تغییر کرد. مبلغ {new_price:,} تومان از کیف پول شما کسر شد."
                    )
                return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

        else:
            # ========== حالت عادی ساخت کمپین ==========
            team_form = CampaignStep3TeamForm(request.POST, service_type=service_type)
            brief_form = CampaignStep3BriefForm(request.POST, request.FILES)

            if team_form.is_valid() and brief_form.is_valid():
                selected_plan_id = team_form.cleaned_data['selected_plan']
                selected_plan = ContentServicePlan.objects.get(id=selected_plan_id)

                if service_type.unit == "minute" and minutes:
                    final_price = selected_plan.price_per_unit * int(minutes)
                else:
                    final_price = selected_plan.price_per_unit

                order, created = ContentOrder.objects.get_or_create(
                    campaign=campaign,
                    defaults={
                        "team": selected_plan.team,
                        "plan": selected_plan,
                        "price": final_price,
                        "minutes": int(minutes) if minutes else None,
                        "status": ContentOrder.Status.PENDING,
                    }
                )
                if not created:
                    order.team = selected_plan.team
                    order.plan = selected_plan
                    order.price = final_price
                    order.minutes = int(minutes) if minutes else None
                    order.save()

                save_brief(order, brief_form)
                save_campaign_content(campaign, brief_form)

                handle_deleted_files(request.POST)
                if not handle_new_files(request, order):
                    return redirect("campaigns:campaign_create_step3_team")

                current_page = request.GET.get('page', '1')
                request.session['step3_team_page'] = current_page

                return redirect("campaigns:campaign_create_step4")
            else:
                for form in (team_form, brief_form):
                    for errors in form.errors.values():
                        for err in errors:
                            messages.error(request, err)

    # ========== GET ==========
    else:
        if is_replacement_mode:
            team_form = CampaignStep3TeamForm(service_type=service_type)

            brief_initial = {}
            if existing_brief:
                brief_initial = {
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

            if existing_content:
                brief_initial['ad_caption'] = existing_content.caption
                brief_initial['ad_link'] = existing_content.link or ''

            brief_form = CampaignStep3BriefForm(initial=brief_initial)

        else:
            initial_plan = existing_order.plan.id if existing_order else None
            team_form = CampaignStep3TeamForm(initial={'selected_plan': initial_plan}, service_type=service_type)

            brief_initial = {}
            if existing_order and hasattr(existing_order, 'brief'):
                b = existing_order.brief
                brief_initial = {
                    'goal': b.goal,
                    'goal_description': b.goal_description,
                    'tone': b.tone,
                    'brand_name': b.brand_name,
                    'hashtags': b.hashtags,
                    'reference_links': b.reference_links,
                    'target_audience': b.target_audience,
                    'description': b.description,
                    'do_not_include': b.do_not_include,
                }
            if hasattr(campaign, 'content') and campaign.content:
                brief_initial['ad_caption'] = campaign.content.caption
                brief_initial['ad_link'] = campaign.content.link or ''

            brief_form = CampaignStep3BriefForm(initial=brief_initial)

    # ========== Context ==========
    context = {
        "campaign": campaign,
        'page_obj': page_obj,
        "service_type": service_type,
        "teams_data": teams_data,
        "minutes": minutes,
        "existing_order": existing_order,
        "team_form": team_form,
        "brief_form": brief_form,
        "attachments": attachments,
        "preselect_plan_id": preselect_plan_id,
        "preselect_team_id": preselect_team_id,
        "influencer_cost": sum(booking.price for booking in campaign.influencer_bookings.all()),  # عدد خالص
        "old_content_cost": existing_order.price if existing_order else 0,
        "step": 3,
        "total_steps": 4,
        "step_name": "انتخاب تیم و پلن تولید محتوا",
        "is_replacement_mode": is_replacement_mode,
        "rejected_team_id": rejected_team_id,
        "wallet_balance": wallet_balance,
    }
    return render(request, "campaigns/forms/create_campaign_step3_team.html", context)


@login_required
def campaign_create_step3_ready(request):
    campaign_id = request.session.get("campaign_draft_id")

    if not campaign_id:
        return redirect("campaigns:campaign_create_step1")

    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile
    )

    # چک میکنیم که content_type درست تنظیم شده باشه
    if campaign.content_type.slug != "ready-content":
        if campaign.content_type.slug == "content-production-team":
            return redirect("campaigns:campaign_create_step3_team")
        return redirect("campaigns:campaign_create_step3")

    content, created = CampaignContent.objects.get_or_create(campaign=campaign)

    # ===== دریافت اطلاعات از session (حالت تبدیل) - با get نه pop =====
    switch_data = request.session.get('campaign_switch_to_ready_data', {})
    is_switch_mode = request.session.get('is_switch_to_ready_mode', False) or bool(switch_data)

    # اگه حالت تبدیل هست و محتوایی تنظیم نشده، از session استفاده کن
    if is_switch_mode and not content.caption:
        content.caption = switch_data.get('caption', '')
        content.link = switch_data.get('link', '')
        content.save()

    if request.method == "POST":
        form = CampaignStep3ReadyForm(
            request.POST,
            request.FILES,
            instance=content,
            is_switch_mode=is_switch_mode
        )

        if form.is_valid():
            if is_switch_mode:
                # ========== ذخیره محتوا ==========
                form.save()

                # ========== ذخیره کمیسیون قبلی (قبل از به‌روزرسانی فاکتور) ==========
                old_commission = 0
                if hasattr(campaign, 'invoice') and campaign.invoice:
                    old_commission = campaign.invoice.commission

                # ========== به‌روزرسانی فاکتور (هزینه محتوا صفر میشه) ==========
                invoice = create_campaign_invoice(campaign)

                # ========== اگر کمیسیون جدید کمتر از قبلی بود، مقدار قبلی رو حفظ کن ==========
                if invoice.commission < old_commission:
                    invoice.commission = old_commission
                    invoice.total_amount = invoice.influencer_cost + invoice.content_cost + invoice.commission
                    invoice.payable_amount = max(invoice.total_amount - invoice.discount_amount, 0)
                    invoice.save(update_fields=['commission', 'total_amount', 'payable_amount'])

                # کمپین رو به APPROVED برگردون
                campaign.status = Campaign.Status.APPROVED
                campaign.replacement_mode = False
                campaign.content_team_rejected = False
                campaign.save(update_fields=['status', 'replacement_mode', 'content_team_rejected'])

                # ارسال نوتیف به اینفلوئنسرها
                influencer_counts = defaultdict(int)
                bookings = campaign.influencer_bookings.select_related('channel__influencer__user')
                for booking in bookings:
                    user = booking.channel.influencer.user
                    influencer_counts[user] += 1
                for user, count in influencer_counts.items():
                    notify_influencer_new_campaign_orders(user, campaign, count)

                # حذف session
                for key in ['campaign_draft_id', 'is_switch_to_ready_mode', 'campaign_switch_to_ready_data']:
                    if key in request.session:
                        del request.session[key]

                messages.success(request, "✅ محتوای شما با موفقیت آپلود شد و کمپین به حالت تایید شده بازگشت.")
                return redirect('advertisers:campaign_detail', campaign_id=campaign.id)
            else:
                # ===== حالت عادی ساخت کمپین =====
                form.save()
                if campaign.is_free:
                    approve_campaign_by_admin(campaign)
                    if "campaign_draft_id" in request.session:
                        del request.session["campaign_draft_id"]
                    messages.success(request, "کمپین رایگان شما با موفقیت ثبت و تأیید شد.")
                    return redirect("advertisers:my_campaigns")
                else:
                    return redirect("campaigns:campaign_create_step4")
        else:
            # نمایش خطاها در تمپلیت
            print(form.errors)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    else:
        # ارسال is_switch_mode به فرم
        form = CampaignStep3ReadyForm(instance=content, is_switch_mode=is_switch_mode)

    context = {
        "campaign": campaign,
        "form": form,
        "existing_media": content.media.url if content.media else None,
        "step": 3,
        "total_steps": 4,
        "step_name": "آپلود محتوای تبلیغ",
        "is_switch_mode": is_switch_mode,
        "switch_data": switch_data,
    }

    return render(request, "campaigns/forms/create_campaign_step3_ready.html", context)


@login_required
def campaign_create_step4(request):
    campaign_id = request.session.get("campaign_draft_id")

    if not campaign_id:
        return redirect("campaigns:campaign_create_step1")

    campaign = get_object_or_404(
        Campaign.objects.select_related(
            "platform",
            "content_type",
            "ad_type",
            "influencer_coupon",
            "content_team_coupon",
            "platform_coupon"
        ),
        id=campaign_id,
        advertiser=request.user.advertiser_profile
    )

    influencer_bookings = (
        campaign.influencer_bookings
        .select_related(
            "channel",
            "channel__platform",
            "channel__influencer"
        )
    )

    content_order = (
        campaign.content_orders
        .select_related("team", "plan", "plan__service_type")
        .first()
    )

    campaign_content = None
    is_video = False
    if campaign.content_type.slug == "ready-content":
        try:
            campaign_content = campaign.content
            is_video = campaign_content.is_video if campaign_content else False
        except CampaignContent.DoesNotExist:
            campaign_content = None

    invoice = create_campaign_invoice(campaign)
    wallet = request.user.wallet

    total_price = invoice.influencer_cost + invoice.content_cost
    step3_page = request.session.get('step3_team_page', '1')

    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "gateway")

        if payment_method == "wallet":
            if wallet.balance < invoice.payable_amount:
                messages.error(request, "موجودی کیف پول کافی نیست.")
                return redirect("campaigns:campaign_create_step4")

            with transaction.atomic():
                wallet.balance -= invoice.payable_amount
                wallet.save(update_fields=["balance"])

                Transaction.objects.create(
                    user=request.user,
                    amount=invoice.payable_amount,
                    type=Transaction.Type.CAMPAIGN_PAYMENT,
                    status=Transaction.Status.SUCCESS,
                    campaign=campaign,
                    invoice=invoice,
                    description=f"پرداخت کمپین {campaign.name} از طریق کیف پول",
                    reference_id=f"WALLET_{invoice.id}_{timezone.now().timestamp()}"
                )

                Payment.objects.create(
                    user=request.user,
                    invoice=invoice,
                    amount=invoice.payable_amount,
                    status=Payment.Status.SUCCESS,
                    payment_method=Payment.Method.WALLET
                )

                invoice.is_paid = True
                invoice.save(update_fields=["is_paid"])

                for coupon in [campaign.influencer_coupon, campaign.content_team_coupon, campaign.platform_coupon]:
                    if coupon:
                        coupon.used_count += 1
                        coupon.save(update_fields=["used_count"])

                campaign.status = Campaign.Status.PENDING
                campaign.save(update_fields=["status"])

            del request.session["campaign_draft_id"]
            messages.success(request, "کمپین با موفقیت ثبت شد.")
            return redirect("advertisers:my_campaigns")

        else:
            with transaction.atomic():
                payment = Payment.objects.create(
                    user=request.user,
                    invoice=invoice,
                    amount=invoice.payable_amount,
                    status=Payment.Status.SUCCESS,
                    payment_method=Payment.Method.GATEWAY
                )

                Transaction.objects.create(
                    user=request.user,
                    amount=invoice.payable_amount,
                    type=Transaction.Type.GATEWAY_PAYMENT,
                    status=Transaction.Status.SUCCESS,
                    campaign=campaign,
                    invoice=invoice,
                    payment=payment,
                    description=f"پرداخت کمپین {campaign.name} از طریق درگاه (شبیه‌سازی)",
                    reference_id=f"GATEWAY_{invoice.id}_{timezone.now().timestamp()}"
                )

                invoice.is_paid = True
                invoice.save(update_fields=["is_paid"])

                # افزایش تعداد استفاده برای هر سه نوع کوپن
                for coupon in [campaign.influencer_coupon, campaign.content_team_coupon, campaign.platform_coupon]:
                    if coupon:
                        coupon.used_count += 1
                        coupon.save(update_fields=["used_count"])

                submit_campaign_for_review(campaign)

            del request.session["campaign_draft_id"]
            messages.success(request, "پرداخت با موفقیت انجام شد. کمپین ثبت گردید.")
            return redirect("advertisers:my_campaigns")

    context = {
        "campaign": campaign,
        "influencer_bookings": influencer_bookings,
        "content_order": content_order,
        "influencer_cost": invoice.influencer_cost,
        "team_cost": invoice.content_cost,
        "total_price": total_price,
        'step3_page': step3_page,
        "commission": invoice.commission,
        "final_total": invoice.total_amount,
        "discount_amount": invoice.discount_amount,
        "payable_amount": invoice.payable_amount,
        "discount_breakdown": getattr(invoice, 'discount_breakdown', {
            'influencer_discount': 0,
            'content_discount': 0,
            'platform_discount': 0
        }),
        "invoice": invoice,
        "wallet": wallet,
        "campaign_content": campaign_content,
        "is_video": is_video,
        "step": 4,
        "total_steps": 4,
        "step_name": "پرداخت",
    }

    return render(request, "campaigns/forms/create_campaign_step4.html", context)


def track_click(request, code):
    influencer = get_object_or_404(
        CampaignInfluencer,
        tracking_code=code
    )

    tracking = influencer.tracking_link

    ip = request.META.get("REMOTE_ADDR")
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    is_unique = not CampaignClick.objects.filter(
        tracking_link=tracking,
        ip_address=ip
    ).exists()

    CampaignClick.objects.create(
        tracking_link=tracking,
        ip_address=ip,
        user_agent=user_agent
    )

    tracking.clicks = F("clicks") + 1

    if is_unique:
        tracking.unique_clicks = F("unique_clicks") + 1

    tracking.save(update_fields=["clicks", "unique_clicks"])

    campaign = influencer.campaign
    content = campaign.content

    if content.utm_enabled:
        destination_url = content.get_utm_link(influencer)
    else:
        destination_url = content.link

    return redirect(destination_url)


# campaigns/views.py

@login_required
def campaign_select_replacement(request, campaign_id):
    """صفحه انتخاب کانال جایگزین بعد از رد شدن - هدایت به استپ ۲"""

    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile,
        status=Campaign.Status.REVISION_NEEDED,  # تغییر: از APPROVED به REVISION_NEEDED
        replacement_mode=True  # تغییر: چک کردن replacement_mode
    )

    rejected_bookings = campaign.influencer_bookings.filter(
        status=CampaignInfluencer.Status.REJECTED
    )

    if not rejected_bookings.exists():
        messages.info(request, "هیچ کانال رد شده‌ای برای جایگزینی وجود ندارد.")
        return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

    return redirect(f"{reverse('campaigns:campaign_create_step2')}?replacement_mode=true&campaign_id={campaign.id}")


@login_required
def campaign_replace_team(request, campaign_id):
    """انتخاب تیم تولید محتوای جایگزین - هدایت به استپ ۳"""

    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile,
        status=Campaign.Status.REVISION_NEEDED,
        replacement_mode=True
    )

    # بررسی اینکه تیم محتوا واقعاً رد کرده
    existing_order = campaign.content_orders.first()
    if not existing_order or existing_order.status != ContentOrder.Status.CANCELLED:
        messages.error(request, "سفارش تیم محتوا قابل جایگزینی نیست.")
        return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

    # هدایت به استپ ۳ با پارامترهای جایگزینی
    return redirect(
        f"{reverse('campaigns:campaign_create_step3_team')}?replacement_mode=true&campaign_id={campaign.id}"
    )


@login_required
def campaign_switch_to_ready(request, campaign_id):
    if request.method != 'POST':
        messages.warning(request, "این عملیات تنها از طریق فرم قابل انجام است.")
        return redirect('advertisers:campaign_detail', campaign_id=campaign_id)

    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile,
        status=Campaign.Status.REVISION_NEEDED
    )

    existing_order = campaign.content_orders.first()
    if not existing_order or existing_order.status != ContentOrder.Status.CANCELLED:
        messages.error(request, "امکان تبدیل به محتوای آماده وجود ندارد.")
        return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

    with transaction.atomic():
        # ========== دریافت اطلاعات بریف ==========
        brief_data = {}
        if hasattr(existing_order, 'brief'):
            brief = existing_order.brief
            caption_text = brief.description[:200] if brief.description else ''
            link_url = ''
            if hasattr(campaign, 'content') and campaign.content and campaign.content.link:
                link_url = campaign.content.link

            brief_data = {
                'caption': caption_text,
                'link': link_url,
            }

        # تغییر نوع محتوا به آماده
        ready_content_type = ContentType.objects.filter(slug='ready-content').first()
        if not ready_content_type:
            messages.error(request, "نوع محتوای آماده در سیستم تعریف نشده است.")
            return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

        campaign.content_type = ready_content_type
        campaign.content_service_type = None

        # لغو سفارش تیم محتوا (بدون حذف)
        existing_order.status = ContentOrder.Status.CANCELLED
        existing_order.save(update_fields=['status'])

        # غیرفعال کردن حالت جایگزینی و رد تیم محتوا
        campaign.replacement_mode = False
        campaign.content_team_rejected = False
        campaign.save(update_fields=[
            'content_type',
            'content_service_type',
            'replacement_mode',
            'content_team_rejected'
        ])


        # ذخیره اطلاعات بریف در session
        request.session['campaign_switch_to_ready_data'] = brief_data
        request.session['campaign_draft_id'] = campaign.id
        request.session['is_switch_to_ready_mode'] = True

    messages.info(request, "لطفاً محتوای تبلیغ را آپلود کنید.")
    return redirect('campaigns:campaign_create_step3_ready')



@login_required
def campaign_switch_to_ready_cancel(request, campaign_id):
    """
    لغو تبدیل به محتوای آماده و برگشت به حالت قبلی (تیم تولید محتوا)
    """
    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile
    )

    if campaign.status != Campaign.Status.REVISION_NEEDED:
        messages.warning(request, "این عملیات قابل انجام نیست.")
        return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

    if campaign.content_type.slug != "ready-content":
        messages.warning(request, "نوع محتوای کمپین آماده نیست.")
        return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

    team_content_type = ContentType.objects.filter(slug='content-production-team').first()
    if team_content_type:
        campaign.content_type = team_content_type
        existing_order = campaign.content_orders.first()
        if existing_order and existing_order.plan and existing_order.plan.service_type:
            campaign.content_service_type = existing_order.plan.service_type
        campaign.replacement_mode = True
        campaign.content_team_rejected = True
        campaign.save(
            update_fields=['content_type', 'content_service_type', 'replacement_mode', 'content_team_rejected']
        )

    # پاک کردن session های مربوط به تبدیل
    for key in ['campaign_switch_to_ready_data', 'is_switch_to_ready_mode']:
        if key in request.session:
            del request.session[key]

    messages.info(request, "به حالت انتخاب تیم تولید محتوا بازگشتید.")
    return redirect('advertisers:campaign_detail', campaign_id=campaign.id)


@login_required
def campaign_continue_without_replacement(request, campaign_id):
    """
    ادامه کمپین بدون انتخاب ناشر جایگزین
    ناشران رد شده نادیده گرفته می‌شوند و کمپین به APPROVED برمی‌گردد
    """
    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile,
        status=Campaign.Status.REVISION_NEEDED,
        replacement_mode=True
    )

    if request.method != 'POST':
        messages.warning(request, "این عملیات تنها از طریق فرم قابل انجام است.")
        return redirect('advertisers:campaign_detail', campaign_id=campaign.id)

    with transaction.atomic():
        # ========== ناشران رد شده رو به REPLACED تغییر بده ==========
        rejected_bookings = campaign.influencer_bookings.filter(
            status=CampaignInfluencer.Status.REJECTED
        )
        rejected_count = rejected_bookings.count()

        # ========== کمپین رو به APPROVED برگردون ==========
        campaign.status = Campaign.Status.APPROVED
        campaign.replacement_mode = False
        campaign.save(update_fields=['status', 'replacement_mode'])

        # ========== نوتیف به کاربر ==========
        from notifications.utils import notify_advertiser_campaign_auto_approved
        notify_advertiser_campaign_auto_approved(campaign)

        messages.success(
            request,
            f"✅ کمپین با موفقیت ادامه یافت. {rejected_count} ناشر رد شده نادیده گرفته شدند."
        )

        return redirect('advertisers:campaign_detail', campaign_id=campaign.id)
