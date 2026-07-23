from campaigns.models import CampaignInfluencer
from payment.models import CampaignInvoice
from content_team.models import ContentOrder

PLATFORM_COMMISSION = 0.15


def create_campaign_invoice(campaign):
    # ============================================================
    # ۱. محاسبه هزینه‌های پایه (قبل از هرگونه تخفیف)
    # ============================================================

    # محاسبه هزینه پایه ناشران
    influencer_bookings = campaign.influencer_bookings.exclude(
        status__in=[
            CampaignInfluencer.Status.REJECTED,
            CampaignInfluencer.Status.REPLACED
        ]
    ).select_related("channel__influencer")
    base_influencer_cost = sum(booking.price for booking in influencer_bookings)

    # محاسبه هزینه پایه تولید محتوا
    content_orders = campaign.content_orders.exclude(
        status=ContentOrder.Status.CANCELLED
    ).select_related("team")
    base_content_cost = sum(order.price for order in content_orders)

    # محاسبه کمیسیون پایه پلتفرم (بر اساس هزینه‌های پایه)
    base_subtotal = base_influencer_cost + base_content_cost
    base_commission = int(base_subtotal * PLATFORM_COMMISSION)

    # ============================================================
    # ۲. اعمال تخفیف‌ها به صورت تفکیک‌شده
    # ============================================================
    total_discount = 0
    influencer_discount_amount = 0
    content_discount_amount = 0
    platform_discount_amount = 0

    # **الف) تخفیف اینفلوئنسر (ناشر)**
    if campaign.influencer_coupon and campaign.influencer_coupon.is_valid():
        coupon = campaign.influencer_coupon
        if coupon.channel:
            target_amount = sum(
                booking.price
                for booking in influencer_bookings
                if booking.channel_id == coupon.channel_id
            )
        else:
            target_amount = base_influencer_cost

        influencer_discount_amount = coupon.calculate_discount(target_amount)
        total_discount += influencer_discount_amount

    # **ب) تخفیف تیم محتوا**
    if campaign.content_team_coupon and campaign.content_team_coupon.is_valid():
        coupon = campaign.content_team_coupon
        if coupon.team:
            target_amount = sum(
                order.price
                for order in content_orders
                if order.team_id == coupon.team_id
            )
        else:
            target_amount = base_content_cost

        content_discount_amount = coupon.calculate_discount(target_amount)
        total_discount += content_discount_amount

    # **ج) تخفیف پلتفرم (کمیسیون)**
    if campaign.platform_coupon and campaign.platform_coupon.is_valid():
        coupon = campaign.platform_coupon
        platform_discount_amount = coupon.calculate_discount(base_commission)
        total_discount += platform_discount_amount

    # ============================================================
    # ۳. محاسبه مبالغ نهایی (بعد از کسر تخفیف)
    # ============================================================

    influencer_cost = max(base_influencer_cost - influencer_discount_amount, 0)
    content_cost = max(base_content_cost - content_discount_amount, 0)
    commission = max(base_commission - platform_discount_amount, 0)

    total_amount = base_influencer_cost + base_content_cost + base_commission
    payable_amount = max(total_amount - total_discount, 0)

    # ============================================================
    # ۴. ذخیره در دیتابیس (با در نظر گرفتن تمام فیلدهای جدید)
    # ============================================================

    invoice, created = CampaignInvoice.objects.get_or_create(
        campaign=campaign,
        defaults={
            # مبالغ پایه
            "base_influencer_cost": base_influencer_cost,
            "base_content_cost": base_content_cost,
            "base_commission": base_commission,

            # مبالغ تخفیف (تفکیکی)
            "influencer_discount_amount": influencer_discount_amount,
            "content_discount_amount": content_discount_amount,
            "platform_discount_amount": platform_discount_amount,

            # مبالغ نهایی (بعد از تخفیف)
            "influencer_cost": influencer_cost,
            "content_cost": content_cost,
            "commission": commission,

            # جمع کل تخفیف
            "discount_amount": total_discount,

            # مبلغ کل و قابل پرداخت
            "total_amount": total_amount,
            "payable_amount": payable_amount,
        }
    )

    if created:
        invoice.save()
        invoice.invoice_number = CampaignInvoice.generate_invoice_number(
            invoice.id,
            invoice.created_at
        )
        invoice.save(update_fields=['invoice_number'])
    else:
        # به‌روزرسانی فیلدهای موجود در صورت تغییرات
        invoice.base_influencer_cost = base_influencer_cost
        invoice.base_content_cost = base_content_cost
        invoice.base_commission = base_commission
        invoice.influencer_discount_amount = influencer_discount_amount
        invoice.content_discount_amount = content_discount_amount
        invoice.platform_discount_amount = platform_discount_amount
        invoice.influencer_cost = influencer_cost
        invoice.content_cost = content_cost
        invoice.commission = commission
        invoice.discount_amount = total_discount
        invoice.total_amount = total_amount
        invoice.payable_amount = payable_amount

        invoice.save(update_fields=[
            "base_influencer_cost",
            "base_content_cost",
            "base_commission",
            "influencer_discount_amount",
            "content_discount_amount",
            "platform_discount_amount",
            "influencer_cost",
            "content_cost",
            "commission",
            "discount_amount",
            "total_amount",
            "payable_amount",
        ])

    return invoice
