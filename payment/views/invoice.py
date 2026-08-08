from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from payment.models import Transaction, CampaignInvoice
from payment.utils import number_to_words
from campaigns.models import Campaign
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction


@login_required
def invoice_list(request):
    """لیست فاکتورهای تبلیغ‌دهنده"""

    # فقط تبلیغ‌دهنده‌ها
    if not hasattr(request.user, 'advertiser_profile'):
        messages.error(request, "شما دسترسی به این بخش ندارید.")
        return redirect('home')

    # دریافت همه فاکتورهای کمپین‌های این تبلیغ‌دهنده
    invoices = CampaignInvoice.objects.filter(
        campaign__advertiser=request.user.advertiser_profile
    ).select_related('campaign').order_by('-created_at')

    # فیلتر بر اساس وضعیت پرداخت
    status_filter = request.GET.get('status')
    if status_filter == 'paid':
        invoices = invoices.filter(is_paid=True)
    elif status_filter == 'unpaid':
        invoices = invoices.filter(is_paid=False)

    context = {
        'invoices': invoices,
        'status_filter': status_filter,
        'total_count': invoices.count(),
        'paid_count': invoices.filter(is_paid=True).count(),
        'unpaid_count': invoices.filter(is_paid=False).count(),
    }

    return render(request, 'payment/invoices/invoice_list.html', context)


@login_required
def invoice_detail(request, invoice_id):
    """جزئیات یک فاکتور"""

    if not hasattr(request.user, 'advertiser_profile'):
        messages.error(request, "شما دسترسی به این بخش ندارید.")
        return redirect('home')

    invoice = get_object_or_404(
        CampaignInvoice.objects.select_related(
            'campaign',
            'campaign__platform',
            'campaign__advertiser',
            'campaign__advertiser__user',
        ),
        id=invoice_id,
        campaign__advertiser=request.user.advertiser_profile
    )

    # دریافت تراکنش‌های مرتبط
    transactions = Transaction.objects.filter(
        invoice=invoice
    ).order_by('-created_at')

    # دریافت تعداد اینفلوئنسرهای کمپین
    influencer_count = invoice.campaign.influencer_bookings.count()

    context = {
        'invoice': invoice,
        'transactions': transactions,
        'influencer_count': influencer_count,
        'can_cancel': not invoice.is_paid,
        'can_pay': not invoice.is_paid,
    }

    return render(request, 'payment/invoices/invoice_detail.html', context)


@login_required
def invoice_print(request, invoice_id):
    """
    نمایش نسخه پرینت فاکتور
    """

    if not hasattr(request.user, 'advertiser_profile'):
        messages.error(request, "شما دسترسی به این بخش ندارید.")
        return redirect('home')

    invoice = get_object_or_404(
        CampaignInvoice.objects.select_related(
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
        campaign__advertiser=request.user.advertiser_profile
    )

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

    if not hasattr(request.user, 'advertiser_profile'):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'شما دسترسی به این بخش ندارید.'}, status=403)
        messages.error(request, "شما دسترسی به این بخش ندارید.")
        return redirect('home')

    try:
        invoice = get_object_or_404(
            CampaignInvoice,
            id=invoice_id,
            campaign__advertiser=request.user.advertiser_profile,
            is_paid=False
        )
    except CampaignInvoice.DoesNotExist:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'فاکتور یافت نشد یا قبلاً پرداخت شده است.'}, status=404)
        messages.error(request, "فاکتور یافت نشد یا قبلاً پرداخت شده است.")
        return redirect('payment:invoice_list')

    campaign = invoice.campaign

    if campaign.status not in [Campaign.Status.DRAFT, Campaign.Status.PENDING]:
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

    if not hasattr(request.user, 'advertiser_profile'):
        messages.error(request, "شما دسترسی به این بخش ندارید.")
        return redirect('home')

    invoice = get_object_or_404(
        CampaignInvoice,
        id=invoice_id,
        campaign__advertiser=request.user.advertiser_profile,
        is_paid=False
    )

    campaign = invoice.campaign

    # ذخیره شناسه کمپین در session برای استفاده در استپ ۴
    request.session['campaign_draft_id'] = campaign.id

    return redirect('campaigns:campaign_create_step4')
