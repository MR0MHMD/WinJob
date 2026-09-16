from influencers.models import ChannelServiceRate, ChannelBooking
from payment.services.create_invoice import create_campaign_invoice, sync_discounts_to_bookings
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

        existing_coupon_in_scope = getattr(campaign, scope_field_map[scope])
        if existing_coupon_in_scope:
            return JsonResponse({
                "success": False,
                "message": f"شما قبلاً از یک کد تخفیف برای این بخش استفاده کرده‌اید."
            }, status=400)

        all_existing_coupons = [
            campaign.influencer_coupon_id,
            campaign.content_team_coupon_id,
            campaign.platform_coupon_id
        ]

        try:
            coupon = Coupon.objects.get(code__iexact=code, scope=scope)
        except Coupon.DoesNotExist:
            return JsonResponse({"success": False, "message": "کد تخفیف معتبر نیست."}, status=404)

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

        # ========== اعمال کوپن ==========
        if scope == 'influencer':
            campaign.influencer_coupon = coupon
        elif scope == 'content_team':
            campaign.content_team_coupon = coupon
        else:
            campaign.platform_coupon = coupon

        campaign.save(update_fields=[scope_field_map[scope]])

        # ✅ ۱. اول تخفیف‌ها رو روی رزروها/سفارشات sync کن
        sync_discounts_to_bookings(campaign)

        # ✅ ۲. بعد فاکتور بساز (از original_price و discount_amount استفاده میکنه)
        invoice = create_campaign_invoice(campaign)

        return JsonResponse({
            "success": True,
            "message": "کد تخفیف با موفقیت اعمال شد.",
            "scope": scope,
            "coupon_code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": float(coupon.value),

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
        return JsonResponse({
            "success": False,
            "message": f"خطا در اعمال کد تخفیف: {str(e)}",
            "error": str(e)
        }, status=500)


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
    """محاسبه مابه‌التفاوت حق العمل و مالیات برای جایگزینی کانال‌ها"""
    try:
        body = json.loads(request.body)
        selected_rate_ids = body.get('rate_ids', [])
        campaign_id = body.get('campaign_id')

        if not campaign_id:
            return JsonResponse({'success': False, 'error': 'شناسه کمپین یافت نشد'}, status=400)

        campaign = get_object_or_404(Campaign, id=campaign_id, advertiser=request.user.advertiser_profile)

        selected_rates = ChannelServiceRate.objects.filter(id__in=selected_rate_ids, is_active=True)
        new_influencer_cost = sum(rate.price for rate in selected_rates)

        # ========== محاسبه با سرویس جدید ==========
        from payment.services.tax_calculator import calculate_replacement_tax

        tax_result = calculate_replacement_tax(
            campaign=campaign,
            new_selected_cost=new_influencer_cost
        )

        return JsonResponse({
            'success': True,
            # مبالغ اصلی
            'total_deduct': tax_result['total_deduct'],
            'total_deduct_formatted': f"{tax_result['total_deduct']:,}",

            # مابه‌التفاوت‌ها
            'commission_diff': tax_result['commission_diff'],
            'commission_to_pay': max(tax_result['commission_diff'], 0),
            'commission_diff_formatted': f"{tax_result['commission_diff']:,}",
            'vat_diff': tax_result['vat_diff'],
            'vat_diff_formatted': f"{tax_result['vat_diff']:,}",

            # هزینه‌ها
            'new_influencer_cost': new_influencer_cost,
            'new_influencer_cost_formatted': f"{new_influencer_cost:,}",
            'current_influencer_cost': tax_result['old_data']['influencer_cost'],
            'old_commission': tax_result['old_data']['commission'],
            'new_commission': tax_result['new_data']['commission'],
            'old_vat': tax_result['old_data']['total_vat'],
            'new_vat': tax_result['new_data']['total_vat'],

            # جزییات نمایشی
            'breakdown': tax_result['breakdown'],
            'selected_count': len(selected_rate_ids),
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def calculate_team_replacement_commission(request):
    """محاسبه مابه‌التفاوت حق العمل و مالیات برای جایگزینی تیم محتوا"""
    try:
        body = json.loads(request.body)
        plan_id = body.get('plan_id')
        campaign_id = body.get('campaign_id')

        if not campaign_id or not plan_id:
            return JsonResponse({'success': False, 'error': 'اطلاعات ناقص است'}, status=400)

        campaign = get_object_or_404(Campaign, id=campaign_id, advertiser=request.user.advertiser_profile)

        try:
            plan = ContentServicePlan.objects.get(id=plan_id, is_active=True)
        except ContentServicePlan.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'پلن یافت نشد'}, status=404)

        new_price = plan.price

        # ========== محاسبه با سرویس جدید ==========
        from payment.services.tax_calculator import calculate_replacement_tax

        tax_result = calculate_replacement_tax(
            campaign=campaign,
            new_selected_cost=0,
            new_content_cost=new_price
        )

        return JsonResponse({
            'success': True,
            'total_deduct': tax_result['total_deduct'],
            'total_deduct_formatted': f"{tax_result['total_deduct']:,}",
            'commission_diff': tax_result['commission_diff'],
            'commission_diff_formatted': f"{tax_result['commission_diff']:,}",
            'vat_diff': tax_result['vat_diff'],
            'vat_diff_formatted': f"{tax_result['vat_diff']:,}",
            'new_price': new_price,
            'new_price_formatted': f"{new_price:,}",
            'old_price': tax_result['old_data']['content_cost'],
            'old_commission': tax_result['old_data']['commission'],
            'new_commission': tax_result['new_data']['commission'],
            'old_vat': tax_result['old_data']['total_vat'],
            'new_vat': tax_result['new_data']['total_vat'],
            'breakdown': tax_result['breakdown'],
            'is_refund': tax_result['is_refund'],
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_campaign_tax_info(request, campaign_id):
    """دریافت اطلاعات مالیاتی کمپین برای نمایش در مودال"""
    try:
        campaign = get_object_or_404(
            Campaign,
            id=campaign_id,
            advertiser=request.user.advertiser_profile
        )

        if hasattr(campaign, 'invoice') and campaign.invoice:
            invoice = campaign.invoice

            # ========== دریافت ناشران رد شده ==========
            rejected_channels = campaign.influencer_bookings.filter(
                status=ChannelBooking.Status.REJECTED
            ).select_related('channel')

            rejected_channels_data = [
                {
                    'channel_name': ch.channel.channel_name,
                    'price': ch.price
                }
                for ch in rejected_channels
            ]

            # ========== محاسبه هزینه ناشران جدید (بدون ناشران رد شده) ==========
            # هزینه فعلی ناشران در فاکتور
            current_influencer_cost = invoice.influencer_cost

            # جمع قیمت ناشران رد شده
            rejected_total = sum(ch.price for ch in rejected_channels)

            # هزینه جدید = هزینه فعلی - قیمت ناشران رد شده
            new_influencer_cost = max(current_influencer_cost - rejected_total, 0)

            return JsonResponse({
                'success': True,
                'content_cost': int(invoice.content_cost),
                'content_vat': int(invoice.content_vat),
                'influencer_cost': int(invoice.influencer_cost),
                'commission': int(invoice.commission),
                'total_vat': int(invoice.total_vat),
                'total_amount': int(invoice.total_amount),
                'payable_amount': int(invoice.payable_amount),
                'new_influencer_cost': int(new_influencer_cost),
                'rejected_channels': rejected_channels_data,
                'rejected_total': int(rejected_total),
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'فاکتوری برای این کمپین وجود ندارد'
            }, status=404)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
