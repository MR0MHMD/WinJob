from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django_iranian_payment.contrib.django import services

from campaigns.services.campaigns_notifications import submit_campaign_for_review
from payment.models import Transaction, Invoice, Payment
from payment.services.create_invoice import create_campaign_invoice
from payment.utils import number_to_words
from campaigns.models import Campaign
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Q


@login_required
def invoice_list(request):
    """لیست فاکتورهای کاربر (هم کمپین و هم کیف پول)"""

    # دریافت همه فاکتورهای کاربر (هم کمپین و هم کیف پول)
    invoices = Invoice.objects.filter(
        user=request.user
    ).select_related('campaign').order_by('-created_at')

    # فیلتر بر اساس نوع فاکتور
    type_filter = request.GET.get('type')
    if type_filter == 'campaign':
        invoices = invoices.filter(type=Invoice.Type.CAMPAIGN)
    elif type_filter == 'wallet':
        invoices = invoices.filter(type=Invoice.Type.WALLET)

    # فیلتر بر اساس وضعیت پرداخت
    status_filter = request.GET.get('status')
    if status_filter == 'paid':
        invoices = invoices.filter(is_paid=True)
    elif status_filter == 'unpaid':
        invoices = invoices.filter(is_paid=False)

    context = {
        'invoices': invoices,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'total_count': invoices.count(),
        'paid_count': invoices.filter(is_paid=True).count(),
        'unpaid_count': invoices.filter(is_paid=False).count(),
        'campaign_count': invoices.filter(type=Invoice.Type.CAMPAIGN).count(),
        'wallet_count': invoices.filter(type=Invoice.Type.WALLET).count(),
    }

    return render(request, 'payment/invoices/invoice_list.html', context)


@login_required
def invoice_detail(request, invoice_id):
    """جزئیات یک فاکتور (هم کمپین و هم کیف پول)"""

    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'user',
            'campaign',
            'campaign__platform',
            'campaign__advertiser',
            'campaign__advertiser__user',
        ),
        id=invoice_id,
        user=request.user
    )

    # دریافت تراکنش‌های مرتبط
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
    }

    # اطلاعات اضافی برای فاکتور کمپین
    if invoice.type == Invoice.Type.CAMPAIGN and invoice.campaign:
        influencer_count = invoice.campaign.influencer_bookings.count()
        context['influencer_count'] = influencer_count
        context['campaign'] = invoice.campaign

    return render(request, 'payment/invoices/invoice_detail.html', context)


@login_required
def invoice_print(request, invoice_id):
    """
    نمایش نسخه پرینت فاکتور (هم کمپین و هم کیف پول)
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
        ),
        id=invoice_id,
        user=request.user
    )

    # ========== فاکتور کیف پول ==========
    if invoice.type == Invoice.Type.WALLET:
        payable_amount_rial = invoice.wallet_deposit_amount * 10  # تبدیل به ریال
        payable_amount_words = number_to_words(payable_amount_rial, 'ریال')

        context = {
            'invoice': invoice,
            'is_wallet_invoice': True,
            'payable_amount_rial': payable_amount_rial,
            'payable_amount_words': payable_amount_words,
            'wallet_deposit_amount': invoice.wallet_deposit_amount,
        }
        return render(request, 'payment/invoices/invoice_print.html', context)

    # ========== فاکتور کمپین ==========
    influencer_count = invoice.campaign.influencer_bookings.count()

    # ============================================================
    # محاسبه مبالغ به ریال (ضرب در ۱۰)
    # ============================================================
    def convert_to_rial(value):
        return value * 10

    # مبالغ پایه (ریالی)
    base_influencer_cost_rial = convert_to_rial(invoice.base_influencer_cost)
    base_content_cost_rial = convert_to_rial(invoice.base_content_cost)
    base_commission_rial = convert_to_rial(invoice.base_commission)

    # مبالغ تخفیف (ریالی)
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

    # مبالغ نهایی (ریالی)
    influencer_cost_rial = convert_to_rial(invoice.influencer_cost + invoice.influencer_vat)
    content_cost_rial = convert_to_rial(invoice.content_cost + invoice.content_vat)
    commission_rial = convert_to_rial(invoice.commission + invoice.commission_vat)
    total_amount_rial = convert_to_rial(invoice.total_amount)
    payable_amount_rial = convert_to_rial(invoice.payable_amount)

    # تبدیل مبلغ نهایی به حروف (واحد ریال)
    payable_amount_words = number_to_words(payable_amount_rial, 'ریال')

    context = {
        'invoice': invoice,
        'influencer_count': influencer_count,
        'is_campaign_invoice': True,

        # پاس دادن تمام مبالغ ریالی به تمپلیت
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

    # فقط فاکتورهای کمپین قابل لغو هستند
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
    campaign.delete()  # فاکتور هم به صورت آبشاری حذف میشه

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

    # فقط فاکتورهای کمپین قابل پرداخت هستند
    if invoice.type != Invoice.Type.CAMPAIGN:
        messages.error(request, "این فاکتور قابل پرداخت نیست.")
        return redirect('payment:invoice_list')

    campaign = invoice.campaign

    if not campaign:
        messages.error(request, "کمپین یافت نشد.")
        return redirect('payment:invoice_list')

    # ذخیره شناسه کمپین در session برای استفاده در استپ ۴
    request.session['campaign_draft_id'] = campaign.id

    return redirect('campaigns:campaign_create_step4')


@login_required
def campaign_payment_callback(request):
    """
    کالبک بازگشت از درگاه زرین‌پال برای پرداخت کمپین
    """
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')

    if not authority:
        messages.error(request, "اطلاعات پرداخت یافت نشد.")
        return redirect('payment:wallet_dashboard')

    # دریافت اطلاعات از سشن
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
            # تأیید پرداخت در زرین‌پال
            result = services.verify_payment(
                slug="zarinpal",
                authority=authority
            )

            if result.status.lower() == 'complete':
                with transaction.atomic():
                    # ========== ثبت پرداخت موفق ==========
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

                    # ========== افزایش استفاده از کوپن‌ها ==========
                    for coupon in [campaign.influencer_coupon, campaign.content_team_coupon, campaign.platform_coupon]:
                        if coupon:
                            coupon.used_count += 1
                            coupon.save(update_fields=["used_count"])

                    # ========== ارسال کمپین به مرحله بررسی ==========
                    submit_campaign_for_review(campaign)

                # پاک کردن سشن
                for key in ['campaign_payment_authority', 'campaign_payment_campaign_id',
                            'campaign_payment_amount', 'campaign_payment_invoice_id']:
                    if key in request.session:
                        del request.session[key]

                # حذف کمپین از سشن
                if 'campaign_draft_id' in request.session:
                    del request.session['campaign_draft_id']

                messages.success(
                    request,
                    f"پرداخت کمپین {campaign.name} با موفقیت انجام شد. "
                    f"کد پیگیری: {result.reference_id}"
                )
                return redirect("advertisers:campaigns_list")

            else:
                messages.error(request, f"پرداخت ناموفق بود. وضعیت: {result.status}")
                return redirect('campaigns:campaign_create_step4')

        except Exception as e:
            messages.error(request, f"خطا در تأیید پرداخت: {str(e)}")
            return redirect('campaigns:campaign_create_step4')

    else:
        messages.warning(request, "پرداخت توسط کاربر لغو شد یا ناموفق بود.")
        return redirect('campaigns:campaign_create_step4')