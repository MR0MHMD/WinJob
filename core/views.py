# views.py

import json
from datetime import timedelta
from django.shortcuts import render
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone

from influencers.models import InfluencerProfile, InfluencerChannel, InfluencerReview
from content_team.models import ContentTeam
from campaigns.models import CampaignInvoice, CampaignClick
from core.models import Category
from blog.models import Post
from plat_form.models import Platform



def home(request):
    # ========== آمار کلی پلتفرم ==========
    total_influencers = InfluencerProfile.objects.filter(is_active=True).count()
    total_channels = InfluencerChannel.objects.filter(is_active=True).count()

    # مجموع هزینه‌های سایت (از فاکتورهای پرداخت شده)
    total_spent = CampaignInvoice.objects.filter(is_paid=True).aggregate(total=Sum('payable_amount'))['total'] or 0

    total_clicks = CampaignClick.objects.count()

    # ========== پلتفرم‌ها با آمار ==========
    platforms = Platform.objects.filter(is_active=True).annotate(
        channels_count=Count('influencer_channels', filter=Q(influencer_channels__is_active=True))
    ).order_by('-channels_count')

    # ========== برترین کانال‌ها (جایگزین اینفلوئنسرهای برتر) ==========
    top_channels_raw = InfluencerChannel.objects.filter(
        is_active=True,
        influencer__is_active=True  # اینفلوئنسر مربوطه هم فعال باشه
    ).annotate(
        total_bookings=Count('campaign_bookings', filter=Q(campaign_bookings__status='completed')),
        avg_channel_rating=Avg('influencer__reviews__rating')
    ).filter(total_bookings__gt=0).order_by('-total_bookings')[:5]

    top_channels = sorted(top_channels_raw, key=lambda x: x.avg_channel_rating or 0, reverse=True)[:8]

    content_teams_raw = ContentTeam.objects.filter(is_active=True)
    content_teams = sorted(content_teams_raw, key=lambda x: x.avg_rating or 0, reverse=True)[:5]

    recent_reviews = InfluencerReview.objects.select_related(
        'influencer', 'advertiser__user'
    ).order_by('-created_at')[:10]

    blog_posts = Post.published.order_by('-created_at')[:4]

    context = {
        'total_influencers': total_influencers,
        'total_channels': total_channels,
        'total_spent': total_spent,
        'total_clicks': total_clicks,
        'platforms': platforms,
        'top_channels': top_channels,
        'content_teams': content_teams,
        'recent_reviews': recent_reviews,
        'blog_posts': blog_posts,
        'now': timezone.now(),
    }

    return render(request, 'core/pages/index.html', context)
