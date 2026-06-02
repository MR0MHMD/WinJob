from .models import InfluencerServiceRate, InfluencerReview, InfluencerChannel
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from decimal import InvalidOperation, Decimal
from .forms import InfluencerProfileForm
from django.http import JsonResponse
from campaigns.models import AdType
from django.views.decorators.http import require_POST
from campaigns.models import CampaignInfluencer
from campaigns.services.raiting_service import submit_influencer_review_service
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

    try:
        body = json.loads(request.body)
        price_raw = str(body.get('price', '')).strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'داده نامعتبر'}, status=400)

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


@login_required
@require_POST
def submit_influencer_review_ajax(request):
    try:
        booking_id = request.POST.get('booking_id')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()

        if not rating:
            return JsonResponse({'success': False, 'message': 'لطفاً امتیاز خود را انتخاب کنید.'})
        if not comment:
            return JsonResponse({'success': False, 'message': 'لطفاً نظر خود را بنویسید.'})

        try:
            rating = int(rating)
            if not 1 <= rating <= 5:
                raise ValueError
        except ValueError:
            return JsonResponse({'success': False, 'message': 'امتیاز باید بین 1 تا 5 باشد.'})

        advertiser = request.user.advertiser_profile

        if booking_id:
            booking = CampaignInfluencer.objects.select_related('campaign__advertiser', 'channel').get(id=booking_id)

            if booking.campaign.advertiser != advertiser:
                return JsonResponse({'success': False, 'message': 'شما دسترسی به این نظر ندارید.'})
            if hasattr(booking, 'review'):
                return JsonResponse({'success': False, 'message': 'شما قبلاً برای این همکاری نظر ثبت کرده‌اید.'})

            submit_influencer_review_service(booking, advertiser, rating, comment)
            return JsonResponse({'success': True, 'message': 'نظر شما با موفقیت ثبت شد. +5 امتیاز به شما تعلق گرفت.'})

        else:
            channel_id = request.POST.get('channel_id')
            if not channel_id:
                return JsonResponse({'success': False, 'message': 'شناسه کانال یافت نشد.'})
            channel = InfluencerChannel.objects.get(id=channel_id)
            if InfluencerReview.objects.filter(channel=channel, advertiser=advertiser).exists():
                return JsonResponse({'success': False, 'message': 'شما قبلاً برای این کانال نظر ثبت کرده‌اید.'})
            InfluencerReview.objects.create(
                channel=channel,
                advertiser=advertiser,
                rating=rating,
                comment=comment,
                campaign_booking=None
            )
            from gamification.services import update_score
            return JsonResponse(
                {'success': True, 'message': 'نظر عمومی شما با موفقیت ثبت شد.'})

    except CampaignInfluencer.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'همکاری مورد نظر یافت نشد.'})
    except InfluencerChannel.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'کانال مورد نظر یافت نشد.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_POST
def edit_influencer_review_ajax(request):
    try:
        review_id = request.POST.get('review_id')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()

        if not review_id or not rating:
            return JsonResponse({'success': False, 'message': 'اطلاعات ناقص است.'})

        if not comment:
            return JsonResponse({'success': False, 'message': 'لطفاً نظر خود را بنویسید.'})

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            return JsonResponse({'success': False, 'message': 'امتیاز باید بین 1 تا 5 باشد.'})

        review = InfluencerReview.objects.get(id=review_id)

        if not hasattr(request.user, 'advertiser_profile') or review.advertiser != request.user.advertiser_profile:
            return JsonResponse({'success': False, 'message': 'شما دسترسی به ویرایش این نظر ندارید.'})

        review.rating = rating
        review.comment = comment
        review.save()

        return JsonResponse({'success': True, 'message': 'نظر شما با موفقیت ویرایش شد.'})

    except InfluencerReview.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'نظر مورد نظر یافت نشد.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
