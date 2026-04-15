from django.http import JsonResponse
from location.models import Province
from django.db.models import Count, Q


def get_provinces_data(request):
    """دریافت دیتای استان‌ها برای نقشه"""
    provinces = Province.objects.annotate(
        influencer_count=Count('influencers', filter=Q(influencers__is_active=True))
    ).values('id', 'name', 'slug', 'influencer_count', 'latitude', 'longitude')

    return JsonResponse(list(provinces), safe=False)