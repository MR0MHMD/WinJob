from payment.services.create_invoice import complete_wallet_payment
from django_iranian_payment.contrib.django import services
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from payment.models import Transaction, Invoice
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse


@login_required
def wallet_dashboard(request):
    """
    صفحه اصلی کیف پول - نمایش موجودی و تراکنش‌ها
    """
    wallet = request.user.wallet

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]

    context = {
        'wallet': wallet,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'payment/wallet/wallet_dashboard.html', context)


@login_required
@require_GET
def load_more_transactions(request):
    """
    API برای لود تراکنش‌های بیشتر (Ajax)
    فقط 10 تای بعدی رو برمیگردونه
    """
    try:
        page = int(request.GET.get('page', 1))
        per_page = 5

        all_transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')

        paginator = Paginator(all_transactions, per_page)

        if page > paginator.num_pages:
            return JsonResponse({
                'transactions': [],
                'has_more': False,
                'error': False
            })

        current_page = paginator.page(page)

        transactions_data = []
        for transaction_ in current_page:
            trans_type = 'other'
            if transaction_.type == 'deposit':
                trans_type = 'deposit'
            elif transaction_.type == 'withdraw':
                trans_type = 'withdraw'
            elif transaction_.type == 'purchase':
                trans_type = 'purchase'

            transactions_data.append({
                'id': transaction_.id,
                'title': transaction_.get_type_display(),
                'type': trans_type,
                'amount': transaction_.amount,
                'is_income': transaction_.is_income,
                'description': transaction_.description if transaction_.description else '',
                'date': transaction_.created_at.strftime('%Y/%m/%d %H:%M'),
            })

        return JsonResponse({
            'transactions': transactions_data,
            'has_more': current_page.has_next(),
            'current_page': page,
            'error': False
        })

    except EmptyPage:
        return JsonResponse({
            'transactions': [],
            'has_more': False,
            'error': False
        })
    except Exception as e:
        print(f"Error in load_more_transactions: {e}")
        return JsonResponse({
            'transactions': [],
            'has_more': False,
            'error': True,
            'message': str(e)
        })


@login_required
def wallet_deposit(request):
    """
    صفحه شارژ کیف پول با درگاه زرین‌پال
    """
    if request.method == 'POST':
        amount = request.POST.get('amount')

        # ========== اعتبارسنجی مبلغ ==========
        try:
            amount = int(amount)
            if amount < 100000:
                messages.error(request, "حداقل مبلغ شارژ ۱,۰۰۰ تومان است.")
                return redirect('payment:wallet_deposit')

            if amount > 50000000:
                messages.error(request, "حداکثر مبلغ شارژ ۵۰,۰۰۰,۰۰۰ تومان است.")
                return redirect('payment:wallet_deposit')

        except (ValueError, TypeError):
            messages.error(request, "مبلغ وارد شده معتبر نیست.")
            return redirect('payment:wallet_deposit')

        # ========== شروع فرآیند پرداخت ==========
        try:
            payment_result, redirect_url = services.start_payment(
                slug="zarinpal",
                amount=amount,
                callback_url=request.build_absolute_uri(
                    reverse('payment:payment_callback')
                ),
                order_id=f"wallet_{request.user.id}_{int(timezone.now().timestamp())}",
                description=f"شارژ کیف پول کاربر {request.user.phone_number} - مبلغ {amount:,} تومان",
                mobile=request.user.phone_number,
            )

            # ✅ فقط authority و مبلغ رو توی session نگه دار
            # (فاکتور بعد از callback موفق ساخته میشه)
            request.session['payment_authority'] = payment_result.authority
            request.session['payment_amount'] = amount

            return redirect(redirect_url)

        except Exception as e:
            messages.error(request, f"خطا در اتصال به درگاه پرداخت: {str(e)}")
            return redirect('payment:wallet_deposit')

    return render(request, 'payment/wallet/wallet_deposit.html')


@login_required
def payment_callback(request):
    """
    کالبک بازگشت از درگاه زرین‌پال
    - فاکتور فقط بعد از پرداخت موفق ساخته میشه
    """
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')

    if not authority:
        messages.error(request, "اطلاعات پرداخت یافت نشد.")
        return redirect('payment:wallet_deposit')

    # ✅ از session میخونیم (نه از دیتابیس)
    session_authority = request.session.get('payment_authority')
    amount = request.session.get('payment_amount', 0)

    if not session_authority or session_authority != authority:
        messages.error(request, "اطلاعات پرداخت معتبر نیست.")
        return redirect('payment:wallet_deposit')

    if not amount:
        messages.error(request, "مبلغ پرداخت یافت نشد.")
        return redirect('payment:wallet_deposit')

    if status == 'OK':
        try:
            result = services.verify_payment(
                slug="zarinpal",
                authority=authority
            )

            if result.status.lower() == 'complete':

                # ✅ فاکتور فقط اینجا ساخته میشه (بعد از پرداخت موفق)
                invoice = complete_wallet_payment(
                    user=request.user,
                    amount=amount,
                    ref_id=result.reference_id,
                    authority=authority,
                )

                # پاک کردن سشن
                for key in ['payment_authority', 'payment_amount']:
                    if key in request.session:
                        del request.session[key]

                messages.success(
                    request,
                    f"کیف پول شما به مبلغ {amount:,} تومان با موفقیت شارژ شد. "
                    f"کد پیگیری: {result.reference_id}"
                )
                return redirect('payment:wallet_dashboard')

            else:
                messages.error(request, f"پرداخت ناموفق بود. وضعیت: {result.status}")
                return redirect('payment:wallet_deposit')

        except Exception as e:
            messages.error(request, f"خطا در تأیید پرداخت: {str(e)}")
            return redirect('payment:wallet_deposit')

    else:
        messages.warning(request, "پرداخت توسط کاربر لغو شد یا ناموفق بود.")
        return redirect('payment:wallet_deposit')
