from campaigns.models import CampaignInvoice, CampaignInfluencer
from content_team.models import ContentOrder

PLATFORM_COMMISSION = 0.15


def create_campaign_invoice(campaign):
    influencer_bookings = campaign.influencer_bookings.exclude(
        status__in=[
            CampaignInfluencer.Status.REJECTED,
            CampaignInfluencer.Status.REPLACED
        ]
    ).select_related("channel__influencer")

    influencer_cost = sum(booking.price for booking in influencer_bookings)

    content_orders = campaign.content_orders.exclude(
        status=ContentOrder.Status.CANCELLED
    ).select_related("team")
    content_cost = sum(order.price for order in content_orders)

    subtotal = influencer_cost + content_cost
    commission = int(subtotal * PLATFORM_COMMISSION)

    total_discount = 0
    discount_breakdown = {
        'influencer_discount': 0,
        'content_discount': 0,
        'platform_discount': 0
    }

    if campaign.influencer_coupon and campaign.influencer_coupon.is_valid():
        coupon = campaign.influencer_coupon

        if coupon.channel:
            target_amount = sum(
                booking.price
                for booking in influencer_bookings
                if booking.channel_id == coupon.channel_id
            )
        else:
            target_amount = influencer_cost

        discount = coupon.calculate_discount(target_amount)
        discount_breakdown['influencer_discount'] = discount
        total_discount += discount

    # Content Team Coupon
    if campaign.content_team_coupon and campaign.content_team_coupon.is_valid():
        coupon = campaign.content_team_coupon

        if coupon.team:
            target_amount = sum(
                order.price
                for order in content_orders
                if order.team_id == coupon.team_id
            )
        else:
            target_amount = content_cost

        discount = coupon.calculate_discount(target_amount)
        discount_breakdown['content_discount'] = discount
        total_discount += discount

    # Platform Coupon
    if campaign.platform_coupon and campaign.platform_coupon.is_valid():
        coupon = campaign.platform_coupon
        discount = coupon.calculate_discount(commission)
        discount_breakdown['platform_discount'] = discount
        total_discount += discount

    # Totals
    total_amount = subtotal + commission
    payable_amount = max(total_amount - total_discount, 0)

    invoice, created = CampaignInvoice.objects.get_or_create(
        campaign=campaign,
        defaults={
            "influencer_cost": influencer_cost,
            "content_cost": content_cost,
            "commission": commission,
            "discount_amount": total_discount,
            "total_amount": total_amount,
            "payable_amount": payable_amount,
        }
    )

    if not created:
        invoice.influencer_cost = influencer_cost
        invoice.content_cost = content_cost
        invoice.commission = commission
        invoice.discount_amount = total_discount
        invoice.total_amount = total_amount
        invoice.payable_amount = payable_amount

        invoice.save(
            update_fields=[
                "influencer_cost",
                "content_cost",
                "commission",
                "discount_amount",
                "total_amount",
                "payable_amount",
            ]
        )

    invoice.discount_breakdown = discount_breakdown

    return invoice
