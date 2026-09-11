from campaigns.services.raiting_service import submit_team_review_service
from content_team.models import ContentTeam, ContentOrder, TeamReview
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@require_GET
def check_slug_availability(request):
    slug = request.GET.get('slug', '').strip()
    team_id = request.GET.get('team_id', None)

    if not slug:
        return JsonResponse({'available': False, 'error': 'اسلاگ نمی‌تواند خالی باشد.'})

    # بررسی یکتایی به جز تیم فعلی
    qs = ContentTeam.objects.filter(slug=slug)
    if team_id and team_id.isdigit():
        qs = qs.exclude(id=int(team_id))

    is_available = not qs.exists()

    return JsonResponse({
        'available': is_available,
        'message': 'این اسلاگ قابل استفاده است.' if is_available else 'این اسلاگ قبلاً توسط تیم دیگری استفاده شده است.'
    })


@login_required
@require_POST
def submit_team_review_ajax(request):
    try:
        order_id = request.POST.get('order_id')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        team_id = request.POST.get('team_id')

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

        if order_id:
            order = ContentOrder.objects.select_related('campaign__advertiser', 'team').get(id=order_id)
            if order.campaign.advertiser != advertiser:
                return JsonResponse({'success': False, 'message': 'شما دسترسی به این نظر ندارید.'})
            if hasattr(order, 'review'):
                return JsonResponse({'success': False, 'message': 'شما قبلاً برای این سفارش نظر ثبت کرده‌اید.'})
            submit_team_review_service(order, advertiser, rating, comment)
            return JsonResponse({'success': True, 'message': 'نظر شما با موفقیت ثبت شد. +5 امتیاز به شما تعلق گرفت.'})
        else:
            if not team_id:
                return JsonResponse({'success': False, 'message': 'شناسه تیم یافت نشد.'})
            team = ContentTeam.objects.get(id=team_id)
            if TeamReview.objects.filter(team=team, advertiser=advertiser).exists():
                return JsonResponse({'success': False, 'message': 'شما قبلاً برای این تیم نظر ثبت کرده‌اید.'})
            TeamReview.objects.create(
                team=team,
                advertiser=advertiser,
                rating=rating,
                comment=comment,
                order=None
            )
            return JsonResponse({'success': True, 'message': 'نظر عمومی شما با موفقیت ثبت شد.'})
    except ContentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'سفارش مورد نظر یافت نشد.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_POST
def edit_team_review_ajax(request):
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
            if not 1 <= rating <= 5:
                raise ValueError
        except ValueError:
            return JsonResponse({'success': False, 'message': 'امتیاز باید بین 1 تا 5 باشد.'})

        review = TeamReview.objects.get(id=review_id)
        if not hasattr(request.user, 'advertiser_profile') or review.advertiser != request.user.advertiser_profile:
            return JsonResponse({'success': False, 'message': 'شما دسترسی به ویرایش این نظر ندارید.'})
        review.rating = rating
        review.comment = comment
        review.save()
        return JsonResponse({'success': True, 'message': 'نظر شما با موفقیت ویرایش شد.'})
    except TeamReview.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'نظر مورد نظر یافت نشد.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# content_team/api_views.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from payment.models import Coupon
from payment.services.create_invoice import create_standalone_invoice
from ..models import ContentOrder
import json
import traceback


# content_team/api.py

@require_POST
@login_required
def standalone_apply_discount(request):
    """
    اعمال کد تخفیف برای سفارش مستقل تولید محتوا
    """
    try:
        body = json.loads(request.body)
        code = body.get("code", "").strip()
        scope = body.get("scope", "")

        if not code:
            return JsonResponse({"success": False, "message": "کد تخفیف وارد نشده است."}, status=400)

        if scope not in ['content_team', 'platform']:
            return JsonResponse({"success": False, "message": "نوع تخفیف نامعتبر است."}, status=400)

        order_id = request.session.get('standalone_order_step2', {}).get('order_id')
        if not order_id:
            return JsonResponse({"success": False, "message": "سفارش یافت نشد."}, status=400)

        order = get_object_or_404(
            ContentOrder,
            id=order_id,
            standalone_user=request.user,
            is_standalone=True
        )

        # ========== نقشه اسکوپ به فیلدهای مدل ==========
        scope_field_map = {
            'content_team': 'content_team_coupon',  # ✅ اسم فیلد واقعی
            'platform': 'platform_coupon'            # ✅ اسم فیلد واقعی
        }

        # چک کردن کوپن‌های موجود
        existing_coupon = getattr(order, scope_field_map[scope])
        if existing_coupon:
            return JsonResponse({
                "success": False,
                "message": f"شما قبلاً از یک کد تخفیف برای این بخش استفاده کرده‌اید."
            }, status=400)

        try:
            coupon = Coupon.objects.get(code__iexact=code, scope=scope)
        except Coupon.DoesNotExist:
            return JsonResponse({"success": False, "message": "کد تخفیف معتبر نیست."}, status=404)

        if not coupon.is_valid():
            return JsonResponse({
                "success": False,
                "message": "این کد تخفیف قابل استفاده نیست (منقضی شده یا استفاده شده)."
            }, status=400)

        # ========== اعمال کوپن ==========
        if scope == 'content_team':
            order.content_team_coupon = coupon
        else:
            order.platform_coupon = coupon

        order.save(update_fields=[scope_field_map[scope]])

        # ساخت فاکتور جدید
        invoice = create_standalone_invoice(order)

        return JsonResponse({
            "success": True,
            "message": "کد تخفیف با موفقیت اعمال شد.",
            "scope": scope,
            "coupon_code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": float(coupon.value),

            "base_content_cost": invoice.base_content_cost,
            "base_commission": invoice.base_commission,
            "content_discount_amount": invoice.content_discount_amount,
            "platform_discount_amount": invoice.platform_discount_amount,

            "discount_amount": invoice.discount_amount,
            "discount_amount_formatted": f"{invoice.discount_amount:,}",
            "payable_amount": invoice.payable_amount,
            "payable_amount_formatted": f"{invoice.payable_amount:,}",
            "final_total": invoice.total_amount,
            "final_total_formatted": f"{invoice.total_amount:,}",
            "commission": invoice.commission,
            "commission_formatted": f"{invoice.commission:,}",
            "content_cost": invoice.content_cost,
            "content_cost_formatted": f"{invoice.content_cost:,}",
            "content_vat": invoice.content_vat,
            "commission_vat": invoice.commission_vat,
            "total_vat": invoice.total_vat,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)