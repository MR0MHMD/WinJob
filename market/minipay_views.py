import logging
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, FormView
from django.contrib import messages
from django.utils import timezone

from market.models import Product, GuestOrder
from market.forms import GuestCheckoutForm, GuestOTPForm
from market.services.minipay import MinipayClient, MinipayError

logger = logging.getLogger(__name__)


class GuestCheckoutView(FormView):
    """صفحه پر کردن آدرس + ساخت سفارش مهمان"""
    template_name = 'market/guest/guest_checkout.html'
    form_class = GuestCheckoutForm

    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(
            Product, pk=kwargs['product_id'], status=Product.Status.ACTIVE,
        )
        # اگه قبلاً سفارش نیمه‌کاره‌ای برای این محصول ساخته شده، بیخیالش
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['product'] = self.product
        ctx['campaign_active'] = self.product.is_on_campaign

        # Preload cities for dependent dropdown
        from core.models import City
        cities = City.objects.values('id', 'name', 'province_id').order_by('name')
        cities_by_province = {}
        for c in cities:
            cities_by_province.setdefault(c['province_id'], []).append({
                'id': c['id'],
                'name': c['name'],
            })
        ctx['cities_by_province'] = cities_by_province
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        order = GuestOrder.objects.create(
            product=self.product,
            product_title=self.product.title,
            unit_price=self.product.final_price,
            quantity=1,
            total_amount=self.product.final_price,
            phone_number=data['phone_number'],
            national_id=data['national_id'],
            receiver_name=data['receiver_name'],
            province=data['province'],
            city=data['city'],
            address=data['address'],
            postal_code=data.get('postal_code', ''),
            status=GuestOrder.Status.PENDING,
        )
        return redirect('market:guest_pay_initiate', order_id=order.pk)


class GuestPaymentInitiateView(View):
    """
    شروع پرداخت: استعلام + پیش‌تراکنش
    روی خطا: order.status = FAILED و redirect به result
    """

    def get(self, request, order_id):
        order = get_object_or_404(GuestOrder, pk=order_id)

        if order.is_paid:
            return redirect('market:guest_pay_result', order_id=order.pk)

        try:
            client = MinipayClient()

            inquiry_id = client.get_inquiry(
                input_value=order.phone_number,
                amount=order.total_amount,
            )
            order.inquiry_id = inquiry_id
            order.status = GuestOrder.Status.INQUIRY_OK
            order.save(update_fields=['inquiry_id', 'status', 'updated_at'])

            pre_id = client.pre_transaction(
                inquiry_id=inquiry_id,
                credit_amount=order.total_amount,
            )
            order.pre_transaction_id = pre_id
            order.status = GuestOrder.Status.AWAITING_OTP
            order.save(update_fields=['pre_transaction_id', 'status', 'updated_at'])

        except MinipayError as e:
            logger.warning("GuestOrder %s initiation failed: %s", order.pk, e)
            order.status = GuestOrder.Status.FAILED
            order.payment_error = str(e)[:2000]
            order.save(update_fields=['status', 'payment_error', 'updated_at'])
            return redirect('market:guest_pay_result', order_id=order.pk)

        return redirect('market:guest_pay_verify', order_id=order.pk)


class GuestPaymentVerifyView(FormView):
    """صفحه ورود رمز خرید ۶ رقمی"""
    template_name = 'market/guest/guest_otp.html'
    form_class = GuestOTPForm

    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(GuestOrder, pk=kwargs['order_id'])
        # اگه هنوز به مرحله OTP نرسیده یا قبلاً پرداخت شده، بفرستش جای مناسب
        if self.order.is_paid:
            return redirect('market:guest_pay_result', order_id=self.order.pk)
        if self.order.status != GuestOrder.Status.AWAITING_OTP:
            return redirect('market:guest_pay_initiate', order_id=self.order.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        return ctx

    def form_valid(self, form):
        password = form.cleaned_data['purchase_password']
        try:
            client = MinipayClient()
            data = client.set_transaction(
                pre_transaction_id=self.order.pre_transaction_id,
                purchase_password=password,
            )
            self.order.transaction_id = data.get('transaction_id', '')
            self.order.payment_ref_id = data.get('ref_id', data.get('transaction_id', ''))
            self.order.status = GuestOrder.Status.PAID
            self.order.paid_at = timezone.now()
            self.order.payment_error = ''
            self.order.save()
        except MinipayError as e:
            self.order.payment_error = str(e)[:2000]
            self.order.save(update_fields=['payment_error', 'updated_at'])
            form.add_error('purchase_password', str(e))
            return self.form_invalid(form)

        return redirect('market:guest_pay_result', order_id=self.order.pk)


class GuestPaymentResultView(TemplateView):
    """صفحه نتیجه نهایی — موفق یا ناموفق"""
    template_name = 'market/guest/guest_result.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = get_object_or_404(GuestOrder, pk=kwargs['order_id'])
        return ctx


import json
import re
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from market.models import Product, SupportOrderRequest


@require_POST
@csrf_protect
def support_order_request(request):
    """
    دریافت درخواست تماس پشتیبان از مودال landing
    ورودی: phone, national_id, product_id (اختیاری)
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body or '{}')
        else:
            data = request.POST
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

    phone = (data.get('phone') or '').strip()
    national_id = (data.get('national_id') or '').strip()
    product_id = data.get('product_id')

    # ---- اعتبارسنجی ----
    errors = {}
    if not re.fullmatch(r'09\d{9}', phone):
        errors['phone'] = 'شماره تلفن باید با ۰۹ شروع شده و ۱۱ رقم باشد.'
    if not re.fullmatch(r'\d{10}', national_id):
        errors['national_id'] = 'کد ملی باید دقیقاً ۱۰ رقم باشد.'
    # چک‌سام کد ملی
    elif len(set(national_id)) == 1:
        errors['national_id'] = 'کد ملی معتبر نیست.'
    else:
        checksum = sum(int(national_id[i]) * (10 - i) for i in range(9)) % 11
        c = int(national_id[9])
        if not ((checksum < 2 and c == checksum) or (checksum >= 2 and c == 11 - checksum)):
            errors['national_id'] = 'کد ملی معتبر نیست.'

    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    # ---- ضد اسپم ساده: در ۱۰ دقیقه گذشته نهایتاً ۳ بار ----
    from datetime import timedelta
    ten_min_ago = timezone.now() - timedelta(minutes=10)
    recent = SupportOrderRequest.objects.filter(
        phone_number=phone, created_at__gte=ten_min_ago,
    ).count()
    if recent >= 3:
        return JsonResponse(
            {'ok': False, 'error': 'لطفاً کمی بعد دوباره تلاش کنید.'},
            status=429,
        )

    # ---- محصول (اختیاری) ----
    product = None
    if product_id:
        try:
            product = Product.objects.filter(pk=int(product_id)).first()
        except (ValueError, TypeError):
            product = None

    # ---- ذخیره ----
    obj = SupportOrderRequest.objects.create(
        product=product,
        phone_number=phone,
        national_id=national_id,
        source_ip=request.META.get('REMOTE_ADDR'),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:255],
    )

    return JsonResponse({
        'ok': True,
        'message': 'درخواست شما ثبت شد. کارشناسان ما به زودی با شما تماس می‌گیرند.',
        'id': obj.pk,
    })