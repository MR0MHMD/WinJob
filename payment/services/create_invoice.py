from payment.constants import VAT_PERCENT, PLATFORM_COMMISSION
from influencers.models import ChannelBooking
from content_team.models import ContentOrder
from payment.models import Invoice, Payment
from django.utils import timezone


def create_campaign_invoice(campaign):
    """
    ساخت فاکتور برای کمپین
    """
    # ========== محاسبه هزینه‌های پایه ==========
    influencer_bookings = campaign.influencer_bookings.exclude(
        status__in=[
            ChannelBooking.Status.REJECTED,
            ChannelBooking.Status.REPLACED
        ]
    ).select_related("channel__influencer")
    base_influencer_cost = sum(booking.price for booking in influencer_bookings)

    content_orders = campaign.content_orders.exclude(
        status=ContentOrder.Status.CANCELLED
    ).select_related("team")
    base_content_cost = sum(order.price for order in content_orders)

    base_subtotal = base_influencer_cost + base_content_cost
    base_commission = int(base_subtotal * PLATFORM_COMMISSION)

    # ========== محاسبه تخفیف‌ها ==========
    total_discount = 0
    influencer_discount_amount = 0
    content_discount_amount = 0
    platform_discount_amount = 0

    # تخفیف اینفلوئنسر
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

    # تخفیف تیم محتوا
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

    # تخفیف پلتفرم
    if campaign.platform_coupon and campaign.platform_coupon.is_valid():
        coupon = campaign.platform_coupon
        platform_discount_amount = coupon.calculate_discount(base_commission)
        total_discount += platform_discount_amount

    # ========== محاسبه مبالغ نهایی ==========
    influencer_cost = max(base_influencer_cost - influencer_discount_amount, 0)
    content_cost = max(base_content_cost - content_discount_amount, 0)
    commission = max(base_commission - platform_discount_amount, 0)

    total_amount = base_influencer_cost + base_content_cost + base_commission
    payable_amount = max(total_amount - total_discount, 0)

    # ========== محاسبه مالیات ==========
    influencer_vat = int(influencer_cost * VAT_PERCENT)
    content_vat = int(content_cost * VAT_PERCENT)
    commission_vat = int(commission * VAT_PERCENT)
    total_vat = influencer_vat + content_vat + commission_vat
    payable_amount += total_vat

    # ========== ساخت یا به‌روزرسانی فاکتور ==========
    invoice, created = Invoice.objects.get_or_create(
        campaign=campaign,
        defaults={
            "type": Invoice.Type.CAMPAIGN,
            "user": campaign.advertiser.user,
            "base_influencer_cost": base_influencer_cost,
            "base_content_cost": base_content_cost,
            "base_commission": base_commission,
            "influencer_discount_amount": influencer_discount_amount,
            "content_discount_amount": content_discount_amount,
            "platform_discount_amount": platform_discount_amount,
            "influencer_cost": influencer_cost,
            "content_cost": content_cost,
            "commission": commission,
            "discount_amount": total_discount,
            "total_amount": total_amount,
            "payable_amount": payable_amount,
            "influencer_vat": influencer_vat,
            "content_vat": content_vat,
            "commission_vat": commission_vat,
            "total_vat": total_vat,
            "description": f"فاکتور کمپین {campaign.name}",
            "is_paid": False,
        }
    )

    if created:
        invoice.invoice_number = Invoice.generate_invoice_number(
            invoice.id,
            invoice.created_at,
            Invoice.Type.CAMPAIGN
        )
        invoice.save(update_fields=['invoice_number'])
    else:
        # به‌روزرسانی فاکتور موجود
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
        invoice.influencer_vat = influencer_vat
        invoice.content_vat = content_vat
        invoice.commission_vat = commission_vat
        invoice.total_vat = total_vat
        invoice.save()

    return invoice


def create_standalone_invoice(order):
    """
    ساخت فاکتور برای سفارش مستقل تولید محتوا
    """
    # ========== محاسبه هزینه‌های پایه ==========
    base_content_cost = order.price  # قیمت پلن

    # ========== محاسبه کمیسیون ==========
    base_commission = int(base_content_cost * PLATFORM_COMMISSION)

    # ========== محاسبه تخفیف‌ها ==========
    total_discount = 0
    content_discount_amount = 0
    platform_discount_amount = 0

    # تخفیف تیم محتوا (اگر کوپن به تیم خاصی تعلق داشته باشه)
    # توجه: در سفارش مستقل، کوپن‌ها رو از خود سفارش میگیریم
    if order.content_team_coupon:
        coupon = order.content_team_coupon
        if coupon.is_valid():
            # اگر کوپن به تیم خاصی تعلق داره، فقط اگه تیم سفارش با تیم کوپن یکی باشه
            if coupon.team and coupon.team.id == order.team_id:
                content_discount_amount = coupon.calculate_discount(base_content_cost)
            elif not coupon.team:  # کوپن عمومی برای همه تیم‌ها
                content_discount_amount = coupon.calculate_discount(base_content_cost)
            total_discount += content_discount_amount

    # تخفیف پلتفرم (برای کمیسیون)
    if order.platform_coupon:
        coupon = order.platform_coupon
        if coupon.is_valid():
            platform_discount_amount = coupon.calculate_discount(base_commission)
            total_discount += platform_discount_amount

    # ========== محاسبه مبالغ نهایی ==========
    content_cost = max(base_content_cost - content_discount_amount, 0)
    commission = max(base_commission - platform_discount_amount, 0)

    total_amount = base_content_cost + base_commission
    payable_amount = max(total_amount - total_discount, 0)

    # ========== محاسبه مالیات بر ارزش افزوده ==========
    content_vat = int(content_cost * VAT_PERCENT)
    commission_vat = int(commission * VAT_PERCENT)
    total_vat = content_vat + commission_vat
    payable_amount += total_vat

    # ========== ساخت یا به‌روزرسانی فاکتور ==========
    invoice, created = Invoice.objects.get_or_create(
        content_order=order,
        defaults={
            "type": Invoice.Type.CONTENT_ORDER,
            "user": order.standalone_user,
            "base_content_cost": base_content_cost,
            "base_commission": base_commission,
            "content_discount_amount": content_discount_amount,
            "platform_discount_amount": platform_discount_amount,
            "content_cost": content_cost,
            "commission": commission,
            "discount_amount": total_discount,
            "total_amount": total_amount,
            "payable_amount": payable_amount,
            "content_vat": content_vat,
            "commission_vat": commission_vat,
            "total_vat": total_vat,
            "description": f"فاکتور سفارش مستقل تولید محتوا #{order.id}",
            "is_paid": False,
        }
    )

    if created:
        invoice.invoice_number = Invoice.generate_invoice_number(
            invoice.id,
            invoice.created_at,
            Invoice.Type.CONTENT_ORDER
        )
        invoice.save(update_fields=['invoice_number'])
    else:
        # به‌روزرسانی فاکتور موجود
        invoice.base_content_cost = base_content_cost
        invoice.base_commission = base_commission
        invoice.content_discount_amount = content_discount_amount
        invoice.platform_discount_amount = platform_discount_amount
        invoice.content_cost = content_cost
        invoice.commission = commission
        invoice.discount_amount = total_discount
        invoice.total_amount = total_amount
        invoice.payable_amount = payable_amount
        invoice.content_vat = content_vat
        invoice.commission_vat = commission_vat
        invoice.total_vat = total_vat
        invoice.save()

    return invoice


def create_wallet_invoice(user, amount, description=None):
    """
    ساخت فاکتور برای شارژ کیف پول
    """
    invoice = Invoice.objects.create(
        type=Invoice.Type.WALLET,
        user=user,
        campaign=None,
        wallet_deposit_amount=amount,
        total_amount=amount,
        payable_amount=amount,
        description=description or f"شارژ کیف پول به مبلغ {amount:,} تومان",
        is_paid=False,
    )

    # تولید شماره فاکتور
    invoice.invoice_number = Invoice.generate_invoice_number(
        invoice.id,
        invoice.created_at,
        Invoice.Type.WALLET
    )
    invoice.save(update_fields=['invoice_number'])

    return invoice


def create_wallet_invoice_for_payment(user, amount, authority, description=None):
    """
    ساخت فاکتور برای پرداخت درگاه (قبل از رفتن به درگاه)
    """
    invoice = create_wallet_invoice(
        user=user,
        amount=amount,
        description=description or f"شارژ کیف پول از طریق زرین‌پال - مبلغ {amount:,} تومان"
    )

    # ثبت Payment با وضعیت PENDING
    payment = Payment.objects.create(
        user=user,
        invoice=invoice,
        amount=amount,
        payment_method=Payment.Method.GATEWAY,
        authority=authority,
        status=Payment.Status.PENDING,
    )

    return invoice, payment


def complete_wallet_payment(invoice, ref_id):
    """
    تکمیل پرداخت کیف پول بعد از تأیید درگاه
    """
    from django.db import transaction

    with transaction.atomic():
        # به‌روزرسانی فاکتور
        invoice.is_paid = True
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=['is_paid', 'paid_at'])

        # به‌روزرسانی پرداخت
        payment = invoice.payments.first()
        if payment:
            payment.status = Payment.Status.SUCCESS
            payment.ref_id = ref_id
            payment.save(update_fields=['status', 'ref_id'])

        # شارژ کیف پول
        wallet = invoice.user.wallet
        wallet.balance += invoice.wallet_deposit_amount
        wallet.save(update_fields=['balance'])

        # ثبت تراکنش
        from payment.models import Transaction
        Transaction.objects.create(
            user=invoice.user,
            amount=invoice.wallet_deposit_amount,
            type=Transaction.Type.DEPOSIT,
            status=Transaction.Status.SUCCESS,
            invoice=invoice,
            payment=payment,
            reference_id=ref_id,
            description=f"شارژ کیف پول از طریق زرین‌پال - کد پیگیری: {ref_id}"
        )

    return True
