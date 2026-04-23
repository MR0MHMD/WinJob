from .models import TeamJoinRequest, ContentTeam, ContentTeamMember
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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
