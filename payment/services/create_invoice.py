from payment.constants import VAT_PERCENT, PLATFORM_COMMISSION
from influencers.models import ChannelBooking
from content_team.models import ContentOrder
from payment.models import Invoice, Payment
from django.utils import timezone
from django.db.models import F


def sync_discounts_to_bookings(campaign):
    """
    تخفیف‌های کوپن‌ها رو روی price رزروها و سفارشات اعمال می‌کنه.

    قواعد:
    - فقط کانال/تیمی که کوپن بهش وصل شده تخفیف می‌گیره
    - اگه کوپن به کانال/تیم خاصی وصل نباشه، به همه اعمال میشه
    - original_price همیشه ثابت می‌مونه
    - price = original_price - discount_amount
    """
    # ========== ۱. اطمینان از پر بودن original_price ==========
    # اگه original_price خالیه (رکوردهای قدیمی)، از price پر کن
    campaign.influencer_bookings.filter(original_price__isnull=True).update(
        original_price=F('price')
    )
    campaign.content_orders.filter(original_price__isnull=True).update(
        original_price=F('price')
    )

    # ========== ۲. ریست همه به original_price ==========
    campaign.influencer_bookings.update(
        price=F('original_price'),
        discount_amount=0
    )
    campaign.content_orders.update(
        price=F('original_price'),
        discount_amount=0
    )

    # ========== ۳. اعمال کوپن اینفلوئنسر ==========
    if campaign.influencer_coupon and campaign.influencer_coupon.is_valid():
        coupon = campaign.influencer_coupon

        if coupon.channel_id:
            bookings = campaign.influencer_bookings.filter(
                channel_id=coupon.channel_id
            )
        else:
            bookings = campaign.influencer_bookings.all()

        for booking in bookings:
            discount = coupon.calculate_discount(booking.original_price)
            booking.discount_amount = discount
            booking.price = max(booking.original_price - discount, 0)
            booking.save(update_fields=['price', 'discount_amount'])

    # ========== ۴. اعمال کوپن تیم محتوا ==========
    if campaign.content_team_coupon and campaign.content_team_coupon.is_valid():
        coupon = campaign.content_team_coupon

        if coupon.team_id:
            orders = campaign.content_orders.filter(team_id=coupon.team_id)
        else:
            orders = campaign.content_orders.all()

        for order in orders:
            discount = coupon.calculate_discount(order.original_price)
            order.discount_amount = discount
            order.price = max(order.original_price - discount, 0)
            order.save(update_fields=['price', 'discount_amount'])


def sync_discounts_to_standalone_order(order):
    """
    تخفیف‌های کوپن‌ها رو روی price سفارش مستقل اعمال می‌کنه.

    قواعد:
    - اگه کوپن content_team به تیم خاصی وصل باشه، فقط اگه تیم سفارش یکی باشه اعمال میشه
    - اگه کوپن content_team به تیم خاصی وصل نباشه، به همه اعمال میشه
    - original_price همیشه ثابت می‌مونه
    - price = original_price - discount_amount
    - کوپن platform روی کمیسیون اعمال میشه (نه روی price)
    """
    # ========== ۱. اطمینان از پر بودن original_price ==========
    if not order.original_price:
        order.original_price = order.price
        order.save(update_fields=['original_price'])

    # ========== ۲. ریست به original_price ==========
    order.price = order.original_price
    order.discount_amount = 0

    # ========== ۳. اعمال کوپن تیم محتوا ==========
    if order.content_team_coupon and order.content_team_coupon.is_valid():
        coupon = order.content_team_coupon

        # چک کن که کوپن به تیم خاصی وصل باشه و با تیم سفارش یکی باشه
        should_apply = True
        if coupon.team_id and coupon.team_id != order.team_id:
            should_apply = False

        if should_apply:
            discount = coupon.calculate_discount(order.original_price)
            order.discount_amount = discount
            order.price = max(order.original_price - discount, 0)

    # ========== ۴. ذخیره ==========
    order.save(update_fields=['price', 'discount_amount', 'original_price'])

def create_campaign_invoice(campaign):
    """
    ساخت فاکتور برای کمپین

    نکته مهم:
    - base_* از original_price محاسبه میشه (قیمت قبل از تخفیف)
    - discount_amount از خود رزروها/سفارشات خونده میشه (نه از کوپن)
    - اینطوری دو بار اعمال تخفیف اتفاق نمیفته
    """
    # ========== محاسبه هزینه‌های پایه (از original_price) ==========
    influencer_bookings = campaign.influencer_bookings.exclude(
        status__in=[
            ChannelBooking.Status.REJECTED,
            ChannelBooking.Status.REPLACED
        ]
    ).select_related("channel__influencer")

    base_influencer_cost = sum(
        (booking.original_price or booking.price)
        for booking in influencer_bookings
    )

    content_orders = campaign.content_orders.exclude(
        status=ContentOrder.Status.CANCELLED
    ).select_related("team")

    base_content_cost = sum(
        (order.original_price or order.price)
        for order in content_orders
    )

    base_subtotal = base_influencer_cost + base_content_cost
    base_commission = int(base_subtotal * PLATFORM_COMMISSION)

    # ========== محاسبه تخفیف‌ها (از خود رزروها/سفارشات) ==========
    influencer_discount_amount = sum(
        booking.discount_amount
        for booking in influencer_bookings
    )

    content_discount_amount = sum(
        order.discount_amount
        for order in content_orders
    )

    # تخفیف پلتفرم (فقط از کوپن پلتفرم)
    platform_discount_amount = 0
    if campaign.platform_coupon and campaign.platform_coupon.is_valid():
        coupon = campaign.platform_coupon
        platform_discount_amount = coupon.calculate_discount(base_commission)

    total_discount = (
        influencer_discount_amount +
        content_discount_amount +
        platform_discount_amount
    )

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
    base_content_cost = order.original_price or order.price

    # ========== محاسبه کمیسیون ==========
    base_commission = int(base_content_cost * PLATFORM_COMMISSION)

    # ========== محاسبه تخفیف‌ها ==========
    content_discount_amount = order.discount_amount or 0
    platform_discount_amount = 0

    if order.platform_coupon and order.platform_coupon.is_valid():
        coupon = order.platform_coupon
        platform_discount_amount = coupon.calculate_discount(base_commission)

    total_discount = content_discount_amount + platform_discount_amount

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

    invoice.invoice_number = Invoice.generate_invoice_number(
        invoice.id,
        invoice.created_at,
        Invoice.Type.WALLET
    )
    invoice.save(update_fields=['invoice_number'])

    return invoice


def complete_wallet_payment(user, amount, ref_id, authority=None):
    """
    تکمیل پرداخت کیف پول بعد از تأیید درگاه
    - اگه فاکتور با این authority وجود داشت، آپدیت میشه
    - اگه نه، فاکتور جدید ساخته میشه
    """
    from django.db import transaction
    from payment.models import Transaction, Invoice, Payment

    with transaction.atomic():
        # ========== ۱. پیدا کردن فاکتور (اگه وجود داشته باشه) ==========
        invoice = None
        payment = None

        if authority:
            # جستجو بر اساس authority
            payment = Payment.objects.filter(
                authority=authority,
                status=Payment.Status.PENDING
            ).select_related('invoice').first()

            if payment:
                invoice = payment.invoice

        # ========== ۲. اگه فاکتور نبود، فاکتور جدید بساز ==========
        if not invoice:
            invoice = Invoice.objects.create(
                type=Invoice.Type.WALLET,
                user=user,
                wallet_deposit_amount=amount,
                total_amount=amount,
                payable_amount=amount,
                description=f"شارژ کیف پول از طریق زرین‌پال - مبلغ {amount:,} تومان",
                is_paid=False,
            )

            # تولید شماره فاکتور
            invoice.invoice_number = Invoice.generate_invoice_number(
                invoice.id,
                invoice.created_at,
                Invoice.Type.WALLET
            )
            invoice.save(update_fields=['invoice_number'])

        # ========== ۳. آپدیت فاکتور ==========
        invoice.is_paid = True
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=['is_paid', 'paid_at'])

        # ========== ۴. ساخت یا آپدیت Payment ==========
        if payment:
            payment.status = Payment.Status.SUCCESS
            payment.ref_id = ref_id
            payment.save(update_fields=['status', 'ref_id'])
        else:
            payment = Payment.objects.create(
                user=user,
                invoice=invoice,
                amount=amount,
                payment_method=Payment.Method.GATEWAY,
                authority=authority or '',
                ref_id=ref_id,
                status=Payment.Status.SUCCESS,
            )

        # ========== ۵. شارژ کیف پول ==========
        wallet = user.wallet
        wallet.balance += amount
        wallet.save(update_fields=['balance'])

        # ========== ۶. ثبت تراکنش ==========
        Transaction.objects.create(
            user=user,
            amount=amount,
            type=Transaction.Type.DEPOSIT,
            status=Transaction.Status.SUCCESS,
            invoice=invoice,
            payment=payment,
            reference_id=ref_id,
            description=f"شارژ کیف پول از طریق زرین‌پال - کد پیگیری: {ref_id}"
        )

    return invoice
