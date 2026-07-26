from influencers.models import ChannelServiceRate, ChannelBooking
from payment.services.create_invoice import create_campaign_invoice
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from content_team.models import ContentServicePlan
from django.http import JsonResponse
from django.contrib import messages
from payment.models import Coupon
from django.db.models import Sum
from ..models import Campaign
import traceback
import json


@require_POST
@login_required
def campaign_step2_calculate_price(request):
    """AJAX endpoint — جمع قیمت سرویس‌های انتخاب شده"""
    try:
        body = json.loads(request.body)
        rate_ids = body.get('service_rate_ids', [])

        if not rate_ids:
            return JsonResponse({'total': 0, 'breakdown': [], 'formatted': '۰'})

        rates = ChannelServiceRate.objects.select_related(
            'channel', 'channel__influencer', 'ad_type'
        ).filter(id__in=rate_ids, is_active=True)

        total = sum(r.price for r in rates)
        breakdown = [
            {'name': f"{r.channel.channel_name}", 'price': int(r.price), 'formatted': f"{int(r.price):,}"}
            for r in rates
        ]

        return JsonResponse({
            'total': int(total),
            'formatted': f"{int(total):,}",
            'breakdown': breakdown,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_content_team_rates(request):
    """دریافت قیمت‌های تیم‌های تولید محتوا"""
    service_type = request.GET.get("service_type")
    minutes = request.GET.get("minutes")

    try:
        service_type = int(service_type)
    except:
        return JsonResponse({"rates": []})

    minutes = int(minutes) if minutes else 1

    rates = ContentServicePlan.objects.filter(
        service_type_id=service_type,
        is_available=True,
        team__is_active=True
    ).select_related("team", "service_type")

    data = []
    for rate in rates:
        if rate.service_type.unit == "minute":
            final_price = rate.price_per_unit * minutes
        else:
            final_price = rate.price_per_unit

        data.append({
            "id": rate.id,
            "team": rate.team.name,
            "logo": rate.team.logo.url if rate.team.logo else "",
            "price": int(final_price),
            "base_price": int(rate.price_per_unit),
            "unit": rate.service_type.unit,
        })

    return JsonResponse({"rates": data})


@require_POST
@login_required
def apply_discount_code(request):
    """اعمال کد تخفیف"""
    try:
        body = json.loads(request.body)
        code = body.get("code", "").strip()
        scope = body.get("scope", "")

        if not code:
            return JsonResponse({"success": False, "message": "کد تخفیف وارد نشده است."}, status=400)

        if scope not in ['influencer', 'content_team', 'platform']:
            return JsonResponse({"success": False, "message": "نوع تخفیف نامعتبر است."}, status=400)

        campaign_id = request.session.get("campaign_draft_id")
        if not campaign_id:
            return JsonResponse({"success": False, "message": "کمپین یافت نشد."}, status=400)

        campaign = Campaign.objects.filter(
            id=campaign_id, advertiser=request.user.advertiser_profile
        ).first()

        if not campaign:
            return JsonResponse({"success": False, "message": "کمپین یافت نشد."}, status=404)

        scope_field_map = {
            'influencer': 'influencer_coupon_id',
            'content_team': 'content_team_coupon_id',
            'platform': 'platform_coupon_id'
        }

        # ==== چک کردن کوپن‌های موجود در کل کمپین ====
        existing_coupon_in_scope = getattr(campaign, scope_field_map[scope])
        if existing_coupon_in_scope:
            return JsonResponse({
                "success": False,
                "message": f"شما قبلاً از یک کد تخفیف برای این بخش استفاده کرده‌اید."
            }, status=400)

        # چک کردن اینکه این کوپن در هیچ اسکوپی قبلاً استفاده نشده باشد
        all_existing_coupons = [
            campaign.influencer_coupon_id,
            campaign.content_team_coupon_id,
            campaign.platform_coupon_id
        ]

        try:
            coupon = Coupon.objects.get(code__iexact=code, scope=scope)
        except Coupon.DoesNotExist:
            return JsonResponse({"success": False, "message": "کد تخفیف معتبر نیست."}, status=404)

        # اگر کوپن قبلاً در یکی از سه فیلد دیگر استفاده شده، خطا بده
        if coupon.id in all_existing_coupons:
            return JsonResponse({
                "success": False,
                "message": "این کد تخفیف قبلاً در یکی از بخش‌های دیگر کمپین استفاده شده است."
            }, status=400)

        if not coupon.is_valid():
            return JsonResponse({
                "success": False,
                "message": "این کد تخفیف قابل استفاده نیست (منقضی شده یا استفاده شده)."
            }, status=400)

        user_coupon_used = Campaign.objects.filter(
            advertiser=request.user.advertiser_profile,
            **{f"{scope_field_map[scope]}": coupon}
        ).exclude(id=campaign_id).exclude(status__in=[Campaign.Status.DRAFT, Campaign.Status.CANCELLED]).exists()

        if user_coupon_used:
            return JsonResponse({
                "success": False,
                "message": "شما قبلاً در یک کمپین دیگر از این کد تخفیف استفاده کرده‌اید."
            }, status=400)

        # اعمال کوپن
        if scope == 'influencer':
            campaign.influencer_coupon = coupon
        elif scope == 'content_team':
            campaign.content_team_coupon = coupon
        else:
            campaign.platform_coupon = coupon

        campaign.save(update_fields=[scope_field_map[scope]])

        invoice = create_campaign_invoice(campaign)

        return JsonResponse({
            "success": True,
            "message": "کد تخفیف با موفقیت اعمال شد.",
            "scope": scope,
            "coupon_code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": float(coupon.value),

            # ==== اطلاعات جدید ====
            "base_influencer_cost": invoice.base_influencer_cost,
            "base_content_cost": invoice.base_content_cost,
            "base_commission": invoice.base_commission,
            "influencer_discount_amount": invoice.influencer_discount_amount,
            "content_discount_amount": invoice.content_discount_amount,
            "platform_discount_amount": invoice.platform_discount_amount,

            "discount_amount": invoice.discount_amount,
            "discount_amount_formatted": f"{invoice.discount_amount:,}",
            "payable_amount": invoice.payable_amount,
            "payable_amount_formatted": f"{invoice.payable_amount:,}",
            "final_total": invoice.total_amount,
            "final_total_formatted": f"{invoice.total_amount:,}",
            "commission": invoice.commission,
            "commission_formatted": f"{invoice.commission:,}",
            "influencer_cost": invoice.influencer_cost,
            "influencer_cost_formatted": f"{invoice.influencer_cost:,}",
            "content_cost": invoice.content_cost,
            "content_cost_formatted": f"{invoice.content_cost:,}",
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_POST
def campaign_delete(request, campaign_id):
    """حذف کمپین پیش‌نویس"""
    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile,
        status=Campaign.Status.DRAFT
    )
    campaign.delete()
    messages.success(request, "کمپین با موفقیت حذف شد.")
    return redirect('advertisers:campaigns_list')


@login_required
@require_POST
def calculate_influencer_replacement_commission(request):
    """محاسبه مابه‌التفاوت حق العمل برای جایگزینی کانال‌ها"""
    try:
        body = json.loads(request.body)
        selected_rate_ids = body.get('rate_ids', [])
        campaign_id = body.get('campaign_id')

        if not campaign_id:
            return JsonResponse({'success': False, 'error': 'شناسه کمپین یافت نشد'}, status=400)

        campaign = get_object_or_404(Campaign, id=campaign_id, advertiser=request.user.advertiser_profile)

        current_influencer_cost = campaign.influencer_bookings.exclude(
            status__in=[ChannelBooking.Status.REJECTED, ChannelBooking.Status.REPLACED]
        ).aggregate(total=Sum('price'))['total'] or 0

        selected_rates = ChannelServiceRate.objects.filter(id__in=selected_rate_ids, is_active=True)
        new_influencer_cost = sum(rate.price for rate in selected_rates)

        content_cost = campaign.invoice.content_cost if hasattr(campaign, 'invoice') and campaign.invoice else 0

        from payment.services.create_invoice import PLATFORM_COMMISSION

        old_commission = campaign.invoice.commission if hasattr(campaign, 'invoice') and campaign.invoice else 0
        if old_commission == 0:
            old_subtotal = int(current_influencer_cost) + int(content_cost)
            old_commission = int(old_subtotal * PLATFORM_COMMISSION)

        new_total_influencer_cost = int(current_influencer_cost) + int(new_influencer_cost)
        new_subtotal = new_total_influencer_cost + int(content_cost)
        new_commission = int(new_subtotal * PLATFORM_COMMISSION)

        commission_diff = max(new_commission - old_commission, 0)
        total_deduct = int(new_influencer_cost) + commission_diff

        return JsonResponse({
            'success': True,
            'current_influencer_cost': int(current_influencer_cost),
            'new_influencer_cost': int(new_influencer_cost),
            'old_commission': old_commission,
            'new_commission': new_commission,
            'commission_diff': commission_diff,
            'total_deduct': total_deduct,
            'total_deduct_formatted': f"{total_deduct:,}",
            'commission_diff_formatted': f"{commission_diff:,}",
            'new_influencer_cost_formatted': f"{int(new_influencer_cost):,}",
            'selected_count': len(selected_rate_ids),
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
