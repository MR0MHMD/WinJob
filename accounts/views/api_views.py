from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from accounts.forms import ProfileUpdateForm
from django.http import JsonResponse
from django.contrib import messages


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
        return redirect('/admin')
