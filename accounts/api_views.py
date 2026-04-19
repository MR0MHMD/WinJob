from content_team.models import ContentTeam, TeamJoinRequest, ContentTeamMember
from accounts.services.registration_service import RegistrationService
from .forms import RegistrationForm, LoginForm, ProfileUpdateForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.http import HttpResponseForbidden
from core.utils import generate_random_slug
from .models import CustomUser, Transaction
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction



def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            password = form.cleaned_data['password']
            user = authenticate(request, phone_number=phone_number, password=password)
            if user is not None:
                login(request, user)
                return JsonResponse({"success": True, "redirect_url": '/'})
            else:
                return JsonResponse({"success": False, "error": "نام کاربری یا رمز عبور اشتباه است."})
    else:
        form = LoginForm()
    return JsonResponse({"success": False, "error": "درخواست نامعتبر است."})


def register_view(request):
    user = request.user

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "درخواست نامعتبر است."})

    form = RegistrationForm(request.POST)

    if not form.is_valid():
        return JsonResponse({
            "success": False,
            "error": form.errors
        })

    phone = form.cleaned_data["phone_number"]
    nickname = form.cleaned_data["nickname"]
    password = form.cleaned_data["password"]
    role = form.cleaned_data["role"]

    try:
        with transaction.atomic():
            if role == "advertiser":
                user, profile = RegistrationService.register_advertiser(
                    phone_number=phone,
                    password=password,
                    nickname=nickname
                )

            elif role == "influencer":
                user, profile = RegistrationService.register_influencer(
                    phone_number=phone,
                    password=password,
                    nickname=nickname
                )

            elif role == "team_member":
                create_new_team = form.cleaned_data.get("create_new_team")

                if create_new_team:
                    # ساخت تیم جدید - کاربر به عنوان مدیر تیم ثبت می‌شود
                    team_name = form.cleaned_data.get("team_name")

                    if not team_name:
                        raise ValueError("لطفاً نام تیم را وارد کنید")

                    # ساخت تیم جدید با اسلاگ تصادفی
                    new_team = ContentTeam.objects.create(
                        name=team_name,
                        slug=generate_random_slug(),
                        is_active=True
                    )
                    team = new_team
                    is_manager = True

                    # ثبت کاربر به عنوان عضو تیم (مدیر)
                    user, team_member = RegistrationService.register_team_member(
                        phone_number=phone,
                        password=password,
                        nickname=nickname,
                        team=team,
                        is_manager=is_manager
                    )

                else:
                    # عضویت در تیم موجود - ایجاد درخواست عضویت
                    team_slug = form.cleaned_data.get("team_slug")

                    if not team_slug:
                        raise ValueError("لطفاً شناسه تیم را وارد کنید")

                    team = ContentTeam.objects.get(slug=team_slug, is_active=True)

                    # ثبت کاربر معمولی (بدون عضویت در تیم)
                    user = CustomUser.objects.create_user(
                        phone_number=phone,
                        password=password,
                        nickname=nickname
                    )

                    if ContentTeamMember.objects.filter(team=team, user=user).exists():
                        raise ValueError("شما قبلاً عضو این تیم هستید.")

                    existing_request = TeamJoinRequest.objects.filter(team=team, user=user).first()

                    if existing_request and existing_request.status == TeamJoinRequest.Status.PENDING:
                        raise ValueError("شما قبلاً درخواست عضویت برای این تیم ثبت کرده‌اید. در انتظار تایید مدیر.")

                    if existing_request and existing_request.status == TeamJoinRequest.Status.APPROVED:
                        raise ValueError("شما قبلاً عضو این تیم شده‌اید.")

                    TeamJoinRequest.objects.create(
                        team=team,
                        user=user,
                        status=TeamJoinRequest.Status.PENDING
                    )

            login(request, user)



            return JsonResponse({
                "success": True,
                "redirect_url": "/"
            })

    except ContentTeam.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "تیم مورد نظر یافت نشد. لطفاً شناسه تیم را بررسی کنید."
        })
    except ValueError as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"خطایی رخ داده است: {str(e)}"
        })
    return redirect("core:home")


def logout_view(request):
    logout(request)
    return redirect("core:home")


@login_required
def user_update(request):
    """ویرایش پروفایل شخصی (فقط ایمیل و نام مستعار)."""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'information save successfully'})
        else:
            return JsonResponse({'status': 'error', 'message': form.errors})


@login_required
def delete_account(request):
    """
    ویو برای حذف حساب کاربری
    """
    if request.method == "POST":
        user = request.user
        user.delete()  # حذف کاربر
        messages.success(request, 'حساب کاربری شما با موفقیت حذف شد.')
        return redirect('core:home')
    return HttpResponseForbidden("Only POST requests are allowed.")


@login_required
def dashboard_router(request):
    if request.user.is_advertiser:
        return redirect("advertisers:dashboard")
    elif request.user.is_influencer:
        return redirect("influencers:dashboard")
    elif request.user.is_team_member:
        return redirect("content_team:dashboard")
    else:
        return redirect('core:home')

