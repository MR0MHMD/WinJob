# market/api_views.py
import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from market.models import Product


@require_GET
def bot_active_product_api(request):
    """
    API برای بات بله — دریافت اطلاعات محصول فعال
    GET /api/bot/product/active/
    """
    now = timezone.now()

    # پیدا کردن محصول فعال
    product = Product.objects.filter(
        status=Product.Status.ACTIVE,
        campaign_start__lte=now,
        campaign_end__gte=now,
    ).prefetch_related('images').first()

    if not product:
        # اگر کمپین فعالی نبود، آخرین محصول فعال
        product = Product.objects.filter(
            status=Product.Status.ACTIVE
        ).prefetch_related('images').first()

    if not product:
        return JsonResponse({
            'ok': False,
            'error': 'هیچ محصول فعالی یافت نشد.'
        }, status=404)

    # ---- تصاویر ----
    images = []
    if product.main_image:
        images.append(product.main_image.url)
    for img in product.images.all():
        if img.image and img.image.url not in images:
            images.append(img.image.url)

    # ---- مشخصات ----
    specs = []
    for pf in product.features.select_related('feature').all():
        specs.append(f"• {pf.feature.name}: {pf.value}")

    # ---- اقساط ----
    import math
    INSTALLMENT_COUNT = 4
    final_price = product.final_price
    regular = math.floor(final_price / INSTALLMENT_COUNT / 1000) * 1000
    last = final_price - regular * (INSTALLMENT_COUNT - 1)

    # ---- دکمه شیشه‌ای ----
    from django.urls import reverse
    checkout_url = request.build_absolute_uri(
        reverse('market:guest_checkout', kwargs={'product_id': product.pk})
    )

    return JsonResponse({
        'ok': True,
        'data': {
            'product_id': product.pk,
            'title': product.title,
            'short_description': product.short_description or '',
            'description': (product.description or '')[:500],
            'base_price': product.base_price,
            'discount_price': product.discount_price,
            'final_price': final_price,
            'discount_percent': product.discount_percent,
            'images': images,
            'specs': specs,
            'installment': {
                'count': INSTALLMENT_COUNT,
                'regular_amount': regular,
                'last_amount': last,
                'is_uniform': regular == last,
            },
            'stock': product.stock,
            'checkout_url': checkout_url,
            'campaign_end_ts': (
                int(product.campaign_end.timestamp() * 1000)
                if product.campaign_end else None
            ),
        }
    })
