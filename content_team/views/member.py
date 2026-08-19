from content_team.models import TeamJoinRequest, ContentTeam, ContentTeamMember
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from content_team.forms import TeamManageForm
from accounts.models import CustomUser
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum


@login_required
def team_members_manage(request, team_slug):
    """
    مدیریت اعضای تیم توسط مدیر تیم
    """
    new_user = None
    team = get_object_or_404(ContentTeam, slug=team_slug)

    pending_requests = TeamJoinRequest.objects.filter(team=team, status=TeamJoinRequest.Status.PENDING)
    pending_requests_count = pending_requests.count()

    try:
        current_member = ContentTeamMember.objects.get(team=team, user=request.user)
        if current_member.role != ContentTeamMember.Role.MANAGER:
            messages.error(request, 'شما دسترسی مدیریت این تیم را ندارید.')
            return redirect('home')
    except ContentTeamMember.DoesNotExist:
        messages.error(request, 'شما عضو این تیم نیستید.')
        return redirect('home')

    if request.method == 'POST' and 'add_member' in request.POST:
        user_id = request.POST.get('user_id')
        role = request.POST.get('role')
        revenue_share_percent = request.POST.get('revenue_share_percent')

        errors = []
        if not user_id:
            errors.append('کاربر را انتخاب کنید')
        if not role:
            errors.append('نقش را انتخاب کنید')
        if not revenue_share_percent:
            errors.append('درصد سهم را وارد کنید')

        if not errors:
            try:
                revenue_share_percent = int(revenue_share_percent)
                if revenue_share_percent < 0 or revenue_share_percent > 100:
                    errors.append('درصد سهم باید بین 0 تا 100 باشد')
            except ValueError:
                errors.append('درصد سهم معتبر نیست')

        if not errors:
            try:
                new_user = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                errors.append('کاربر مورد نظر یافت نشد')

        if not errors:
            if ContentTeamMember.objects.filter(team=team, user=new_user).exists():
                errors.append('این کاربر قبلاً عضو تیم است')

        if not errors:
            current_total = team.members.filter(is_active=True).aggregate(
                total=Sum('revenue_share_percent')
            )['total'] or 0

            if current_total + revenue_share_percent > 100:
                errors.append(
                    f'مجموع درصد سهام اعضای فعال از 100 بیشتر میشود. (فعلاً {current_total}% + {revenue_share_percent}% = {current_total + revenue_share_percent}%)')

        if not errors:
            ContentTeamMember.objects.create(
                team=team,
                user=new_user,
                role=role,
                revenue_share_percent=revenue_share_percent,
                is_active=True
            )
            messages.success(request, f'عضو {new_user.nickname} با موفقیت به تیم اضافه شد.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)
        else:
            for error in errors:
                messages.error(request, error)

    if request.method == 'POST' and 'edit_member' in request.POST:
        member_id = request.POST.get('member_id')
        role = request.POST.get('role')
        revenue_share_percent = request.POST.get('revenue_share_percent')

        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

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
            other_members_total = team.members.filter(is_active=True).exclude(id=member.id).aggregate(
                total=Sum('revenue_share_percent')
            )['total'] or 0

            if other_members_total + revenue_share_percent > 100:
                errors.append(
                    f'مجموع درصد سهام از 100 بیشتر میشود. (سایر اعضا {other_members_total}% + این عضو {revenue_share_percent}% = {other_members_total + revenue_share_percent}%)')

        if not errors:
            member.role = role
            member.revenue_share_percent = revenue_share_percent
            member.save()
            messages.success(request, f'اطلاعات {member.user.nickname} با موفقیت ویرایش شد.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)
        else:
            for error in errors:
                messages.error(request, error)

    if request.method == 'POST' and 'expel_member' in request.POST:
        member_id = request.POST.get('member_id')
        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

        if member.user == request.user:
            messages.error(request, 'شما نمی‌توانید خودتان را از تیم اخراج کنید.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)

        user_nickname = member.user.nickname
        member.delete()
        messages.success(request, f'{user_nickname} از تیم اخراج شد.')
        return redirect('content_team:team_members_manage', team_slug=team.slug)

    if request.method == 'POST' and 'deactivate_member' in request.POST:
        member_id = request.POST.get('member_id')
        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

        if member.user == request.user:
            messages.error(request, 'شما نمی‌توانید خودتان را غیرفعال کنید.')
            return redirect('content_team:team_members_manage', team_slug=team.slug)

        member.is_active = False
        member.save()
        messages.success(request, f'{member.user.nickname} غیرفعال شد.')
        return redirect('content_team:team_members_manage', team_slug=team.slug)

    if request.method == 'POST' and 'activate_member' in request.POST:
        member_id = request.POST.get('member_id')
        member = get_object_or_404(ContentTeamMember, id=member_id, team=team)

        current_total = team.members.filter(is_active=True).aggregate(
            total=Sum('revenue_share_percent')
        )['total'] or 0

        if current_total + member.revenue_share_percent > 100:
            messages.error(request,
                           f'با فعال کردن {member.user.nickname}، مجموع درصد سهام از 100 بیشتر میشود. (فعلاً {current_total}% + {member.revenue_share_percent}% = {current_total + member.revenue_share_percent}%)')
            return redirect('content_team:team_members_manage', team_slug=team.slug)

        member.is_active = True
        member.save()
        messages.success(request, f'{member.user.nickname} دوباره فعال شد.')
        return redirect('content_team:team_members_manage', team_slug=team.slug)

    members = team.members.all()
    active_members = members.filter(is_active=True)
    inactive_members = members.filter(is_active=False)

    total_percent = active_members.aggregate(total=Sum('revenue_share_percent'))['total'] or 0
    is_valid = total_percent == 100

    existing_member_ids = members.values_list('user_id', flat=True)
    available_users = CustomUser.objects.exclude(id__in=existing_member_ids).filter(is_active=True)

    context = {
        'team': team,
        'pending_requests': pending_requests,
        'pending_requests_count': pending_requests_count,
        'members': members,
        'active_members': active_members,
        'inactive_members': inactive_members,
        'total_percent': total_percent,
        'is_valid': is_valid,
        'available_users': available_users,
        'role_choices': ContentTeamMember.Role.choices,
        'current_member': current_member,
    }

    return render(request, 'content_team/forms/team_members.html', context)


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


@login_required
def team_manage_view(request):
    # پیدا کردن عضو تیم برای کاربر جاری
    try:
        team_member = ContentTeamMember.objects.select_related('team').get(user=request.user, is_active=True)
    except ContentTeamMember.DoesNotExist:
        messages.error(request, "شما عضو هیچ تیم فعالی نیستید.")
        return redirect('core:home')

    # بررسی نقش مدیر بودن
    if team_member.role != ContentTeamMember.Role.MANAGER:
        messages.error(request, "شما دسترسی مدیریت این تیم را ندارید.")
        return redirect('accounts:dashboard_router')

    team = team_member.team

    # ذخیره اسلاگ قبلی برای بررسی تغییر
    old_slug = team.slug

    # پردازش فرم
    if request.method == 'POST':
        form = TeamManageForm(request.POST, request.FILES, instance=team)
        if form.is_valid():
            team = form.save(commit=False)

            # ========== چک کردن تغییر اسلاگ ==========
            if team.slug != old_slug:
                # ۱. حذف QR Code قدیمی از استوریج
                if team.qr_code:
                    try:
                        if default_storage.exists(team.qr_code.name):
                            default_storage.delete(team.qr_code.name)
                    except Exception as e:
                        print(f"⚠️ خطا در حذف QR Code قدیمی: {e}")

                # ۲. پاک کردن فیلد QR Code از دیتابیس
                team.qr_code = None

            # ذخیره تیم
            team.save()

            # ========== تولید QR Code جدید (اگه پاک شده بود) ==========
            if not team.qr_code:
                try:
                    team.generate_qr(force=True)
                    # رفرش از دیتابیس برای آدرس جدید
                    team.refresh_from_db()
                except Exception as e:
                    print(f"⚠️ خطا در تولید QR Code جدید: {e}")

            messages.success(request, "اطلاعات تیم با موفقیت به‌روزرسانی شد.")
            return redirect('content_team:team_manage')
        else:
            messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")
    else:
        form = TeamManageForm(instance=team)

    context = {
        'team': team,
        'form': form,
        'members': team.members.filter(is_active=True).select_related('user'),
        'total_percent': team.get_total_revenue_percent(),
    }
    return render(request, 'content_team/forms/team_management.html', context)
