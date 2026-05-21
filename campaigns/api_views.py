from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

from campaigns.models import Campaign
from content_team.models import ContentServicePlan


@require_POST
@login_required
def campaign_step2_calculate_price(request):
    """
    AJAX endpoint — جمع قیمت سرویس‌های انتخاب شده
    """
    try:
        body = json.loads(request.body)
        rate_ids = body.get('service_rate_ids', [])

        if not rate_ids:
            return JsonResponse({
                'total': 0,
                'breakdown': [],
                'formatted': '۰'
            })

        from influencers.models import InfluencerServiceRate

        rates = (
            InfluencerServiceRate.objects
            .select_related(
                'channel',
                'channel__influencer',
                'ad_type'
            )
            .filter(id__in=rate_ids, is_active=True)
        )

        total = sum(r.price for r in rates)

        breakdown = [
            {
                'name': f"{r.channel.channel_name}",
                'price': int(r.price),
                'formatted': f"{int(r.price):,}"
            }
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

    if content_slug == "ready-content":
        return redirect("campaigns:campaign_create_step3_ready")

    elif content_slug == "content-production-team":
        return redirect("campaigns:campaign_create_step3_team")

    else:
        messages.error(request, "نوع محتوای کمپین معتبر نیست.")
        return redirect("campaigns:campaign_create_step1")


@login_required
def api_content_team_rates(request):
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
    try:
        body = json.loads(request.body)
        code = body.get("code", "").strip()
        scope = body.get("scope", "")

        if not code:
            return JsonResponse(
                {"success": False, "message": "کد تخفیف وارد نشده است."},
                status=400
            )

        if scope not in ['influencer', 'content_team', 'platform']:
            return JsonResponse(
                {"success": False, "message": "نوع تخفیف نامعتبر است."},
                status=400
            )

        campaign_id = request.session.get("campaign_draft_id")

        if not campaign_id:
            return JsonResponse(
                {"success": False, "message": "کمپین یافت نشد."},
                status=400
            )

        from campaigns.models import Campaign, Coupon
        from campaigns.services import create_campaign_invoice
        from django.utils import timezone

        campaign = Campaign.objects.filter(
            id=campaign_id,
            advertiser=request.user.advertiser_profile
        ).first()

        if not campaign:
            return JsonResponse(
                {"success": False, "message": "کمپین یافت نشد."},
                status=404
            )

        # Check if already has coupon for this scope
        scope_field_map = {
            'influencer': 'influencer_coupon_id',
            'content_team': 'content_team_coupon_id',
            'platform': 'platform_coupon_id'
        }

        existing_coupon = getattr(campaign, scope_field_map[scope])
        if existing_coupon:
            return JsonResponse({
                "success": False,
                "message": f"شما قبلاً از یک کد تخفیف {dict(Coupon.Scope.choices)[scope]} استفاده کرده‌اید."
            }, status=400)

        try:
            coupon = Coupon.objects.get(code__iexact=code, scope=scope)
        except Coupon.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "کد تخفیف معتبر نیست."},
                status=404
            )

        # Basic validation
        if not coupon.is_valid():
            return JsonResponse(
                {"success": False, "message": "این کد تخفیف قابل استفاده نیست."},
                status=400
            )

        # Check if user has used this coupon in other campaigns
        user_coupon_used = Campaign.objects.filter(
            advertiser=request.user.advertiser_profile,
            **{f"{scope_field_map[scope]}": coupon}
        ).exclude(
            id=campaign_id
        ).exclude(
            status__in=[Campaign.Status.CANCELLED]
        ).exists()

        if user_coupon_used:
            return JsonResponse({
                "success": False,
                "message": "شما قبلاً در یک کمپین دیگر از این کد تخفیف استفاده کرده‌اید."
            }, status=400)

        # Scope-specific validation
        influencer_bookings = campaign.influencer_bookings.select_related(
            "channel__influencer"
        )
        content_orders = campaign.content_orders.select_related("team")

        if coupon.scope == Coupon.Scope.INFLUENCER:
            if coupon.channel:
                exists = influencer_bookings.filter(
                    channel_id=coupon.channel_id
                ).exists()

                if not exists:
                    return JsonResponse({
                        "success": False,
                        "message": "این کد تخفیف مربوط به اینفلوئنسر دیگری است."
                    }, status=400)

        elif coupon.scope == Coupon.Scope.CONTENT_TEAM:
            if coupon.team:
                exists = content_orders.filter(
                    team_id=coupon.team_id
                ).exists()

                if not exists:
                    return JsonResponse({
                        "success": False,
                        "message": "این کد تخفیف مربوط به تیم محتوای دیگری است."
                    }, status=400)

        # Apply coupon to campaign
        if scope == 'influencer':
            campaign.influencer_coupon = coupon
        elif scope == 'content_team':
            campaign.content_team_coupon = coupon
        else:  # platform
            campaign.platform_coupon = coupon

        campaign.save(update_fields=[scope_field_map[scope]])

        # Recalculate invoice
        invoice = create_campaign_invoice(campaign)
        discount_breakdown = getattr(invoice, 'discount_breakdown', {
            'influencer_discount': 0,
            'content_discount': 0,
            'platform_discount': 0
        })

        return JsonResponse({
            "success": True,
            "message": "کد تخفیف با موفقیت اعمال شد.",
            "scope": scope,
            "coupon_code": coupon.code,

            "discount_type": coupon.discount_type,
            "discount_value": float(coupon.value),

            "discount_amount": invoice.discount_amount,
            "discount_amount_formatted": f"{invoice.discount_amount:,}",

            "discount_breakdown": discount_breakdown,

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
        import traceback
        traceback.print_exc()

        return JsonResponse(
            {"error": str(e)},
            status=500
        )
