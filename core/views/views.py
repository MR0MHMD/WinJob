from influencers.models import Channel, ChannelReview, InfluencerProfile, ChannelBooking
from content_team.models import ContentTeam, ContentPortfolio, ContentOrder
from campaigns.models import CampaignClick, Campaign
from django.views.generic import TemplateView
from django.db.models import Count, Q, Avg
from core.models import Platform
from django.shortcuts import render
from django.utils import timezone
from django.http import Http404
from blog.models import Post


def home(request):
    total_influencers = InfluencerProfile.objects.filter(is_active=True).count()
    total_campaigns = Campaign.objects.filter(status=Campaign.Status.COMPLETED).count()
    total_channels = Channel.objects.filter(is_active=True, status="approved").count()
    total_teams = ContentTeam.objects.filter(is_active=True).count()
    total_clicks = CampaignClick.objects.count()

    platforms = Platform.objects.filter(is_active=True).annotate(
        channels_count=Count('influencer_channels', filter=Q(influencer_channels__is_active=True))
    ).order_by('-channels_count')

    top_channels = Channel.objects.filter(
        is_active=True,
        influencer__is_active=True
    ).annotate(
        completed_bookings=Count(
            'campaign_bookings',
            filter=Q(campaign_bookings__status='completed')
        ),
        avg_channel_rating=Avg('reviews__rating')
    ).select_related('score').order_by(
        '-score__points',
        '-completed_bookings'
    )[:5]

    content_teams_raw = ContentTeam.objects.filter(is_active=True)
    content_teams = sorted(content_teams_raw, key=lambda x: x.avg_rating or 0, reverse=True)[:5]

    recent_reviews = ChannelReview.objects.select_related(
        'channel', 'advertiser__user'
    ).order_by('-created_at')[:10]

    blog_posts = Post.published.order_by('-created_at')[:4]

    brand_testimonials = [
        {'name': 'دیجیکالا', 'logo': 'digikala.webp',
         'text': 'همکاری با وینجاب نرخ تبدیل کمپین‌های ما رو ۳ برابر کرد. آنالیز دقیق و ناشران حرفه‌ای، برگ برنده ما بود.',
         'rating': 5},
        {'name': 'اسنپ', 'logo': 'snap.webp',
         'text': 'سرعت اجرا و شفافیت گزارش‌ها بی‌نظیره. تیم وینجاب واقعاً مفهوم مارکتینگ مدرن رو پیاده کردن.',
         'rating': 5},
        {'name': 'تپسی', 'logo': 'tapsi.webp',
         'text': 'قیمت‌گذاری منصفانه و دسترسی به کانال‌های هدف، هزینه‌های تبلیغاتی مون رو نصف کرد.', 'rating': 4},
        {'name': 'همراه اول', 'logo': 'hamrah-aval.webp',
         'text': 'بزرگترین چالش ما پیدا کردن اینفلوئنسر واقعی بود که وینجاب به بهترین شکل حلش کرد.', 'rating': 5},
        {'name': 'فیلیمو', 'logo': 'filimo.webp',
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


class AboutView(TemplateView):
    template_name = "core/pages/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ========== آمارهای واقعی ==========
        context['successful_campaigns'] = Campaign.objects.filter(
            status=Campaign.Status.COMPLETED
        ).count()

        context['active_approved_channels'] = Channel.objects.filter(
            status='approved',
            is_active=True
        ).count()

        context['active_content_teams'] = ContentTeam.objects.filter(
            is_active=True
        ).count()

        context['total_clicks'] = CampaignClick.objects.count()

        context["completed_bookings"] = ChannelBooking.objects.filter(
            status=ChannelBooking.Status.COMPLETED
        ).count()

        context["portfolio_count"] = ContentPortfolio.objects.filter(
            is_active=True
        ).count()

        context["completed_content_orders"] = ContentOrder.objects.filter(
            status=ContentOrder.Status.COMPLETED
        ).count()

        return context


def platform_landing_page(request, slug):
    try:
        platform = Platform.objects.get(slug=slug, is_active=True)
    except Platform.DoesNotExist:
        raise Http404("پلتفرم مورد نظر یافت نشد.")

    total_campaigns = Campaign.objects.filter(
        platform=platform,
        status=Campaign.Status.COMPLETED
    ).count()

    total_channels = Channel.objects.filter(
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

    top_channels = Channel.objects.filter(
        platform=platform,
        is_active=True,
        influencer__is_active=True
    ).annotate(
        completed_bookings=Count(
            'campaign_bookings',
            filter=Q(campaign_bookings__status='completed')
        ),
        avg_channel_rating=Avg('reviews__rating')
    ).select_related('score').order_by(
        '-score__points',
        '-completed_bookings'
    )[:5]

    content_teams = []

    brand_testimonials = [
        {'name': 'دیجیکالا', 'logo': 'digikala.webp',
         'text': 'همکاری با وینجاب نرخ تبدیل کمپین‌های ما رو ۳ برابر کرد. آنالیز دقیق و ناشران حرفه‌ای، برگ برنده ما بود.',
         'rating': 5},
        {'name': 'اسنپ', 'logo': 'snap.webp',
         'text': 'سرعت اجرا و شفافیت گزارش‌ها بی‌نظیره. تیم وینجاب واقعاً مفهوم مارکتینگ مدرن رو پیاده کردن.',
         'rating': 5},
        {'name': 'تپسی', 'logo': 'tapsi.webp',
         'text': 'قیمت‌گذاری منصفانه و دسترسی به کانال‌های هدف، هزینه‌های تبلیغاتیمون رو نصف کرد.', 'rating': 4},
        {'name': 'همراه اول', 'logo': 'hamrah-aval.webp',
         'text': 'بزرگترین چالش ما پیدا کردن اینفلوئنسر واقعی بود که وینجاب به بهترین شکل حلش کرد.', 'rating': 5},
        {'name': 'فیلیمو', 'logo': 'filimo.webp',
         'text': 'کمپین معرفی سریال جدیدمون با وینجاب ۲.۵ میلیون بازدید ارگانیک گرفت.', 'rating': 4},
    ]

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
            'hero_image': 'landing/rubika/rub_hero.webp',
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


class TermsView(TemplateView):
    """صفحه قوانین و مقررات"""
    template_name = "core/pages/terms.html"


from django.contrib import messages
from django.views.generic import TemplateView
from django.shortcuts import redirect
from tickets.models import TicketCategory, ContactRequest
from core.models import FAQ
from accounts.models import CustomUser   # فرض بر این که مدل یوزر اینجاست


class ContactView(TemplateView):
    """صفحه تماس با ما"""
    template_name = "core/pages/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = TicketCategory.objects.filter(is_active=True).order_by('order', 'name')
        # ۵ سوال متداول رندوم
        context['faqs'] = FAQ.objects.filter(is_active=True).order_by('?')[:5]
        return context

    def post(self, request, *args, **kwargs):
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip() or None
        category_id = request.POST.get('subject')
        message = request.POST.get('message', '').strip()

        # اعتبارسنجی ساده
        errors = []
        if not name:
            errors.append('نام و نام خانوادگی الزامی است.')
        if not phone:
            errors.append('شماره موبایل الزامی است.')
        if not category_id:
            errors.append('موضوع را انتخاب کنید.')
        if not message:
            errors.append('پیام الزامی است.')

        try:
            category = TicketCategory.objects.get(pk=category_id, is_active=True)
        except (TicketCategory.DoesNotExist, ValueError, TypeError):
            errors.append('موضوع انتخاب‌شده معتبر نیست.')
            category = None

        if errors:
            for err in errors:
                messages.error(request, err)
            return self.get(request, *args, **kwargs)

        # پیدا کردن یوزر بر اساس شماره موبایل (اگر وجود داشته باشد)
        user = None
        try:
            clean_phone = ''.join(c for c in phone if c.isdigit())
            user = CustomUser.objects.filter(phone_number__endswith=clean_phone[-10:]).first()
            # user = CustomUser.objects.filter(phone_number=phone).first()
        except Exception:
            pass

        ContactRequest.objects.create(
            name=name,
            phone=phone,
            email=email,
            category=category,
            message=message,
            user=user,
            status=ContactRequest.Status.PENDING,
        )

        messages.success(request, 'پیام شما ثبت شد. به زودی با شما تماس می‌گیریم.')
        return redirect('core:contact')

class HelpGuideView(TemplateView):
    """صفحه راهنمای پویا بر اساس نقش کاربر"""
    template_name = "core/pages/help.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if not user.is_authenticated:
            role = 'guest'
            role_label = 'مهمان'
        elif getattr(user, 'is_advertiser', None):
            role = 'advertiser'
            role_label = 'تبلیغ‌دهنده'
        elif getattr(user, 'is_influencer', None):
            role = 'influencer'
            role_label = 'اینفلوئنسر'
        elif getattr(user, 'is_team_member', None):
            role = 'team_member'
            role_label = 'عضو تیم محتوا'
        else:
            role = 'user'
            role_label = 'کاربر'

        # پیش‌نمایش نقش با ?role=advertiser و ...
        preview = self.request.GET.get('role')
        if preview in ('guest', 'advertiser', 'influencer', 'team_member', 'user'):
            role = preview
            labels = {
                'guest': 'مهمان',
                'advertiser': 'تبلیغ‌دهنده',
                'influencer': 'اینفلوئنسر',
                'team_member': 'عضو تیم محتوا',
                'user': 'کاربر',
            }
            role_label = labels[role]

        context['current_role'] = role
        context['role_label'] = role_label
        context['is_authenticated'] = user.is_authenticated
        return context


from tickets.models import TicketCategory, TicketTitle
from core.models import FAQ
from django.db.models import Count, Q


class FAQPageView(TemplateView):
    template_name = "core/pages/faq.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        categories = (
            TicketCategory.objects
            .filter(is_active=True)
            .annotate(
                titles_count=Count('titles', filter=Q(titles__is_active=True)),
                faq_count=Count(
                    'titles__faqs',
                    filter=Q(titles__is_active=True, titles__faqs__is_active=True)
                )
            )
            .order_by('order', 'name')
        )
        context['categories'] = categories

        cat_slug = self.request.GET.get('category', '').strip()
        title_slug = self.request.GET.get('title', '').strip()

        selected_category = None
        selected_title = None
        titles = []
        faqs = []

        if cat_slug:
            selected_category = categories.filter(slug=cat_slug).first()
            if selected_category:
                titles = (
                    TicketTitle.objects
                    .filter(category=selected_category, is_active=True)
                    .annotate(faq_count=Count('faqs', filter=Q(faqs__is_active=True)))
                    .order_by('order', 'name')
                )
                if title_slug:
                    selected_title = titles.filter(slug=title_slug).first()
                    if selected_title:
                        faqs = (
                            FAQ.objects
                            .filter(title=selected_title, is_active=True)
                            .order_by('order', 'created_at')
                        )

        context['selected_category'] = selected_category
        context['selected_title'] = selected_title
        context['titles'] = titles
        context['faqs'] = faqs
        context['cat_slug'] = cat_slug
        context['title_slug'] = title_slug
        context['total_faqs'] = FAQ.objects.filter(is_active=True).count()
        context['total_categories'] = categories.count()
        return context


def content_production_landing(request):
    """لندینگ اختصاصی سرویس تولید محتوا"""
    from content_team.models import ContentTeam, ContentPortfolio, ContentServicePlan, ContentOrder
    from core.models import ContentServiceType
    from influencers.models import Channel

    # ========== آمار ==========
    total_teams = ContentTeam.objects.filter(is_active=True).count()
    total_portfolios = ContentPortfolio.objects.filter(is_active=True).count()
    completed_orders = ContentOrder.objects.filter(
        status=ContentOrder.Status.COMPLETED
    ).count()

    # ========== تیم‌های برتر ==========
    content_teams_raw = ContentTeam.objects.filter(is_active=True)
    content_teams = sorted(content_teams_raw, key=lambda x: x.avg_rating or 0, reverse=True)[:5]

    # ========== نمونه کارها ==========
    portfolios = ContentPortfolio.objects.filter(
        is_active=True,
        media__isnull=False
    ).select_related('team', 'service_type').order_by('-created_at')[:9]

    # ========== انواع خدمات ==========
    service_types = ContentServiceType.objects.filter(
        is_active=True
    ).order_by('display_order')[:6]

    # ========== پلن‌های نمونه ==========
    sample_plans = ContentServicePlan.objects.filter(
        is_active=True
    ).select_related('team', 'service_type').order_by('price')[:3]

    # ========== نظرات (از ریویوهای تیم) ==========
    from content_team.models import TeamReview
    reviews = TeamReview.objects.select_related(
        'team', 'advertiser__user'
    ).filter(rating__gte=4).order_by('-created_at')[:6]

    # ========== سوالات متداول ==========
    faqs = [
        {'q': 'چطور می‌تونم سفارش تولید محتوا بدم؟',
         'a': 'کافیه روی دکمه «ثبت سفارش» کلیک کنی، نوع محتوا و تیم رو انتخاب کنی و اطلاعات بریف رو پر کنی. کل فرآیند کمتر از ۵ دقیقه طول می‌کشه.'},
        {'q': 'چقدر طول می‌کشه تا محتوا تحویل داده بشه؟',
         'a': 'بستگی به نوع پلن و تیم داره، ولی معمولاً بین ۳ تا ۷ روز کاری. توی صفحه هر پلن، زمان تحویل مشخص شده.'},
        {'q': 'اگه کمپین تبلیغاتی نداشته باشم هم می‌تونم سفارش بدم؟',
         'a': 'قطعاً! تولید محتوا یه سرویس مستقله. می‌تونی فقط محتوا سفارش بدی و هرجایی که خواستی ازش استفاده کنی.'},
        {'q': 'اگه از محتوا راضی نبودم چی؟',
         'a': 'تا ۲ بار می‌تونی درخواست ویرایش بدی و تیم موظفه اصلاحات رو انجام بده. اگه بعد از ویرایش هم راضی نبودی، تیم پشتیبانی بررسی می‌کنه.'},
        {'q': 'امکان انتخاب چند گزینه برای تحویل هست؟',
         'a': 'بله! بعضی پلن‌ها به صورت MULTI_CHOICE هستن، یعنی تیم چند نسخه می‌سازه و تو یکیش رو انتخاب می‌کنی.'},
        {'q': 'هزینه‌ها چطوریه؟',
         'a': 'هر تیم پلن‌های خودش رو با قیمت مشخص ارائه می‌ده. توی صفحه هر تیم می‌تونی همه پلن‌ها و قیمت‌هاشون رو ببینی.'},
    ]

    context = {
        'total_teams': total_teams,
        'total_portfolios': total_portfolios,
        'completed_orders': completed_orders,
        'content_teams': content_teams,
        'portfolios': portfolios,
        'service_types': service_types,
        'sample_plans': sample_plans,
        'reviews': reviews,
        'faqs': faqs,
    }
    return render(request, 'core/pages/content_production_landing.html', context)