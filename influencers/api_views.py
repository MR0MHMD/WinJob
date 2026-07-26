from campaigns.services.campaigns_notifications import approve_influencer_report_service, reject_influencer_report_service
from campaigns.services.raiting_service import submit_influencer_review_service
from .models import InfluencerServiceRate, InfluencerReview, InfluencerChannel
from influencers.models import CampaignChannel, CampaignReport
from .services.verification_service import VerificationService
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from decimal import InvalidOperation, Decimal
from .forms import InfluencerProfileForm
from django.http import JsonResponse
from django.conf import settings
from django.urls import reverse
from core.models import AdType
import requests
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
            booking = CampaignChannel.objects.select_related('campaign__advertiser', 'channel').get(id=booking_id)

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

    except CampaignChannel.DoesNotExist:
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


@login_required
def verify_channel_modal(request, channel_id):
    channel = get_object_or_404(InfluencerChannel, id=channel_id, influencer__user=request.user)

    # ریست خودکار اگر قفل تمام شده باشد
    VerificationService.reset_if_cooldown_expired(channel)

    if channel.status == 'approved':
        return JsonResponse({'status': 'already_verified', 'message': 'این کانال قبلاً تأیید شده است.'})

    if channel.status == 'rejected' and VerificationService.is_cooldown_active(channel):
        remaining = VerificationService.get_cooldown_remaining(channel)
        return JsonResponse({
            'status': 'error',
            'message': f'کانال شما رد شده است. لطفاً {remaining} ساعت دیگر برای تأیید مجدد اقدام کنید.'
        }, status=403)

    # اگر کد قبلی منقضی شده، کد جدید بساز
    if VerificationService.is_code_expired(channel):
        code = VerificationService.set_verification_code(channel)
    else:
        code = channel.verification_code

    return JsonResponse({
        'status': 'ok',
        'code': code,
        'target_url': channel.url or '',
        'channel_id': channel.id,
    })


@login_required
@require_http_methods(["POST"])
def start_verification(request, channel_id):
    channel = get_object_or_404(InfluencerChannel, id=channel_id, influencer__user=request.user)

    # ریست خودکار اگر قفل تمام شده باشد
    VerificationService.reset_if_cooldown_expired(channel)

    if channel.status == 'approved':
        return JsonResponse({'status': 'error', 'message': 'کانال قبلاً تأیید شده است.'}, status=400)

    if VerificationService.is_cooldown_active(channel):
        remaining_hours = VerificationService.get_cooldown_remaining(channel)
        return JsonResponse({
            'status': 'error',
            'message': f'کانال شما رد شده است. لطفاً {remaining_hours} ساعت دیگر مجدد تلاش کنید.'
        }, status=400)

    if not channel.verification_code or VerificationService.is_code_expired(channel):
        return JsonResponse({'status': 'error', 'message': 'کد منقضی شده است. لطفاً صفحه را دوباره بارگیری کنید.'}, status=400)

    code = channel.verification_code
    target_url = channel.url
    if not target_url:
        return JsonResponse({'status': 'error', 'message': 'آدرس کانال وارد نشده است.'}, status=400)

    callback_url = request.build_absolute_uri(
        reverse('influencers:verification_callback', args=[channel.id])
    )

    success, message = VerificationService.start_verification(target_url, code, callback_url)
    if success:
        return JsonResponse({'status': 'pending', 'message': message})
    else:
        return JsonResponse({'status': 'error', 'message': message}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def verification_callback(request, channel_id):
    channel = get_object_or_404(InfluencerChannel, id=channel_id)

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'status': 'error', 'message': 'JSON نامعتبر'}, status=400)

    status = data.get('status')
    code = data.get('code')

    if not code or channel.verification_code != code:
        return JsonResponse({'status': 'error', 'message': 'کد نامعتبر است.'}, status=400)

    if VerificationService.is_code_expired(channel):
        return JsonResponse({'status': 'error', 'message': 'کد منقضی شده است.'}, status=400)

    if status == 'verified':
        VerificationService.record_successful_verification(channel)
        return JsonResponse({'status': 'ok'})
    else:  # status == 'failed'
        is_rejected = VerificationService.record_failed_attempt(channel)
        if is_rejected:
            message = "کانال شما به دلیل ۳ بار تأیید ناموفق رد شد. لطفاً ۷۲ ساعت بعد دوباره تلاش کنید."
        else:
            remaining = 3 - channel.verification_failed_attempts
            message = f"کد در صفحه پیدا نشد. {remaining} تلاش دیگر دارید."
        return JsonResponse({'status': 'failed', 'message': message}, status=200)


@login_required
def verification_status(request, channel_id):
    channel = get_object_or_404(InfluencerChannel, id=channel_id, influencer__user=request.user)

    # ریست خودکار اگر قفل تمام شده باشد (برای نمایش وضعیت صحیح)
    VerificationService.reset_if_cooldown_expired(channel)

    if channel.status == 'approved':
        return JsonResponse({'status': 'approved'})
    elif channel.status == 'rejected':
        remaining_hours = VerificationService.get_cooldown_remaining(channel)
        return JsonResponse({
            'status': 'rejected',
            'message': f'کانال رد شده است. {remaining_hours} ساعت دیگر می‌توانید تلاش کنید.'
        })
    elif channel.verification_failed_attempts > 0 and channel.status == 'pending':
        remaining = 3 - channel.verification_failed_attempts
        return JsonResponse({
            'status': 'failed',
            'message': f'کد پیدا نشد. {remaining} تلاش دیگر دارید.'
        })
    else:
        return JsonResponse({'status': 'pending'})


def trigger_n8n_verification(report_id, post_link, expected_caption, expected_tracking_link, platform_slug):
    webhook_url = settings.N8N_CAMPAIGN_REPORT_WEBHOOK
    payload = {
        "report_id": report_id,
        "post_link": post_link,
        "expected_caption": expected_caption,
        "expected_tracking_link": expected_tracking_link,
        "platform_slug": platform_slug,
        "callback_url": f"{settings.SITE_URL}/influencers/report/{report_id}/n8n-callback/"
    }
    headers = {"X-Callback-Token": settings.N8N_CALLBACK_SECRET}
    try:
        requests.post(webhook_url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"❌ Failed to trigger n8n: {e}")


# ========== ویوی برگشت نتیجه از n8n ==========
@csrf_exempt
@require_http_methods(["POST"])
def n8n_report_callback(request, report_id):
    """
    n8n بعد از بررسی کامل، نتیجه رو به این آدرس POST می‌کنه.
    نمونه body:
    {
        "status": "approved",  // یا "rejected"
        "auto_check_details": {
            "link_found": true,
            "text_match_score": 92.5,
            "image_match_score": 87.0,
            "checked_at": "2025-01-15T12:00:00Z",
            "errors": []
        },
        "admin_notes": "متن تبلیغ کامل تطابق داشت ولی تصویر کمی تغییر کرده بود."
    }
    """
    # 1. بررسی توکن امنیتی (اختیاری اما توصیه میشه)
    auth_header = request.headers.get("X-Callback-Token")
    if auth_header != settings.N8N_CALLBACK_SECRET:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    # 2. گرفتن گزارش
    try:
        report = CampaignReport.objects.select_related('campaign_influencer').get(id=report_id)
    except CampaignReport.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Report not found"}, status=404)

    # 3. اگر قبلاً تایید یا رد شده، دیگه تغییری نکن
    if report.status != CampaignReport.Status.PENDING:
        return JsonResponse({"status": "error", "message": f"Report already {report.status}"}, status=400)

    # 4. خوندن داده‌های ارسالی از n8n
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    new_status = data.get("status")
    auto_details = data.get("auto_check_details", {})
    admin_notes = data.get("admin_notes", "")

    if new_status not in ["approved", "rejected"]:
        return JsonResponse({"status": "error", "message": "Invalid status"}, status=400)

    # 5. به‌روزرسانی گزارش
    report.auto_check_details = auto_details
    report.admin_notes = admin_notes  # می‌تونه یادداشت n8n یا دلیل رد باشه

    # 6. فراخوانی سرویس‌های تأیید/رد (که نوتیفیکیشن و پرداخت رو انجام می‌دن)
    if new_status == "approved":
        approve_influencer_report_service(report)
    else:
        # دلیل رد رو از فیلد admin_notes می‌گیریم
        reason = admin_notes or "بررسی خودکار: مغایرت محتوا"
        reject_influencer_report_service(report, reason=reason)

    return JsonResponse({"status": "ok", "message": f"Report {new_status} successfully"})
