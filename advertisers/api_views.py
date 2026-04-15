from django.http import JsonResponse
from .forms import AdvertiserProfileForm
from django.contrib.auth.decorators import login_required


@login_required
def profile_update(request):
    """ویرایش پروفایل کسب‌وکار."""
    if request.method == 'POST':
        form = AdvertiserProfileForm(request.POST, instance=request.user.advertiser_profile)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'data save was successfully'})
        else:
            return JsonResponse({'status': 'error', 'message': form.errors})
    else:
        form = AdvertiserProfileForm(instance=request.user.advertiser_profile)
    return JsonResponse({'status': 'error', 'message': 'your request must be POST'})
