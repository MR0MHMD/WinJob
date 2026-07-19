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
