from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django_iranian_payment.contrib.django import services

from campaigns.services.campaigns_notifications import submit_campaign_for_review
from content_team.models import ContentOrder
from payment.models import Transaction, Invoice, Payment
from payment.services.create_invoice import create_campaign_invoice
from payment.utils import number_to_words
from campaigns.models import Campaign
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Q


# ============================================================
# helper: ساخت context اقلام فاکتور وین مارکت
# ============================================================
def _build_market_invoice_items(invoice):
    """
    از OrderItem ها، اطلاعات اقلام + قیمت با/بدون تخفیف رو می‌سازه
    """
    order = invoice.market_order
    if not order:
        return {
            'market_order': None,
            'market_items': [],
            'market_total_without_discount': 0,
            'market_total_with_discount': 0,
            'market_discount_amount': 0,
        }

    items_data = []
    total_without_discount = 0
    total_with_discount = 0

    for item in order.items.select_related('product', 'variant').all():
        base_unit = item.product.base_price if item.product else item.unit_price
        qty = item.quantity
        line_without = base_unit * qty
        line_with = item.subtotal

        items_data.append({
            'product_title': item.product_title,
            'variant_info': item.variant_info,
            'quantity': qty,
            'unit_price': item.unit_price,
            'base_unit_price': base_unit,
            'line_without_discount': line_without,
            'line_with_discount': line_with,
            'has_discount': line_without > line_with,
        })
        total_without_discount += line_without
        total_with_discount += line_with

    return {
        'market_order': order,
        'market_items': items_data,
        'market_total_without_discount': total_without_discount,
        'market_total_with_discount': total_with_discount,
        'market_discount_amount': max(total_without_discount - total_with_discount, 0),
    }


@login_required
def invoice_list(request):
    """لیست فاکتورهای کاربر (هم کمپین و هم کیف پول)"""

    invoices = Invoice.objects.filter(
        user=request.user
    ).select_related('campaign').order_by('-created_at')

    type_filter = request.GET.get('type')
    if type_filter == 'campaign':
        invoices = invoices.filter(type=Invoice.Type.CAMPAIGN)
    elif type_filter in ('wallet', 'windirect', 'content_order', 'market_order'):
        invoices = invoices.filter(type=type_filter)

    status_filter = request.GET.get('status')
    if status_filter == 'paid':
        invoices = invoices.filter(is_paid=True)
    elif status_filter == 'unpaid':
        invoices = invoices.filter(is_paid=False)

    # آمار از queryset پایه (بدون فیلتر) تا ارقام ثابت بمونن
    base_qs = Invoice.objects.filter(user=request.user)

    context = {
        'invoices': invoices,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'total_count': base_qs.count(),
        'paid_count': base_qs.filter(is_paid=True).count(),
        'unpaid_count': base_qs.filter(is_paid=False).count(),
        'campaign_count': base_qs.filter(type=Invoice.Type.CAMPAIGN).count(),
        'wallet_count': base_qs.filter(type=Invoice.Type.WALLET).count(),
        'market_order_count': base_qs.filter(type=Invoice.Type.MARKET_ORDER).count(),
    }

    return render(request, 'payment/invoices/invoice_list.html', context)


@login_required
def invoice_detail(request, invoice_id):
    """جزئیات یک فاکتور (کمپین، کیف پول، اشتراک، سفارش محتوا)"""

    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'user',
            'campaign',
            'campaign__platform',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'subscription_order',
            'subscription_order__offer__plan',
            'content_order',
            'market_order',
        ).prefetch_related(
            'market_order__items__product',
            'market_order__items__variant',
        ),
        id=invoice_id,
        user=request.user
    )

    # تراکنش‌های مرتبط
    transactions = Transaction.objects.filter(
        invoice=invoice
    ).order_by('-created_at')

    context = {
        'invoice': invoice,
        'transactions': transactions,
        'can_cancel': not invoice.is_paid and invoice.type == Invoice.Type.CAMPAIGN,
        'can_pay': not invoice.is_paid and invoice.type == Invoice.Type.CAMPAIGN,
        'is_wallet_invoice': invoice.type == Invoice.Type.WALLET,
        'is_campaign_invoice': invoice.type == Invoice.Type.CAMPAIGN,
        'is_windirect_invoice': invoice.type == Invoice.Type.WINDIRECT,
        'is_content_order_invoice': invoice.type == Invoice.Type.CONTENT_ORDER,
        'is_market_order_invoice': invoice.type == Invoice.Type.MARKET_ORDER,
    }

    # اطلاعات اضافی برای فاکتور وین مارکت
    if invoice.type == Invoice.Type.MARKET_ORDER:
        context.update(_build_market_invoice_items(invoice))

    # اطلاعات اضافی برای فاکتور کمپین
    if invoice.type == Invoice.Type.CAMPAIGN and invoice.campaign:
        influencer_count = invoice.campaign.influencer_bookings.count()
        context['influencer_count'] = influencer_count
        context['campaign'] = invoice.campaign

    # اطلاعات اضافی برای فاکتور اشتراک
    if invoice.type == Invoice.Type.WINDIRECT:
        context['order'] = invoice.subscription_order

    # اطلاعات اضافی برای فاکتور سفارش محتوا
    if invoice.type == Invoice.Type.CONTENT_ORDER:
        context['content_order'] = invoice.content_order

    return render(request, 'payment/invoices/invoice_detail.html', context)


@login_required
def invoice_print(request, invoice_id):
    """
    نمایش نسخه پرینت فاکتور
    پشتیبانی از:
    - فاکتور کمپین (CAMPAIGN)
    - فاکتور کیف پول (WALLET)
    - فاکتور سفارش مستقل تولید محتوا (CONTENT_ORDER)
    - فاکتور اشتراک وین دایرکت (WINDIRECT)
    """

    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'user',
            'campaign',
            'campaign__platform',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'campaign__advertiser__user__province',
            'campaign__influencer_coupon',
            'campaign__content_team_coupon',
            'campaign__platform_coupon',
            'content_order',
            'content_order__team',
            'content_order__plan',
            'subscription_order',
            'subscription_order__offer__plan',
            'market_order',
        ),
        id=invoice_id,
        user=request.user
    )

    # ============================================================
    # ۱. فاکتور اشتراک وین دایرکت
    # ============================================================
    if invoice.type == Invoice.Type.WINDIRECT:
        order = invoice.subscription_order
        # مبالغ به ریال
        def convert_to_rial(value):
            return int(value or 0) * 10

        base_plan_cost_rial = convert_to_rial(invoice.base_plan_cost)
        plan_discount_amount_rial = convert_to_rial(invoice.plan_discount_amount)
        plan_cost_rial = convert_to_rial(invoice.plan_cost)
        plan_vat_rial = convert_to_rial(invoice.plan_vat)
        payable_amount_rial = convert_to_rial(invoice.payable_amount)

        payable_amount_words = number_to_words(payable_amount_rial, 'ریال')

        context = {
            'invoice': invoice,
            'order': order,
            'is_windirect_invoice': True,
            'base_plan_cost_rial': base_plan_cost_rial,
            'plan_discount_amount_rial': plan_discount_amount_rial,
            'plan_cost_rial': plan_cost_rial,
            'plan_vat_rial': plan_vat_rial,
            'payable_amount_rial': payable_amount_rial,
            'payable_amount_words': payable_amount_words,
        }
        return render(request, 'payment/invoices/invoice_print.html', context)

    # ============================================================
    # ۲. فاکتور کیف پول
    # ============================================================
    if invoice.type == Invoice.Type.WALLET:
        payable_amount_rial = invoice.wallet_deposit_amount * 10
        payable_amount_words = number_to_words(payable_amount_rial, 'ریال')

        context = {
            'invoice': invoice,
            'is_wallet_invoice': True,
            'payable_amount_rial': payable_amount_rial,
            'payable_amount_words': payable_amount_words,
            'wallet_deposit_amount': invoice.wallet_deposit_amount,
        }
        return render(request, 'payment/invoices/invoice_print.html', context)

    # ============================================================
    # ۳. فاکتور سفارش مستقل تولید محتوا (CONTENT_ORDER)
    # ============================================================
    if invoice.type == Invoice.Type.CONTENT_ORDER:
        content_order = invoice.content_order

        def convert_to_rial(value):
            return value * 10

        base_content_cost_rial = convert_to_rial(invoice.base_content_cost)
        base_commission_rial = convert_to_rial(invoice.base_commission)

        content_discount_rial = convert_to_rial(invoice.content_discount_amount)
        platform_discount_rial = convert_to_rial(invoice.platform_discount_amount)
        total_discount_rial = convert_to_rial(invoice.discount_amount)

        content_after_discount_rial = base_content_cost_rial - content_discount_rial
        platform_after_discount_rial = base_commission_rial - platform_discount_rial

        content_vat_rial = convert_to_rial(invoice.content_vat)
        platform_vat_rial = convert_to_rial(invoice.commission_vat)

        content_cost_rial = convert_to_rial(invoice.content_cost + invoice.content_vat)
        commission_rial = convert_to_rial(invoice.commission + invoice.commission_vat)
        total_amount_rial = convert_to_rial(invoice.total_amount)
        payable_amount_rial = convert_to_rial(invoice.payable_amount)

        payable_amount_words = number_to_words(payable_amount_rial, 'ریال')

        context = {
            'invoice': invoice,
            'content_order': content_order,
            'is_content_order_invoice': True,

            'team_name': content_order.team.name if content_order.team else '-',
            'plan_name': content_order.plan.name if content_order.plan else '-',
            'plan_price': content_order.price if content_order.price else 0,

            'base_content_cost_rial': base_content_cost_rial,
            'base_commission_rial': base_commission_rial,
            'content_after_discount_rial': content_after_discount_rial,
            'platform_after_discount_rial': platform_after_discount_rial,
            'content_vat_rial': content_vat_rial,
            'platform_vat_rial': platform_vat_rial,
            'content_discount_rial': content_discount_rial,
            'platform_discount_rial': platform_discount_rial,
            'total_discount_rial': total_discount_rial,
            'content_cost_rial': content_cost_rial,
            'commission_rial': commission_rial,
            'total_amount_rial': total_amount_rial,
            'payable_amount_rial': payable_amount_rial,
            'payable_amount_words': payable_amount_words,
        }

        return render(request, 'payment/invoices/invoice_print.html', context)

    # ============================================================
    # ۳.۵ فاکتور سفارش وین مارکت
    # ============================================================
    if invoice.type == Invoice.Type.MARKET_ORDER:
        ctx = _build_market_invoice_items(invoice)

        # تبدیل به ریال
        def convert_to_rial(value):
            return int(value or 0) * 10

        items_rial = []
        for it in ctx['market_items']:
            items_rial.append({
                **it,
                'unit_price_rial': convert_to_rial(it['unit_price']),
                'base_unit_price_rial': convert_to_rial(it['base_unit_price']),
                'line_without_discount_rial': convert_to_rial(it['line_without_discount']),
                'line_with_discount_rial': convert_to_rial(it['line_with_discount']),
            })

        total_without_rial = convert_to_rial(ctx['market_total_without_discount'])
        total_with_rial = convert_to_rial(ctx['market_total_with_discount'])
        discount_rial = convert_to_rial(ctx['market_discount_amount'])
        payable_amount_rial = convert_to_rial(invoice.payable_amount)

        payable_amount_words = number_to_words(payable_amount_rial, 'ریال')

        context = {
            'invoice': invoice,
            'market_order': ctx['market_order'],
            'market_items': items_rial,
            'is_market_order_invoice': True,
            'market_total_without_discount_rial': total_without_rial,
            'market_total_with_discount_rial': total_with_rial,
            'market_discount_amount_rial': discount_rial,
            'payable_amount_rial': payable_amount_rial,
            'payable_amount_words': payable_amount_words,
        }
        return render(request, 'payment/invoices/invoice_print.html', context)

    # ============================================================
    # ۴. فاکتور کمپین (CAMPAIGN)
    # ============================================================
    influencer_count = 0
    if invoice.campaign:
        influencer_count = invoice.campaign.influencer_bookings.count()

    def convert_to_rial(value):
        return value * 10

    base_influencer_cost_rial = convert_to_rial(invoice.base_influencer_cost)
    base_content_cost_rial = convert_to_rial(invoice.base_content_cost)
    base_commission_rial = convert_to_rial(invoice.base_commission)

    influencer_discount_rial = convert_to_rial(invoice.influencer_discount_amount)
    content_discount_rial = convert_to_rial(invoice.content_discount_amount)
    platform_discount_rial = convert_to_rial(invoice.platform_discount_amount)
    total_discount_rial = convert_to_rial(invoice.discount_amount)

    influencer_after_discount_rial = base_influencer_cost_rial - influencer_discount_rial
    content_after_discount_rial = base_content_cost_rial - content_discount_rial
    platform_after_discount_rial = base_commission_rial - platform_discount_rial

    influencer_vat_rial = convert_to_rial(invoice.influencer_vat)
    content_vat_rial = convert_to_rial(invoice.content_vat)
    platform_vat_rial = convert_to_rial(invoice.commission_vat)

    influencer_cost_rial = convert_to_rial(invoice.influencer_cost + invoice.influencer_vat)
    content_cost_rial = convert_to_rial(invoice.content_cost + invoice.content_vat)
    commission_rial = convert_to_rial(invoice.commission + invoice.commission_vat)
    total_amount_rial = convert_to_rial(invoice.total_amount)
    payable_amount_rial = convert_to_rial(invoice.payable_amount)

    payable_amount_words = number_to_words(payable_amount_rial, 'ریال')

    context = {
        'invoice': invoice,
        'influencer_count': influencer_count,
        'is_campaign_invoice': True,

        'base_influencer_cost_rial': base_influencer_cost_rial,
        'base_content_cost_rial': base_content_cost_rial,
        'base_commission_rial': base_commission_rial,

        'influencer_after_discount_rial': influencer_after_discount_rial,
        'content_after_discount_rial': content_after_discount_rial,
        'platform_after_discount_rial': platform_after_discount_rial,

        'influencer_vat_rial': influencer_vat_rial,
        'content_vat_rial': content_vat_rial,
        'platform_vat_rial': platform_vat_rial,

        'influencer_discount_rial': influencer_discount_rial,
        'content_discount_rial': content_discount_rial,
        'platform_discount_rial': platform_discount_rial,
        'total_discount_rial': total_discount_rial,

        'influencer_cost_rial': influencer_cost_rial,
        'content_cost_rial': content_cost_rial,
        'commission_rial': commission_rial,
        'total_amount_rial': total_amount_rial,
        'payable_amount_rial': payable_amount_rial,
        'payable_amount_words': payable_amount_words,
    }

    return render(request, 'payment/invoices/invoice_print.html', context)


@login_required
@transaction.atomic
def cancel_invoice(request, invoice_id):
    """لغو فاکتور و حذف کامل کمپین (پشتیبانی از JSON)"""

    try:
        invoice = get_object_or_404(
            Invoice,
            id=invoice_id,
            user=request.user,
            is_paid=False
        )
    except Invoice.DoesNotExist:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'فاکتور یافت نشد یا قبلاً پرداخت شده است.'}, status=404)
        messages.error(request, "فاکتور یافت نشد یا قبلاً پرداخت شده است.")
        return redirect('payment:invoice_list')

    if invoice.type != Invoice.Type.CAMPAIGN:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'این فاکتور قابل لغو نیست.'}, status=400)
        messages.error(request, "این فاکتور قابل لغو نیست.")
        return redirect('payment:invoice_list')

    campaign = invoice.campaign

    if not campaign or campaign.status not in [Campaign.Status.DRAFT, Campaign.Status.PENDING]:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'این کمپین قابل لغو نیست.'}, status=400)
        messages.error(request, "این کمپین قابل لغو نیست.")
        return redirect(invoice)

    campaign_name = campaign.name
    campaign.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f'فاکتور و کمپین {campaign_name} با موفقیت لغو شدند.'})

    messages.success(request, f"فاکتور و کمپین {campaign_name} با موفقیت لغو شدند.")
    return redirect('payment:invoice_list')


@login_required
def redirect_to_payment(request, invoice_id):
    """هدایت کاربر به صفحه پرداخت (استپ ۴)"""

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        user=request.user,
        is_paid=False
    )

    if invoice.type != Invoice.Type.CAMPAIGN:
        messages.error(request, "این فاکتور قابل پرداخت نیست.")
        return redirect('payment:invoice_list')

    campaign = invoice.campaign

    if not campaign:
        messages.error(request, "کمپین یافت نشد.")
        return redirect('payment:invoice_list')

    request.session['campaign_draft_id'] = campaign.id

    return redirect('campaigns:campaign_create_step4')


@login_required
def campaign_payment_callback(request):
    """کالبک بازگشت از درگاه زرین‌پال برای پرداخت کمپین"""
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')

    if not authority:
        messages.error(request, "اطلاعات پرداخت یافت نشد.")
        return redirect('payment:wallet_dashboard')

    campaign_id = request.session.get('campaign_payment_campaign_id')
    amount = request.session.get('campaign_payment_amount', 0)

    if not campaign_id:
        messages.error(request, "اطلاعات کمپین یافت نشد.")
        return redirect('payment:wallet_dashboard')

    campaign = get_object_or_404(
        Campaign,
        id=campaign_id,
        advertiser=request.user.advertiser_profile
    )

    invoice = create_campaign_invoice(campaign)

    if status == 'OK':
        try:
            result = services.verify_payment(
                slug="zarinpal",
                authority=authority
            )

            if result.status.lower() == 'complete':
                with transaction.atomic():
                    payment = Payment.objects.create(
                        user=request.user,
                        invoice=invoice,
                        amount=amount,
                        status=Payment.Status.SUCCESS,
                        payment_method=Payment.Method.GATEWAY,
                        authority=authority,
                        ref_id=result.reference_id,
                    )

                    Transaction.objects.create(
                        user=request.user,
                        amount=amount,
                        type=Transaction.Type.GATEWAY_PAYMENT,
                        status=Transaction.Status.SUCCESS,
                        campaign=campaign,
                        invoice=invoice,
                        payment=payment,
                        reference_id=result.reference_id,
                        description=f"پرداخت کمپین {campaign.name} از طریق زرین‌پال - کد پیگیری: {result.reference_id}"
                    )

                    invoice.is_paid = True
                    invoice.paid_at = timezone.now()
                    invoice.save(update_fields=["is_paid", "paid_at"])

                    for coupon in [campaign.influencer_coupon, campaign.content_team_coupon, campaign.platform_coupon]:
                        if coupon:
                            coupon.used_count += 1
                            coupon.save(update_fields=["used_count"])

                    submit_campaign_for_review(campaign)

                for key in ['campaign_payment_authority', 'campaign_payment_campaign_id',
                            'campaign_payment_amount', 'campaign_payment_invoice_id']:
                    if key in request.session:
                        del request.session[key]

                if 'campaign_draft_id' in request.session:
                    del request.session['campaign_draft_id']

                messages.success(
                    request,
                    f"پرداخت کمپین {campaign.name} با موفقیت انجام شد. "
                    f"کد پیگیری: {result.reference_id}"
                )
                return redirect("advertisers:campaign_detail", campaign.id)

            else:
                messages.error(request, f"پرداخت ناموفق بود. وضعیت: {result.status}")
                return redirect('campaigns:campaign_create_step4')

        except Exception as e:
            messages.error(request, f"خطا در تأیید پرداخت: {str(e)}")
            return redirect('campaigns:campaign_create_step4')

    else:
        messages.warning(request, "پرداخت توسط کاربر لغو شد یا ناموفق بود.")
        return redirect('campaigns:campaign_create_step4')


@login_required
def standalone_order_payment_callback(request):
    """کالبک بازگشت از درگاه زرین‌پال برای پرداخت سفارش مستقل تولید محتوا"""
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')

    if not authority:
        messages.error(request, "اطلاعات پرداخت یافت نشد.")
        return redirect('content_team:standalone_order_step3')

    order_id = request.session.get('standalone_payment_order_id')
    amount = request.session.get('standalone_payment_amount', 0)
    invoice_id = request.session.get('standalone_payment_invoice_id')

    if not order_id:
        messages.error(request, "اطلاعات سفارش یافت نشد.")
        return redirect('content_team:standalone_order_step1')

    order = get_object_or_404(
        ContentOrder,
        id=order_id,
        standalone_user=request.user,
        is_standalone=True
    )

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        content_order=order
    )

    if invoice.is_paid:
        messages.warning(request, 'این سفارش قبلاً پرداخت شده است.')
        for key in ['standalone_payment_authority', 'standalone_payment_order_id',
                    'standalone_payment_amount', 'standalone_payment_invoice_id']:
            if key in request.session:
                del request.session[key]
        return redirect('home')

    if status == 'OK':
        try:
            result = services.verify_payment(
                slug="zarinpal",
                authority=authority
            )

            if result.status.lower() == 'complete':
                with transaction.atomic():
                    payment = Payment.objects.create(
                        user=request.user,
                        invoice=invoice,
                        amount=amount,
                        status=Payment.Status.SUCCESS,
                        payment_method=Payment.Method.GATEWAY,
                        authority=authority,
                        ref_id=result.reference_id,
                    )

                    Transaction.objects.create(
                        user=request.user,
                        amount=amount,
                        type=Transaction.Type.CONTENT_ORDER_PAYMENT,
                        status=Transaction.Status.SUCCESS,
                        invoice=invoice,
                        payment=payment,
                        reference_id=result.reference_id,
                        description=f"پرداخت سفارش مستقل تولید محتوا #{order.id} از طریق زرین‌پال - کد پیگیری: {result.reference_id}"
                    )

                    invoice.is_paid = True
                    invoice.paid_at = timezone.now()
                    invoice.save(update_fields=["is_paid", "paid_at"])

                    order.status = ContentOrder.Status.PENDING
                    order.save(update_fields=['status'])

                    if hasattr(order, 'content_team_coupon') and order.content_team_coupon:
                        order.content_team_coupon.used_count += 1
                        order.content_team_coupon.save(update_fields=["used_count"])

                    if hasattr(order, 'platform_coupon') and order.platform_coupon:
                        order.platform_coupon.used_count += 1
                        order.platform_coupon.save(update_fields=["used_count"])

                for key in ['standalone_payment_authority', 'standalone_payment_order_id',
                            'standalone_payment_amount', 'standalone_payment_invoice_id',
                            'standalone_order_step1', 'standalone_order_step2']:
                    if key in request.session:
                        del request.session[key]

                from notifications.utils import create_notification
                create_notification(
                    user=request.user,
                    notification_type='new_content_order',
                    title='✅ سفارش شما با موفقیت ثبت شد',
                    message=f'سفارش تولید محتوا شما با شناسه #{order.id} با موفقیت ثبت شد.\n'
                            f'تیم «{order.team.name}» به زودی سفارش شما را بررسی میکند.',
                    link=f'/content_team/team/orders/{order.id}',
                    related_object_id=order.id,
                    related_content_type='ContentOrder'
                )

                from notifications.utils import notify_content_team_new_order
                active_members = order.team.members.filter(is_active=True).select_related('user')
                for member in active_members:
                    notify_content_team_new_order(member.user, order)

                messages.success(
                    request,
                    f"✅ پرداخت سفارش تولید محتوا #{order.id} با موفقیت انجام شد. "
                    f"کد پیگیری: {result.reference_id}"
                )
                return redirect('advertisers:content_order_detail', order.id)

            else:
                messages.error(request, f"پرداخت ناموفق بود. وضعیت: {result.status}")
                return redirect('content_team:standalone_order_step3')

        except Exception as e:
            messages.error(request, f"خطا در تأیید پرداخت: {str(e)}")
            return redirect('content_team:standalone_order_step3')

    else:
        messages.warning(request, "پرداخت توسط کاربر لغو شد یا ناموفق بود.")

        Payment.objects.create(
            user=request.user,
            invoice=invoice,
            amount=amount,
            status=Payment.Status.FAILED,
            payment_method=Payment.Method.GATEWAY,
            authority=authority,
        )

        for key in ['standalone_payment_authority', 'standalone_payment_order_id',
                    'standalone_payment_amount', 'standalone_payment_invoice_id']:
            if key in request.session:
                del request.session[key]

        return redirect('content_team:standalone_order_step3')