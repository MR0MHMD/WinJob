from influencers.models import InfluencerChannel, InfluencerReview, InfluencerProfile
from campaigns.models import CampaignClick, Campaign
from django.db.models import Count, Q, Avg
from content_team.models import ContentTeam
from plat_form.models import Platform
from django.shortcuts import render
from django.utils import timezone
from django.http import Http404
from blog.models import Post

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


def platform_landing_page(request, slug):
    # بررسی وجود پلتفرم (مثلاً اینستاگرام)
    try:
        platform = Platform.objects.get(slug=slug, is_active=True)
    except Platform.DoesNotExist:
        raise Http404("پلتفرم مورد نظر یافت نشد.")

    # آمار ویژه همین پلتفرم
    total_campaigns = Campaign.objects.filter(
        platform=platform,
        status=Campaign.Status.COMPLETED
    ).count()

    total_channels = InfluencerChannel.objects.filter(
        platform=platform,
        is_active=True
    ).count()

    total_influencers = InfluencerProfile.objects.filter(
        channels__platform=platform,
        is_active=True
    ).distinct().count()

    total_clicks = CampaignClick.objects.filter(
        tracking_link__campaign_influencer__campaign__platform=platform
    ).count()

    # ۵ پیج برتر اینستاگرام (مرتب‌سازی: امتیاز گیمیفیکیشن، سپس تعداد همکاری موفق)
    top_channels = InfluencerChannel.objects.filter(
        platform=platform,
        is_active=True,
        influencer__is_active=True
    ).annotate(
        # تعداد همکاری‌های موفق (کمپین تمام شده)
        completed_bookings=Count(
            'campaign_bookings',
            filter=Q(campaign_bookings__status='completed')
        ),
        # میانگین امتیاز نظرات
        avg_channel_rating=Avg('reviews__rating')
    ).select_related('score').order_by(
        '-score__points',  # اولویت اول: امتیاز گیمیفیکیشن
        '-completed_bookings'  # اولویت دوم: تعداد همکاری موفق
    )[:5]

    # تیم‌های محتوا (در این لندینگ پیج حذف می‌شه اما برای عدم خطا خالی می‌دیم)
    content_teams = []

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

    # تنظیمات ظاهری بر اساس پلتفرم
    platform_theme = {
        'instagram': {
            'gradient': 'linear-gradient(135deg, #feda77, #f58529, #dd2a7b, #8134af, #515bd4)',
            'primary_color': '#dd2a7b',
            'accent_color': '#f58529',
            'hero_image': 'landing/instagram/insta-hero.webp',
            'hero_title': 'اینستاگرام',
            'stats_label': 'پیج اینستاگرامی',
            "channel_label": "پیج های اینستاگرام"
        },
        'eitaa': {
            'gradient': 'linear-gradient(135deg, #ff8c00, #ff4d00, #e63600)',
            'primary_color': '#ff4d00',
            'accent_color': '#ff8c00',
            'hero_image': 'landing/eitaa/eitaa-hero.webp',
            'hero_title': 'ایتا',
            'stats_label': 'کانال ایتا',
            "channel_label": "کانال های ایتا"
        },
        'telegram': {
            'gradient': 'linear-gradient(135deg, #29a9e1, #1e88e5, #0d47a1)',
            'primary_color': '#1e88e5',
            'accent_color': '#29a9e1',
            'hero_image': 'landing/telegram/tel-hero.webp',
            'hero_title': 'تلگرام',
            'stats_label': 'کانال تلگرامی',
            "channel_label": "کانال های تلگرام"
        },
        'rubika': {
            'gradient': 'linear-gradient(135deg, #7a4587, #5bd5bd, #b8cd06, #f4a926, #e54d52)',
            'primary_color': '#7a4587',
            'accent_color': '#5bd5bd',
            'hero_image': 'landing/rubika/rub-hero.webp',
            'hero_title': 'روبیکا',
            'stats_label': 'کانال روبیکا',
            "channel_label": "کانال های روبیکا"
        },
        'bale': {
            'gradient': 'linear-gradient(135deg, #4df1b6, #2d2b73, #1a1a4d)',
            'primary_color': '#2d2b73',
            'accent_color': '#4df1b6',
            'hero_image': 'landing/bale/bale-hero.webp',
            'hero_title': 'بله',
            'stats_label': 'کانال بله',
            "channel_label": "کانال های بله"
        },
        'sorush': {
            'gradient': 'linear-gradient(135deg, #3991ac, #155c72, #0a3a4a)',
            'primary_color': '#3991ac',
            'accent_color': '#155c72',
            'hero_image': 'landing/sorush/sor-hero.webp',
            'hero_title': 'سروش پلاس',
            'stats_label': 'کانال سروش',
            "channel_label": "کانال های سروش"
        },
    }

    theme = platform_theme.get(platform.slug, platform_theme['instagram'])


    context = {
        'platform': platform,
        'total_campaigns': total_campaigns,
        'total_channels': total_channels,
        'total_influencers': total_influencers,
        'total_clicks': total_clicks,
        'top_channels': top_channels,
        'theme': theme,
        'content_teams': content_teams,
        'brand_testimonials': brand_testimonials,
        'now': timezone.now(),
    }
    return render(request, 'core/pages/platform_landing.html', context)

def pending(request):
    return render(request, "core/pages/pending.html")
