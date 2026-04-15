from campaigns.models import CampaignInvoice, Coupon

PLATFORM_COMMISSION = 0.15


def create_campaign_invoice(campaign):
    influencer_bookings = campaign.influencer_bookings.select_related(
        "channel__influencer"
    )

    # ✅ استفاده از sum() پایتون
    influencer_cost = sum(booking.price for booking in influencer_bookings)

    content_orders = campaign.content_orders.select_related("team")

    # ✅ استفاده از sum() پایتون
    content_cost = sum(order.price for order in content_orders)

    subtotal = influencer_cost + content_cost

    commission = int(subtotal * PLATFORM_COMMISSION)

    coupon = campaign.coupon

    discount_amount = 0

    # ----------------------------
    # Coupon Logic
    # ----------------------------

    if coupon and coupon.is_valid():

        # ========================
        # Influencer Discount
        # ========================

        if coupon.scope == Coupon.Scope.INFLUENCER:

            if coupon.influencer:

                target_amount = sum(
                    booking.price
                    for booking in influencer_bookings
                    if booking.channel.influencer_id == coupon.influencer_id
                )

            else:
                target_amount = influencer_cost

            discount_amount = coupon.calculate_discount(target_amount)

        # ========================
        # Content Team Discount
        # ========================

        elif coupon.scope == Coupon.Scope.CONTENT_TEAM:

            if coupon.team:

                target_amount = sum(
                    order.price
                    for order in content_orders
                    if order.team_id == coupon.team_id
                )

            else:
                target_amount = content_cost

            discount_amount = coupon.calculate_discount(target_amount)

        # ========================
        # Platform Discount
        # ========================

        elif coupon.scope == Coupon.Scope.PLATFORM:

            discount_amount = coupon.calculate_discount(commission)

    # ----------------------------
    # Totals
    # ----------------------------

    total_amount = subtotal + commission

    # ✅ استفاده از max() پایتون
    payable_amount = max(total_amount - discount_amount, 0)

    invoice, created = CampaignInvoice.objects.get_or_create(
        campaign=campaign,
        defaults={
            "influencer_cost": influencer_cost,
            "content_cost": content_cost,
            "commission": commission,
            "discount_amount": discount_amount,
            "total_amount": total_amount,
            "payable_amount": payable_amount,
        }
    )

    if not created:
        invoice.influencer_cost = influencer_cost
        invoice.content_cost = content_cost
        invoice.commission = commission
        invoice.discount_amount = discount_amount
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

    return invoice