from influencers.models import InfluencerChannel, InfluencerReview, InfluencerProfile
from campaigns.models import CampaignClick, Campaign
from django.db.models import Count, Q, Avg
from content_team.models import ContentTeam
from plat_form.models import Platform
from django.shortcuts import render
from django.utils import timezone
from django.http import Http404
from blog.models import Post
from accounts.models import CustomUser


def home(request):
    total_influencers = InfluencerProfile.objects.filter(is_active=True).count()
    total_campaigns = Campaign.objects.filter(status=Campaign.Status.COMPLETED).count()
    total_channels = InfluencerChannel.objects.filter(is_active=True).count()
    total_teams = ContentTeam.objects.filter(is_active=True).count()
    total_clicks = CampaignClick.objects.count()

    platforms = Platform.objects.filter(is_active=True).annotate(
        channels_count=Count('influencer_channels', filter=Q(influencer_channels__is_active=True))
    ).order_by('-channels_count')

    top_channels_raw = InfluencerChannel.objects.filter(
        is_active=True,
        influencer__is_active=True
    ).annotate(
        total_bookings=Count('campaign_bookings', filter=Q(campaign_bookings__status='completed')),
        avg_channel_rating=Avg('reviews__rating')
    ).filter(total_bookings__gt=0).order_by('-total_bookings')[:5]

    top_channels = sorted(top_channels_raw, key=lambda x: x.avg_channel_rating or 0, reverse=True)[:8]

    content_teams_raw = ContentTeam.objects.filter(is_active=True)
    content_teams = sorted(content_teams_raw, key=lambda x: x.avg_rating or 0, reverse=True)[:5]

    recent_reviews = InfluencerReview.objects.select_related(
        'channel', 'advertiser__user'
    ).order_by('-created_at')[:10]

    blog_posts = Post.published.order_by('-created_at')[:4]

    brand_testimonials = [
        {'name': 'دیجیکالا', 'logo': 'digikala.png',
         'text': 'همکاری با وینجاب نرخ تبدیل کمپین‌های ما رو ۳ برابر کرد. آنالیز دقیق و ناشران حرفه‌ای، برگ برنده ما بود.',
         'rating': 5},
        {'name': 'اسنپ', 'logo': 'snap.png',
         'text': 'سرعت اجرا و شفافیت گزارش‌ها بی‌نظیره. تیم وینجاب واقعاً مفهوم مارکتینگ مدرن رو پیاده کردن.',
         'rating': 5},
        {'name': 'تپسی', 'logo': 'tapsi.png',
         'text': 'قیمت‌گذاری منصفانه و دسترسی به کانال‌های هدف، هزینه‌های تبلیغاتیمون رو نصف کرد.', 'rating': 4},
        {'name': 'همراه اول', 'logo': 'hamrah-aval.png',
         'text': 'بزرگترین چالش ما پیدا کردن اینفلوئنسر واقعی بود که وینجاب به بهترین شکل حلش کرد.', 'rating': 5},
        {'name': 'فیلیمو', 'logo': 'filimo.png',
         'text': 'کمپین معرفی سریال جدیدمون با وینجاب ۲.۵ میلیون بازدید ارگانیک گرفت.', 'rating': 4},
    ]

    context = {
        'total_campaigns': total_campaigns,
        'total_channels': total_channels,
        'total_influencers': total_influencers,
        'total_teams': total_teams,
        'total_clicks': total_clicks,
        'platforms': platforms,
        'top_channels': top_channels,
        'content_teams': content_teams,
        'recent_reviews': recent_reviews,
        'brand_testimonials': brand_testimonials,
        'blog_posts': blog_posts,
        'now': timezone.now(),
    }

    return render(request, 'core/pages/index.html', context)


def landing_page(request, platform):
    """
    فقط و فقط مسیریابی ساده به تمپلیت مناسب بر اساس اسم پلتفرم
    """

    # دیکشنری مسیر تمپلیت‌ها
    templates = {
        'telegram': 'core/landing/telegram_landing.html',
        'instagram': 'core/landing/instagram_landing.html',
        'bale': 'core/landing/bale_landing.html',
        'eitaa': 'core/landing/eitaa_landing.html',
        'rubika': 'core/landing/rubika_landing.html',
        'sorush': 'core/landing/soroush_landing.html',
    }

    # پیدا کردن تمپلیت
    template_name = templates.get(platform.lower())

    if not template_name:
        raise Http404("صفحه مورد نظر یافت نشد")

    return render(request, template_name)


def pending(request):
    return render(request, "core/pages/pending.html")
