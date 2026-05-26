from .models import CampaignClick, CampaignInfluencer, Campaign, Payment
from django.shortcuts import redirect, get_object_or_404, render
from content_team.models import ContentOrder, ContentOrderFile, ContentTeam
from django.contrib.auth.decorators import login_required
from influencers.models import InfluencerServiceRate
from accounts.models import Transaction
from .services.campaigns_notifications import submit_campaign_for_review
from .services.create_invoice import create_campaign_invoice
from .utils import _detect_file_type
from django.db.models import Prefetch
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, F
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

    if not campaign_id:
        return redirect('campaigns:campaign_create_step1')

    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile
    )

    platform = campaign.platform
    ad_type = campaign.ad_type

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
            'channel__city',
            'channel__category'
        )
    )

    filter_form = InfluencerFilterForm(request.GET or None)

    rates = base_queryset

    if filter_form.is_valid():

        search = filter_form.cleaned_data.get("search")
        category = filter_form.cleaned_data.get("category")
        province = filter_form.cleaned_data.get("province")
        city = filter_form.cleaned_data.get("city")
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

        if city:
            rates = rates.filter(channel__city=city)

        if followers_min is not None:
            rates = rates.filter(channel__followers_count__gte=followers_min)

        if followers_max is not None:
            rates = rates.filter(channel__followers_count__lte=followers_max)

        if price_min is not None:
            rates = rates.filter(price__gte=price_min)

        if price_max is not None:
            rates = rates.filter(price__lte=price_max)

    rates = rates.order_by("-channel__followers_count")

    prev_selected = list(
        campaign.influencer_bookings
        .values_list('service_rate_id', flat=True)
    )

    if request.method == "POST":

        selected_rates = request.POST.getlist("rates")

        if not selected_rates:
            messages.error(request, "حداقل یک سرویس اینفلوئنسر انتخاب کنید.")
        else:

            selected_rates_qs = base_queryset.filter(id__in=selected_rates)

            if not selected_rates_qs.exists():
                messages.error(request, "انتخاب نامعتبر است.")
                return redirect(request.path)

            CampaignInfluencer.objects.filter(
                campaign=campaign
            ).delete()

            for rate in selected_rates_qs:
                CampaignInfluencer.objects.create(
                    campaign=campaign,
                    channel=rate.channel,
                    service_rate=rate,
                    price=rate.price
                )

            return redirect('campaigns:campaign_create_step3')

    print("prev_selected:", prev_selected)  # در ترمینال لاگ می‌شود

    context = {
        "campaign": campaign,
        "rates": rates,
        "prev_selected": prev_selected,
        "platform": platform,
        "filter_form": filter_form,
        "step": 2,
        "total_steps": 4,
    }

    return render(request, "campaigns/forms/create_campaign_step2.html", context)


@login_required
def campaign_create_step3_team(request):
    # ------------------------
    # Helpers
    # ------------------------
    def safe_load_json(value):
        try:
            return json.loads(value) if value else []
        except json.JSONDecodeError:
            return []

    def calculate_price(rate, minutes):
        if service_type.unit == "minute" and minutes:
            return rate.price_per_unit * int(minutes)
        return rate.price_per_unit

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
        """ذخیره کپشن و لینک در CampaignContent"""
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

    # ------------------------ کمپین و سرویس ------------------------
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

    minutes = request.session.get("content_minutes")  # فقط برای سرویس‌های دقیقه‌ای

    # ------------------------ اطلاعات موجود (در صورت ویرایش) ------------------------
    existing_order = ContentOrder.objects.filter(campaign=campaign).select_related("plan", "team", "brief").first()
    attachments = existing_order.files.all() if existing_order else []

    # ------------------------ تیم‌های دارای پلن برای این سرویس ------------------------
    # گرفتن همه تیم‌هایی که حداقل یک پلن فعال برای این سرویس دارن
    teams_with_plans = ContentTeam.objects.filter(
        service_plans__service_type=service_type,
        service_plans__is_active=True,
        is_active=True
    ).distinct().prefetch_related(
        Prefetch(
            'service_plans',
            queryset=ContentServicePlan.objects.filter(
                service_type=service_type,
                is_active=True
            ).select_related('service_type').order_by('price_per_unit'),  # <-- اینجا select_related اضافه شد
            to_attr='active_plans_for_service'
        )
    )

    # در تابع campaign_create_step3_team، بعد از خطوط اولیه و قبل از ساختن teams_data
    # ========== اضافه کردن قابلیت انتخاب خودکار از طریق GET ==========
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
    else:
        preselect_plan_id = None

    # ... داخل ویو، بعد از گرفتن teams_with_plans
    teams_data = []
    for team in teams_with_plans:
        plans = getattr(team, 'active_plans_for_service', [])
        if plans:
            plan_prices = []
            for plan in plans:
                # محاسبه قیمت نهایی
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
                'plans_json': json.dumps(plan_prices, ensure_ascii=False)  # برای استفاده در data attribute
            })

    # ------------------------ پردازش POST ------------------------
    if request.method == "POST":
        team_form = CampaignStep3TeamForm(request.POST, service_type=service_type)
        brief_form = CampaignStep3BriefForm(request.POST, request.FILES)

        if team_form.is_valid() and brief_form.is_valid():
            selected_plan_id = team_form.cleaned_data['selected_plan']
            selected_plan = ContentServicePlan.objects.get(id=selected_plan_id)

            # محاسبه قیمت نهایی
            if service_type.unit == "minute" and minutes:
                final_price = selected_plan.price_per_unit * int(minutes)
            else:
                final_price = selected_plan.price_per_unit

            # ایجاد یا بروزرسانی ContentOrder
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

            # ذخیره بریف
            save_brief(order, brief_form)  # همان تابع قبلی

            # ذخیره محتوای تبلیغ (caption و link) در CampaignContent
            save_campaign_content(campaign, brief_form)  # همان تابع قبلی

            # مدیریت فایل‌های پیوست
            handle_deleted_files(request.POST)
            if not handle_new_files(request, order):
                return redirect("campaigns:campaign_create_step3_team")

            return redirect("campaigns:campaign_create_step4")

        else:
            for form in (team_form, brief_form):
                for errors in form.errors.values():
                    for err in errors:
                        messages.error(request, err)

    # ------------------------ GET (بارگذاری اولیه) ------------------------
    else:
        initial_plan = existing_order.plan.id if existing_order else None

        if existing_order:
            preselect_plan_id = existing_order.plan.id
            preselect_team_id = existing_order.team.id
        else:
            preselect_plan_id = None
            preselect_team_id = None


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
        # بارگذاری caption و link از CampaignContent
        if hasattr(campaign, 'content') and campaign.content:
            brief_initial['ad_caption'] = campaign.content.caption
            brief_initial['ad_link'] = campaign.content.link or ''

        brief_form = CampaignStep3BriefForm(initial=brief_initial)

    # ------------------------ کانتکست ------------------------
    context = {
        "campaign": campaign,
        "service_type": service_type,
        "teams_data": teams_data,
        "minutes": minutes,
        "existing_order": existing_order,
        "team_form": team_form,
        "brief_form": brief_form,
        "attachments": attachments,
        "preselect_plan_id": preselect_plan_id,
        "preselect_team_id": preselect_team_id,
        "step": 3,
        "total_steps": 4,
        "step_name": "انتخاب تیم و پلن تولید محتوا",
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

    if campaign.content_type.slug != "ready-content":
        return redirect("campaigns:campaign_create_step3")

    content, created = CampaignContent.objects.get_or_create(campaign=campaign)

    if request.method == "POST":
        form = CampaignStep3ReadyForm(
            request.POST,
            request.FILES,
            instance=content
        )

        if form.is_valid():
            form.save()
            return redirect("campaigns:campaign_create_step4")
        else:
            # برای دیباگ - میتونی خطاها رو لاگ کنی
            print(form.errors)

    else:
        form = CampaignStep3ReadyForm(instance=content)

    context = {
        "campaign": campaign,
        "form": form,
        "existing_media": content.media.url if content.media else None,
        "step": 3,
        "total_steps": 4,
        "step_name": "آپلود محتوای تبلیغ",
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

                # افزایش تعداد استفاده برای هر سه نوع کوپن
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

    destination_url = content.get_utm_link(influencer)

    return redirect(destination_url)
