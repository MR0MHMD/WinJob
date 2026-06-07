from content_team.models import TeamJoinRequest, ContentTeam, ContentTeamMember, ContentOrder, TeamReview
from campaigns.services.raiting_service import submit_team_review_service
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum


@login_required
def team_member_edit(request, team_slug, member_id):
    """
    ویرایش سریع یک عضو (با ریدایرکت به صفحه اصلی مدیریت)
    """
    team = get_object_or_404(ContentTeam, slug=team_slug)

    try:
        current_member = ContentTeamMember.objects.get(team=team, user=request.user)
        if current_member.role != ContentTeamMember.Role.MANAGER:
            messages.error(request, 'شما دسترسی مدیریت این تیم را ندارید.')
            return redirect('core:home')
    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو این تیم نیستید.')
        return redirect('core:home')

    member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

    if request.method == 'POST':
        role = request.POST.get('role')
        revenue_share_percent = request.POST.get('revenue_share_percent')

        errors = []

        if not role:
            errors.append('نقش را انتخاب کنید')

        try:
            revenue_share_percent = int(revenue_share_percent)
            if revenue_share_percent < 0 or revenue_share_percent > 100:
                errors.append('درصد سهم باید بین 0 تا 100 باشد')
        except ValueError:
            errors.append('درصد سهم معتبر نیست')

        if not errors:
            other_total = team.members.filter(is_active=True).exclude(id=member.id).aggregate(
                total=Sum('revenue_share_percent')
            )['total'] or 0

            if other_total + revenue_share_percent > 100:
                errors.append(f'مجموع درصد سهام از 100 بیشتر میشود. (سایر اعضا {other_total}%)')

        if not errors:
            member.role = role
            member.revenue_share_percent = revenue_share_percent
            member.save()
            messages.success(request, f'اطلاعات {member.user.nickname} با موفقیت ویرایش شد.')
        else:
            for error in errors:
                messages.error(request, error)

        return redirect('content_team:team_members_manage', team_slug=team.slug)

    return redirect('content_team:team_members_manage', team_slug=team.slug)


@login_required
def team_join_request_handle(request, team_slug, request_id):
    """
    مدیریت درخواست عضویت در تیم (تایید یا رد) توسط مدیر تیم
    """

    team = get_object_or_404(ContentTeam, slug=team_slug)

    try:
        current_member = ContentTeamMember.objects.get(team=team, user=request.user)
        if current_member.role != ContentTeamMember.Role.MANAGER:
            messages.error(request, 'شما دسترسی مدیریت این تیم را ندارید.')
            return redirect('team_members_manage', team_slug=team.slug)
    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو این تیم نیستید.')
        return redirect('home')

    join_request = get_object_or_404(TeamJoinRequest, id=request_id, team=team)

    if join_request.status != TeamJoinRequest.Status.PENDING:
        messages.warning(request, 'این درخواست قبلاً بررسی شده است.')
        return redirect('team_members_manage', team_slug=team.slug)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            role = request.POST.get('role')
            revenue_share_percent = request.POST.get('revenue_share_percent')

            errors = []
            if not role:
                errors.append('لطفاً نقش را انتخاب کنید')

            try:
                revenue_share_percent = int(revenue_share_percent)
                if revenue_share_percent < 0 or revenue_share_percent > 100:
                    errors.append('درصد سهم باید بین 0 تا 100 باشد')
            except (ValueError, TypeError):
                errors.append('درصد سهم معتبر نیست')

            if not errors:
                current_total = team.get_total_revenue_percent()
                if current_total + revenue_share_percent > 100:
                    errors.append(
                        f'مجموع درصد سهام از 100 بیشتر می‌شود. (در حال حاضر {current_total}% + {revenue_share_percent}% = {current_total + revenue_share_percent}%)')

            if not errors:
                with transaction.atomic():
                    ContentTeamMember.objects.create(
                        team=team,
                        user=join_request.user,
                        role=role,
                        revenue_share_percent=revenue_share_percent,
                        is_active=True
                    )

                    join_request.status = TeamJoinRequest.Status.APPROVED
                    join_request.save()

                messages.success(request,
                                 f'درخواست {join_request.user.nickname} با موفقیت تایید شد و به تیم اضافه گردید.')
                return redirect('content_team:team_members_manage', team_slug=team.slug)
            else:
                for error in errors:
                    messages.error(request, error)
                return redirect('content_team:team_members_manage', team_slug=team.slug)

        elif action == 'reject':
            with transaction.atomic():
                join_request.status = TeamJoinRequest.Status.REJECTED
                join_request.save()

            messages.success(request, f'درخواست {join_request.user.nickname} با موفقیت رد شد.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)

    messages.error(request, 'درخواست نامعتبر است.')
    return redirect('content_team:team_members_manage', team_slug=team.slug)


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
            from content_team.models import ContentTeam
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
