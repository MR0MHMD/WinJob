from ..models import Campaign, CampaignInfluencer, ContentType
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from content_team.models import ContentOrder
from django.contrib import messages
from django.db import transaction
from django.urls import reverse



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
        return redirect(campaign)

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
        return redirect(campaign)

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
        return redirect(campaign)

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
            return redirect(campaign)

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
        return redirect(campaign)

    if campaign.content_type.slug != "ready-content":
        messages.warning(request, "نوع محتوای کمپین آماده نیست.")
        return redirect(campaign)

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
    return redirect(campaign)


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
        return redirect(campaign)

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

        messages.success(
            request,
            f"✅ کمپین با موفقیت ادامه یافت. {rejected_count} ناشر رد شده نادیده گرفته شدند."
        )

        return redirect(campaign)
