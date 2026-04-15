from .models import InfluencerChannel, InfluencerServiceRate
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from decimal import InvalidOperation, Decimal
from .forms import InfluencerProfileForm
from django.http import JsonResponse
from campaigns.models import AdType
import json


@login_required
def profile_update(request):
    if request.method == 'POST':
        form = InfluencerProfileForm(
            request.POST,
            request.FILES,
            instance=request.user.influencer_profile
        )

        if form.is_valid():
            form.save()
            return JsonResponse({
                'status': 'success',
                'message': 'data save was successfully'
            })

        return JsonResponse({
            'status': 'error',
            'message': form.errors
        })

    return JsonResponse({
        'status': 'error',
        'message': 'your request must be POST'
    })


@login_required
def rate_inline_edit(request, channel_id, ad_type_id):
    """ذخیره inline قیمت تعرفه"""
    try:
        influencer = request.user.influencer_profile
    except:
        return JsonResponse({'success': False, 'error': 'پروفایل یافت نشد'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'متد نامعتبر'}, status=405)

    channel = get_object_or_404(InfluencerChannel, pk=channel_id, influencer=influencer)
    ad_type = get_object_or_404(AdType, pk=ad_type_id, platform=channel.platform)

    # ← اینجا تغییر کرد: JSON body رو بخون
    try:
        body = json.loads(request.body)
        price_raw = str(body.get('price', '')).strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'داده نامعتبر'}, status=400)

    # اگه قیمت خالی بود، آبجکت رو حذف کن
    if not price_raw:
        InfluencerServiceRate.objects.filter(channel=channel, ad_type=ad_type).delete()
        return JsonResponse({
            'success': True,
            'deleted': True,
            'formatted_price': 'هنوز مشخص نشده',
        })

    try:
        price = Decimal(price_raw)
        if price < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        return JsonResponse({'success': False, 'error': 'قیمت وارد شده معتبر نیست'}, status=400)

    rate, created = InfluencerServiceRate.objects.update_or_create(
        channel=channel,
        ad_type=ad_type,
        defaults={'price': price, 'is_active': True}
    )

    return JsonResponse({
        'success': True,
        'deleted': False,
        'formatted_price': rate.formatted_price(),
        'created': created,
    })
