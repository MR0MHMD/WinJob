from ..forms import CustomUserForm, AdvertiserProfileForm, InfluencerProfileForm
from django.contrib.auth.decorators import login_required
from influencers.forms import InfluencerProfileForm
from advertisers.forms import AdvertiserProfileForm
from django.shortcuts import render, redirect
from django.contrib import messages


@login_required
def edit_profile(request):
    user = request.user

    user_form = CustomUserForm(instance=user)
    profile_form = None

    if user.is_advertiser:
        profile_form = AdvertiserProfileForm(instance=user.advertiser_profile)
    elif user.is_influencer:
        profile_form = InfluencerProfileForm(instance=user.influencer_profile)

    if request.method == 'POST':
        user_form = CustomUserForm(request.POST, request.FILES, instance=user)

        if user.is_advertiser:
            profile_form = AdvertiserProfileForm(request.POST, instance=user.advertiser_profile)
        elif user.is_influencer:
            profile_form = InfluencerProfileForm(request.POST, instance=user.influencer_profile)

        if user_form.is_valid() and (not profile_form or profile_form.is_valid()):
            user_form.save()
            if profile_form:
                profile_form.save()

            messages.success(request, 'اطلاعات پروفایل با موفقیت بروزرسانی شد!')
            return redirect('accounts:edit_profile')
        else:
            messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'accounts/forms/edit_profile.html', context)
