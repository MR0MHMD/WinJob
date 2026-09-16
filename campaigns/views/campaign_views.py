from ..services.campaigns_notifications import submit_campaign_for_review, approve_campaign_by_admin
from ..utils import save_brief, save_campaign_content, handle_deleted_files, handle_new_files
from django.db.models import Prefetch, Count, Sum, Q, F, Case, When, Value, IntegerField, Avg
from notifications.utils import notify_influencer_new_campaign_orders
from payment.services.tax_calculator import calculate_replacement_tax
from payment.services.create_invoice import create_campaign_invoice
from ..services.free_campaign import create_free_campaign_bookings
from influencers.models import ChannelServiceRate, ChannelBooking
from django.shortcuts import redirect, get_object_or_404, render
from django_iranian_payment.contrib.django import services
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Coalesce
from payment.models import Transaction, Payment
from ..models import Campaign, CampaignContent
from django.core.paginator import Paginator
from collections import defaultdict
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.urls import reverse

import json
from content_team.models import (
    ContentOrder,
    ContentOrderFile,
    ContentTeam,
    ContentServicePlan,
    ContentOrderDescription,
    TeamReview
)
from ..forms import (
    CampaignStep3BriefForm,
    CampaignStep3ReadyForm,
    CampaignStep3TeamForm,
    InfluencerFilterForm,
    CampaignStep1Form,
)


@login_required
def campaign_create_step1(request, campaign_id=None):
    editing_campaign = None

    if campaign_id:
        editing_campaign = get_object_or_404(
            Campaign,
            id=campaign_id,
            advertiser=request.user.advertiser_profile,
            status=Campaign.Status.DRAFT
        )
        request.session['campaign_draft_id'] = editing_campaign.id

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
        })

    return render(request, 'campaigns/forms/create_campaign_step1.html', context)


@login_required
def campaign_create_step2(request):
    # ========== بررسی حالت جایگزینی ==========
    is_replacement_mode = request.GET.get('replacement_mode') == 'true'
    replacement_campaign_id = request.GET.get('campaign_id')

    if is_replacement_mode and replacement_campaign_id:
        campaign = get_object_or_404(
            Campaign,
            id=replacement_campaign_id,
            advertiser=request.user.advertiser_profile,
            status=Campaign.Status.REVISION_NEEDED,
            replacement_mode=True
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
        ChannelServiceRate.objects
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
            status=ChannelBooking.Status.REJECTED
        ).values_list('service_rate_id', flat=True)
        rates = rates.exclude(id__in=rejected_ids)

        # 2. کانال‌هایی که قبلاً انتخاب شدن (و رد نشدن) رو هم حذف کن
        existing_ids = campaign.influencer_bookings.exclude(
            status=ChannelBooking.Status.REJECTED
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
                status=ChannelBooking.Status.REJECTED
            ).values_list('service_rate_id', flat=True)
        )
        rejected_bookings = campaign.influencer_bookings.filter(
            status=ChannelBooking.Status.REJECTED
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
            messages.error(request, "حداقل یک کانال انتخاب کنید.")
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
                    # ========== ۱. محاسبه مالیات با سرویس جدید ==========

                    tax_result = calculate_replacement_tax(
                        campaign=campaign,
                        new_selected_cost=total_selected_price
                    )

                    total_deduct = tax_result['total_deduct']

                    # ========== ۲. بررسی موجودی کیف پول ==========
                    if total_deduct > wallet_balance:
                        # ساخت پیام خطای زیبا
                        error_parts = [
                            f"موجودی کیف پول شما ({wallet_balance:,} تومان) کافی نیست."
                        ]

                        # اضافه کردن جزییات به پیام
                        for item in tax_result['breakdown']:
                            if not item.get('is_total'):
                                error_parts.append(f"{item['label']}: {item['formatted']} تومان")

                        error_parts.append(f"مبلغ نهایی: {total_deduct:,} تومان")

                        messages.error(request, "\n".join(error_parts))
                        return redirect(request.path)

                    # ========== ۳. رزروهای رد شده به REPLACED ==========
                    rejected_bookings.update(
                        status=ChannelBooking.Status.REPLACED
                    )

                    # ========== ۴. اضافه کردن رزروهای جدید ==========
                    for rate in selected_rates_qs:
                        ChannelBooking.objects.create(
                            campaign=campaign,
                            channel=rate.channel,
                            service_rate=rate,
                            price=rate.price,
                            original_price=rate.price,
                            status=ChannelBooking.Status.PENDING
                        )

                    # ========== ۵. کسر مبلغ از کیف پول ==========
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

                        # تراکنش برای مابه‌التفاوت کمیسیون (اگر مثبت)
                        if tax_result['commission_diff'] > 0:
                            Transaction.objects.create(
                                user=request.user,
                                amount=tax_result['commission_diff'],
                                type=Transaction.Type.CAMPAIGN_PAYMENT,
                                status=Transaction.Status.SUCCESS,
                                campaign=campaign,
                                description=f"پرداخت مابه‌التفاوت حق‌العمل (از {tax_result['old_data']['commission']:,} به {tax_result['new_data']['commission']:,} تومان)",
                                reference_id=f"COMMISSION_DIFF_{campaign.id}_{timezone.now().timestamp()}"
                            )

                        # تراکنش برای مابه‌التفاوت مالیات (اگر مثبت)
                        if tax_result['vat_diff'] > 0:
                            Transaction.objects.create(
                                user=request.user,
                                amount=tax_result['vat_diff'],
                                type=Transaction.Type.CAMPAIGN_PAYMENT,
                                status=Transaction.Status.SUCCESS,
                                campaign=campaign,
                                description=f"پرداخت مابه‌التفاوت مالیات بر ارزش افزوده (از {tax_result['old_data']['total_vat']:,} به {tax_result['new_data']['total_vat']:,} تومان)",
                                reference_id=f"VAT_DIFF_{campaign.id}_{timezone.now().timestamp()}"
                            )

                        # اگر مالیات کاهش پیدا کرده (تخفیف/کمک هزینه)
                        if tax_result['vat_diff'] < 0:
                            Transaction.objects.create(
                                user=request.user,
                                amount=abs(tax_result['vat_diff']),
                                type=Transaction.Type.CAMPAIGN_REFUND,
                                status=Transaction.Status.SUCCESS,
                                campaign=campaign,
                                description=f"کمک هزینه کاهش مالیات بر ارزش افزوده (از {tax_result['old_data']['total_vat']:,} به {tax_result['new_data']['total_vat']:,} تومان)",
                                reference_id=f"TAX_ADJUSTMENT_{campaign.id}_{timezone.now().timestamp()}"
                            )

                    # ========== ۶. به‌روزرسانی فاکتور ==========
                    invoice = create_campaign_invoice(campaign)

                    # ✅ حفظ کمیسیون قبلی (اگر جدید کمتر بود)
                    old_commission = tax_result['old_data']['commission']
                    if invoice.commission < old_commission:
                        invoice.commission = old_commission

                    # ✅ تنظیم مالیات جدید (نه قبلی!)
                    new_vat = tax_result['new_data']['total_vat']
                    invoice.total_vat = new_vat  # ✅ مالیات جدید رو اعمال کن

                    # ✅ محاسبه مجدد مبلغ قابل پرداخت با مالیات جدید
                    invoice.total_amount = invoice.influencer_cost + invoice.content_cost + invoice.commission
                    invoice.payable_amount = invoice.total_amount + invoice.total_vat

                    # ✅ ذخیره نهایی
                    invoice.save(update_fields=[
                        'commission',
                        'total_vat',
                        'total_amount',
                        'payable_amount'
                    ])

                    # ========== ۷. تغییر وضعیت کمپین ==========
                    campaign.status = Campaign.Status.APPROVED
                    campaign.replacement_mode = False
                    campaign.save(update_fields=['status', 'replacement_mode'])

                    request.session.pop('replacement_campaign_id', None)
                    request.session.pop('replacement_mode', None)

                    # ========== ۸. ساخت پیام موفقیت ==========
                    success_parts = [f"✅ کانال‌های جایگزین با موفقیت انتخاب شدند."]

                    for item in tax_result['breakdown']:
                        if item.get('is_total'):
                            success_parts.append(f"💰 {item['label']}: {item['formatted']} تومان")
                        else:
                            success_parts.append(f"• {item['label']}: {item['formatted']} تومان")

                    messages.success(request, "\n".join(success_parts))

                    return redirect(campaign)
                else:
                    # ========== حالت عادی ==========
                    ChannelBooking.objects.filter(campaign=campaign).delete()
                    for rate in selected_rates_qs:
                        ChannelBooking.objects.create(
                            campaign=campaign,
                            channel=rate.channel,
                            service_rate=rate,
                            price=rate.price,
                            original_price=rate.price,
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
def campaign_create_step3_router(request):
    campaign_id = request.session.get("campaign_draft_id")

    if not campaign_id:
        return redirect("campaigns:campaign_create_step1")

    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile
    )

    content_slug = campaign.content_type.slug.lower()

    step3_page = request.session.get('step3_team_page', '1')

    if content_slug == "ready-content":
        return redirect("campaigns:campaign_create_step3_ready")
    elif content_slug == "content-production-team":
        url = reverse("campaigns:campaign_create_step3_team")
        return redirect(f"{url}?page={step3_page}")
    else:
        messages.error(request, "نوع محتوای کمپین معتبر نیست.")
        return redirect("campaigns:campaign_create_step1")


@login_required
def campaign_create_step3_team(request):
    """
    مرحله سوم ساخت کمپین - انتخاب تیم تولید محتوا و پلن
    پشتیبانی از حالت عادی و حالت جایگزینی
    """
    # ========== بررسی حالت جایگزینی ==========
    is_replacement_mode = request.GET.get('replacement_mode') == 'true'
    replacement_campaign_id = request.GET.get('campaign_id')

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

        rejected_team_id = None
        request.session.pop('replacement_campaign_id', None)
        request.session.pop('replacement_mode_team', None)
        existing_brief = None
        existing_content = None

    wallet_balance = request.user.wallet.balance
    existing_order = ContentOrder.objects.filter(campaign=campaign).select_related("plan", "team", "brief").first()
    attachments = existing_order.files.all() if existing_order else []

    # ========== دریافت تیم‌های دارای پلن فعال ==========
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
                ).select_related('service_type').order_by('price'),
                to_attr='active_plans_for_service'
            )
        )
        .annotate(
            total_points=Coalesce('score__points', Value(0, output_field=IntegerField())),
            total_completed_orders=Count('orders', filter=Q(orders__status='completed'), distinct=True)
        )
        .order_by('-total_points', '-total_completed_orders')
    )

    # ========== فیلتر تیم‌های رد شده در حالت جایگزینی ==========
    if is_replacement_mode:
        rejected_team_ids = list(
            campaign.content_orders.filter(
                status=ContentOrder.Status.CANCELLED
            ).values_list('team_id', flat=True)
        )
        if rejected_team_id and rejected_team_id not in rejected_team_ids:
            rejected_team_ids.append(rejected_team_id)
        if rejected_team_ids:
            teams_with_plans = teams_with_plans.exclude(id__in=rejected_team_ids)

        # فیلتر بر اساس موجودی کیف پول
        filtered_teams = []
        for team in teams_with_plans:
            if team.id in rejected_team_ids:
                continue
            plans = getattr(team, 'active_plans_for_service', [])
            valid_plans = [p for p in plans if p.price <= wallet_balance]
            if valid_plans:
                team.active_plans_for_service = valid_plans
                filtered_teams.append(team)
        teams_with_plans = filtered_teams

    # ========== صفحه‌بندی ==========
    paginator = Paginator(teams_with_plans, 21)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ========== انتخاب‌های قبلی (برای حالت ویرایش) ==========
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

    # ========== محاسبه محبوب‌ترین پلن‌ها ==========
    most_popular_map = {}
    all_plans = ContentServicePlan.objects.filter(
        team__in=teams_with_plans,
        service_type=service_type,
        is_active=True
    )
    for plan in all_plans:
        key = (plan.team_id, plan.service_type_id)
        completed_count = plan.orders.filter(
            status__in=[ContentOrder.Status.COMPLETED, ContentOrder.Status.DONE]
        ).count()
        if key not in most_popular_map or completed_count > most_popular_map[key]['count']:
            most_popular_map[key] = {'plan_id': plan.id, 'count': completed_count}

    most_popular_ids = [
        data['plan_id'] for data in most_popular_map.values() if data['count'] > 0
    ]

    # ========== ساختاردهی تیم‌ها با اطلاعات کامل پلن ==========
    teams_data = []
    for team in page_obj:
        plans = getattr(team, 'active_plans_for_service', [])
        if not plans:
            continue

        plan_list = []
        for plan in plans:
            # میانگین امتیاز پلن
            avg_rating = TeamReview.objects.filter(
                order__plan=plan,
                order__status__in=[ContentOrder.Status.COMPLETED, ContentOrder.Status.DONE]
            ).aggregate(avg=Avg('rating'))['avg']
            avg_rating = round(avg_rating, 1) if avg_rating else None

            features = plan.features
            if isinstance(features, str):
                try:
                    features = json.loads(features)
                except:
                    features = []
            elif not isinstance(features, list):
                features = []

            plan_list.append({
                'id': plan.id,
                'name': plan.name,
                'price': int(plan.price),
                'description': plan.description,
                'delivery_days': plan.estimated_delivery_days,
                'features': features,
                'service_type_icon': plan.service_type.icon or 'fi-star',
                'pricing_unit': plan.pricing_unit,
                'base_quantity': plan.base_quantity,
                'min_quantity': plan.min_quantity,
                'max_quantity': plan.max_quantity,
                'delivery_options_count': plan.delivery_options_count,
                'quantity_display': plan.quantity_display,
                'delivery_type_display': plan.delivery_type_display,
                'avg_rating': avg_rating,
                'is_most_popular': plan.id in most_popular_ids,
            })

        teams_data.append({
            'team': team,
            'plans': plan_list,
            'plans_json': json.dumps(plan_list, ensure_ascii=False),
            'first_plan_id': plan_list[0]['id'] if plan_list else None
        })

    # ========== پردازش POST ==========
    if request.method == "POST":
        if is_replacement_mode:
            # ===== حالت جایگزینی =====
            selected_plan_id = request.POST.get('selected_plan')
            if not selected_plan_id:
                messages.error(request, "لطفاً یک پلن تولید محتوا انتخاب کنید.")
                return redirect(request.path)

            try:
                selected_plan = ContentServicePlan.objects.get(id=selected_plan_id, is_active=True)
            except ContentServicePlan.DoesNotExist:
                messages.error(request, "پلن انتخاب شده معتبر نیست.")
                return redirect(request.path)

            new_price = selected_plan.price
            old_order = campaign.content_orders.first()
            old_price = old_order.price if old_order else 0
            wallet = request.user.wallet

            # ========== محاسبه مالیات با سرویس جدید ==========
            tax_result = calculate_replacement_tax(
                campaign=campaign,
                new_selected_cost=0,  # هزینه کانال‌ها تغییر نمی‌کنه
                new_content_cost=new_price  # ✅ هزینه جدید تیم محتوا
            )

            total_deduct = tax_result['total_deduct']

            # ========== بررسی موجودی کیف پول ==========
            if total_deduct > wallet.balance:
                error_parts = [
                    f"موجودی کیف پول شما ({wallet.balance:,} تومان) کافی نیست."
                ]
                for item in tax_result['breakdown']:
                    if not item.get('is_total'):
                        error_parts.append(f"{item['label']}: {item['formatted']} تومان")
                error_parts.append(f"مبلغ نهایی: {total_deduct:,} تومان")
                messages.error(request, "\n".join(error_parts))
                return redirect(request.path)

            with transaction.atomic():
                # ========== کسر مبلغ از کیف پول ==========
                if total_deduct > 0:
                    wallet.balance -= total_deduct
                    wallet.save(update_fields=['balance'])

                    # تراکنش برای هزینه تیم جدید
                    Transaction.objects.create(
                        user=request.user,
                        amount=new_price,
                        type=Transaction.Type.CAMPAIGN_PAYMENT,
                        status=Transaction.Status.SUCCESS,
                        campaign=campaign,
                        description=f"پرداخت تیم تولید محتوای جدید ({selected_plan.team.name}) در کمپین {campaign.name} (جایگزینی)",
                        reference_id=f"TEAM_NEW_PAYMENT_{campaign.id}_{timezone.now().timestamp()}"
                    )

                    # ✅ تراکنش برای مابه‌التفاوت کمیسیون (اگر مثبت)
                    if tax_result['commission_diff'] > 0:
                        Transaction.objects.create(
                            user=request.user,
                            amount=tax_result['commission_diff'],
                            type=Transaction.Type.CAMPAIGN_PAYMENT,
                            status=Transaction.Status.SUCCESS,
                            campaign=campaign,
                            description=f"پرداخت مابه‌التفاوت حق‌العمل (از {tax_result['old_data']['commission']:,} به {tax_result['new_data']['commission']:,} تومان)",
                            reference_id=f"COMMISSION_DIFF_TEAM_{campaign.id}_{timezone.now().timestamp()}"
                        )

                    # ✅ تراکنش برای مابه‌التفاوت مالیات (اگر مثبت)
                    if tax_result['vat_diff'] > 0:
                        Transaction.objects.create(
                            user=request.user,
                            amount=tax_result['vat_diff'],
                            type=Transaction.Type.CAMPAIGN_PAYMENT,
                            status=Transaction.Status.SUCCESS,
                            campaign=campaign,
                            description=f"پرداخت مابه‌التفاوت مالیات بر ارزش افزوده (از {tax_result['old_data']['total_vat']:,} به {tax_result['new_data']['total_vat']:,} تومان)",
                            reference_id=f"VAT_DIFF_TEAM_{campaign.id}_{timezone.now().timestamp()}"
                        )

                    # ✅ اگر مالیات کاهش پیدا کرده (تخفیف/کمک هزینه)
                    if tax_result['vat_diff'] < 0:
                        Transaction.objects.create(
                            user=request.user,
                            amount=abs(tax_result['vat_diff']),
                            type=Transaction.Type.CAMPAIGN_REFUND,
                            status=Transaction.Status.SUCCESS,
                            campaign=campaign,
                            description=f"کمک هزینه کاهش مالیات بر ارزش افزوده (از {tax_result['old_data']['total_vat']:,} به {tax_result['new_data']['total_vat']:,} تومان)",
                            reference_id=f"TAX_ADJUSTMENT_TEAM_{campaign.id}_{timezone.now().timestamp()}"
                        )

                # ========== آپدیت سفارش قدیمی ==========
                if old_order and old_order.status != ContentOrder.Status.CANCELLED:
                    old_order.status = ContentOrder.Status.CANCELLED
                    old_order.save(update_fields=['status'])

                # ========== ایجاد سفارش جدید ==========
                new_order = ContentOrder.objects.create(
                    campaign=campaign,
                    team=selected_plan.team,
                    plan=selected_plan,
                    price=new_price,
                    original_price=new_price,
                    selected_quantity=selected_plan.base_quantity,
                    status=ContentOrder.Status.PENDING
                )

                old_order.replaced_by = new_order
                old_order.replaced_at = timezone.now()
                old_order.save(update_fields=['replaced_by', 'replaced_at'])

                # ========== کپی بریف ==========
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

                # ========== کپی فایل‌های پیوست ==========
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

                # ========== اطمینان از وجود CampaignContent ==========
                campaign_content, created = CampaignContent.objects.get_or_create(campaign=campaign)
                if old_order and hasattr(old_order, 'brief') and not campaign_content.caption:
                    old_brief = old_order.brief
                    if hasattr(old_brief, 'ad_caption'):
                        campaign_content.caption = old_brief.ad_caption
                        campaign_content.link = old_brief.ad_link or ''
                        campaign_content.save(update_fields=['caption', 'link'])

                # ========== به‌روزرسانی فاکتور ==========
                if hasattr(campaign, 'invoice'):
                    invoice = create_campaign_invoice(campaign)

                    # ✅ حفظ کمیسیون قبلی (اگر جدید کمتر بود)
                    old_commission = tax_result['old_data']['commission']
                    if invoice.commission < old_commission:
                        invoice.commission = old_commission

                    # ✅ تنظیم مالیات جدید
                    new_vat = tax_result['new_data']['total_vat']
                    invoice.total_vat = new_vat

                    # ✅ محاسبه مجدد مبلغ قابل پرداخت
                    invoice.total_amount = invoice.influencer_cost + invoice.content_cost + invoice.commission
                    invoice.payable_amount = invoice.total_amount + invoice.total_vat

                    invoice.save(update_fields=[
                        'commission',
                        'total_vat',
                        'total_amount',
                        'payable_amount'
                    ])

                # ========== تغییر وضعیت کمپین ==========
                campaign.status = Campaign.Status.APPROVED
                campaign.replacement_mode = False
                campaign.content_team_rejected = False
                campaign.save(update_fields=['status', 'replacement_mode', 'content_team_rejected'])

                request.session.pop('replacement_campaign_id', None)
                request.session.pop('replacement_mode_team', None)

                # ========== پیام موفقیت ==========
                success_parts = [f"✅ تیم تولید محتوا با موفقیت تغییر کرد."]
                for item in tax_result['breakdown']:
                    if item.get('is_total'):
                        success_parts.append(f"💰 {item['label']}: {item['formatted']} تومان")
                    else:
                        success_parts.append(f"• {item['label']}: {item['formatted']} تومان")

                messages.success(request, "\n".join(success_parts))
                return redirect(campaign)

        else:
            # ===== حالت عادی =====
            team_form = CampaignStep3TeamForm(request.POST, service_type=service_type)
            brief_form = CampaignStep3BriefForm(request.POST, request.FILES)

            if team_form.is_valid() and brief_form.is_valid():
                selected_plan_id = team_form.cleaned_data['selected_plan']
                selected_plan = ContentServicePlan.objects.get(id=selected_plan_id)
                final_price = selected_plan.price

                order, created = ContentOrder.objects.get_or_create(
                    campaign=campaign,
                    defaults={
                        "team": selected_plan.team,
                        "plan": selected_plan,
                        "price": final_price,
                        "original_price": final_price,
                        "selected_quantity": selected_plan.base_quantity,
                        "status": ContentOrder.Status.PENDING,
                    }
                )
                if not created:
                    order.team = selected_plan.team
                    order.plan = selected_plan
                    order.price = final_price
                    order.original_price = final_price
                    order.selected_quantity = selected_plan.base_quantity
                    order.save()

                save_brief(order, brief_form)
                save_campaign_content(campaign, brief_form)

                handle_deleted_files(request.POST)
                if not handle_new_files(request, order):
                    return redirect("campaigns:campaign_create_step3_team")

                request.session['step3_team_page'] = request.GET.get('page', '1')
                return redirect("campaigns:campaign_create_step4")
            else:
                for form in (team_form, brief_form):
                    for errors in form.errors.values():
                        for err in errors:
                            messages.error(request, err)

    # ========== مقداردهی فرم‌ها برای GET ==========
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

    # ========== Context نهایی ==========
    context = {
        "campaign": campaign,
        'page_obj': page_obj,
        "service_type": service_type,
        'teams_data': teams_data,
        'most_popular_ids': most_popular_ids,
        "existing_order": existing_order,
        "team_form": team_form,
        "brief_form": brief_form,
        "attachments": attachments,
        "preselect_plan_id": preselect_plan_id,
        "preselect_team_id": preselect_team_id,
        "influencer_cost": sum(booking.price for booking in campaign.influencer_bookings.all()),
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

                # ✅ حذف کوپن تیم محتوا (چون سفارش محتوا حذف شده)
                if campaign.content_team_coupon:
                    campaign.content_team_coupon = None
                    campaign.save(update_fields=['content_team_coupon'])

                # ========== دریافت اطلاعات قبلی فاکتور ==========
                old_content_cost = 0
                old_commission = 0
                old_vat = 0
                old_influencer_cost = 0
                old_invoice = None

                if hasattr(campaign, 'invoice') and campaign.invoice:
                    old_invoice = campaign.invoice
                    old_content_cost = int(old_invoice.content_cost)
                    old_commission = int(old_invoice.commission)
                    old_vat = int(old_invoice.total_vat)
                    old_influencer_cost = int(old_invoice.influencer_cost)

                # ========== محاسبه دقیق هزینه‌های جدید ==========
                # هزینه ناشران جدید (همون قبلی)
                new_influencer_cost = old_influencer_cost

                # هزینه محتوا = ۰ (چون حذف میشه)
                new_content_cost = 0

                # کمیسیون = همون قبلی (تغییر نمیکنه)
                new_commission = old_commission

                # ========== محاسبه مالیات جدید با فرمول درست ==========
                # مالیات جدید = (هزینه ناشران + کمیسیون) × ۱۰٪
                # دقت: اینجا نباید هزینه محتوا رو حساب کنیم!
                tax_base = new_influencer_cost + new_commission
                new_vat = int(tax_base * 0.10)  # ۱۱,۴۰۰,۰۰۰ + ۱,۸۰۰,۰۰۰ = ۱۳,۲۰۰,۰۰۰ × ۰.۱۰ = ۱,۳۲۰,۰۰۰ ✅

                # ========== مابه‌التفاوت مالیات ==========
                vat_diff = new_vat - old_vat  # ۱,۳۲۰,۰۰۰ - ۱,۳۸۰,۰۰۰ = -۶۰,۰۰۰ ✅

                # ========== برگشت مبلغ به کیف پول کاربر ==========
                if vat_diff < 0:
                    refund_amount = abs(vat_diff)  # ۶۰,۰۰۰ ✅
                    wallet = request.user.wallet
                    wallet.balance += refund_amount
                    wallet.save(update_fields=['balance'])

                    Transaction.objects.create(
                        user=request.user,
                        amount=refund_amount,
                        type=Transaction.Type.CAMPAIGN_REFUND,
                        status=Transaction.Status.SUCCESS,
                        campaign=campaign,
                        invoice=old_invoice,
                        description=f'برگشت مابه‌التفاوت مالیات بابت حذف هزینه تولید محتوا (از {old_vat:,} به {new_vat:,} تومان)',
                        reference_id=f'TAX_REFUND_CONTENT_REMOVAL_{campaign.id}_{timezone.now().timestamp()}'
                    )

                # ========== به‌روزرسانی فاکتور ==========
                # ابتدا فاکتور رو با create_campaign_invoice به‌روز می‌کنیم
                invoice = create_campaign_invoice(campaign)

                # ========== سپس مقادیر درست رو روی فاکتور تنظیم می‌کنیم ==========
                invoice.influencer_cost = new_influencer_cost
                invoice.content_cost = new_content_cost  # ۰
                invoice.commission = new_commission
                invoice.total_vat = new_vat  # ۱,۳۲۰,۰۰۰ ✅
                invoice.total_amount = new_influencer_cost + new_content_cost + new_commission  # ۱۱,۴۰۰,۰۰۰ + ۰ + ۱,۸۰۰,۰۰۰ = ۱۳,۲۰۰,۰۰۰
                invoice.payable_amount = invoice.total_amount + new_vat  # ۱۳,۲۰۰,۰۰۰ + ۱,۳۲۰,۰۰۰ = ۱۴,۵۲۰,۰۰۰ ✅

                # اگه تخفیفی وجود داره، اعمال کن
                if invoice.discount_amount > 0:
                    invoice.payable_amount = max(invoice.payable_amount - invoice.discount_amount, 0)

                invoice.save(update_fields=[
                    'influencer_cost',
                    'content_cost',
                    'commission',
                    'total_vat',
                    'total_amount',
                    'payable_amount'
                ])

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
                return redirect(campaign)
            else:
                # ===== حالت عادی ساخت کمپین =====
                form.save()
                if campaign.is_free:
                    approve_campaign_by_admin(campaign)
                    if "campaign_draft_id" in request.session:
                        del request.session["campaign_draft_id"]
                    messages.success(request, "کمپین رایگان شما با موفقیت ثبت و تأیید شد.")
                    return redirect("advertisers:campaigns_list")
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

    # ========== پردازش POST ==========
    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "gateway")

        # ========== پرداخت از کیف پول ==========
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

                submit_campaign_for_review(campaign)

            del request.session["campaign_draft_id"]
            messages.success(request, "کمپین با موفقیت ثبت شد.")
            return redirect("advertisers:campaigns_list")

        # ========== پرداخت از درگاه (تغییر کرده) ==========
        else:
            try:
                # ========== شروع فرآیند پرداخت در زرین‌پال ==========
                payment_result, redirect_url = services.start_payment(
                    slug="zarinpal",
                    amount=invoice.payable_amount,
                    callback_url=request.build_absolute_uri(
                        reverse('payment:campaign_payment_callback')
                    ),
                    order_id=f"campaign_{campaign.id}_{int(timezone.now().timestamp())}",
                    description=f"پرداخت کمپین {campaign.name} - مبلغ {invoice.payable_amount:,} تومان",
                    mobile=request.user.phone_number,
                    email=request.user.email or '',
                )

                # ========== ذخیره اطلاعات در سشن ==========
                request.session['campaign_payment_authority'] = payment_result.authority
                request.session['campaign_payment_campaign_id'] = campaign.id
                request.session['campaign_payment_amount'] = invoice.payable_amount
                request.session['campaign_payment_invoice_id'] = invoice.id

                # ========== هدایت مستقیم به درگاه ==========
                return redirect(redirect_url)

            except Exception as e:
                messages.error(request, f"خطا در اتصال به درگاه پرداخت: {str(e)}")
                return redirect("campaigns:campaign_create_step4")

    # ========== GET ==========
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
        "discount_breakdown": {
            'influencer_discount': invoice.influencer_discount_amount,
            'content_discount': invoice.content_discount_amount,
            'platform_discount': invoice.platform_discount_amount,
            'base_influencer_cost': invoice.base_influencer_cost,
            'base_content_cost': invoice.base_content_cost,
            'base_commission': invoice.base_commission,
        },
        "invoice": invoice,
        "wallet": wallet,
        "campaign_content": campaign_content,
        "is_video": is_video,
        "step": 4,
        "total_steps": 4,
        "step_name": "پرداخت",
    }

    return render(request, "campaigns/forms/create_campaign_step4.html", context)
