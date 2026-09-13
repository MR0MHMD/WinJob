# support/views/list.py

"""
ListView های پنل Support

هر View بر اساس نقش، دسترسی و فیلتر استانی مناسب داره.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg, Prefetch, Sum
from django.views.generic import ListView
from django.utils import timezone
from datetime import timedelta

from ..mixins import (
    BaseSupportMixin,
    ContentManagerRequiredMixin,
    PublishManagerRequiredMixin,
    RegionalFilterMixin,
    RegionalFilterComplexMixin,
)
from influencers.models import ChannelServiceRate, Channel, InfluencerProfile, ChannelBooking
from campaigns.models import Campaign, CampaignReport
from advertisers.models import AdvertiserProfile
from notifications.models import Notification
from core.models import Platform, Province, Category
from tickets.models import TicketMessage, Ticket
from accounts.models import CustomUser
from content_team.models import (
    ContentOrder,
    ContentTeam,
    ContentTeamMember,
    ContentOrderDescription,
    ContentOrderFile,
    ContentDelivery,
)

User = get_user_model()


# ============================================================
#                        Ticket List
# ============================================================
class TicketListView(BaseSupportMixin, RegionalFilterMixin, ListView):
    """
    لیست تیکت‌ها

    دسترسی: همه نقش‌ها
    فیلتر Regional: کاربر استان خودش
    """
    model = Ticket
    template_name = 'support/tickets/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 20
    ordering = ['-updated_at']

    province_field_path = 'user__province'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'user', 'category', 'title'
        ).prefetch_related(
            Prefetch(
                'messages',
                queryset=TicketMessage.objects.order_by('-created_at')[:1],
                to_attr='last_msg'
            )
        )


# ============================================================
#                        Channel List
# ============================================================
class ChannelListView(PublishManagerRequiredMixin, RegionalFilterMixin, ListView):
    """
    لیست کانال‌های اینفلوئنسر

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: خود Channel فیلد province داره
    """
    model = Channel
    template_name = 'support/channels/channel_list.html'
    context_object_name = 'channels'
    paginate_by = 50

    province_field_path = 'province'

    def get_queryset(self):
        queryset = Channel.objects.select_related(
            'influencer',
            'influencer__user',
            'platform',
            'province',
            'category',
            'score'
        ).prefetch_related(
            Prefetch('service_rates', queryset=ChannelServiceRate.objects.filter(is_active=True)),
            Prefetch('campaign_bookings', queryset=ChannelBooking.objects.filter(status='completed')),
        ).annotate(
            avg_rating_=Avg('reviews__rating'),
            reviews_count_=Count('reviews'),
            completed_bookings_count_=Count('campaign_bookings', filter=Q(campaign_bookings__status='completed')),
            total_revenue_=Sum('campaign_bookings__price', filter=Q(campaign_bookings__status='completed'))
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            queryset = queryset.filter(province=user.province)

        # ========== جستجو ==========
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(channel_name__icontains=search) |
                Q(channel_id__icontains=search) |
                Q(influencer__user__nickname__icontains=search) |
                Q(influencer__user__phone_number__icontains=search)
            )

        # ========== فیلترها ==========
        influencer_id = self.request.GET.get('influencer')
        if influencer_id and influencer_id.isdigit():
            queryset = queryset.filter(influencer_id=int(influencer_id))

        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        platform = self.request.GET.get('platform')
        if platform:
            queryset = queryset.filter(platform_id=platform)

        province = self.request.GET.get('province')
        if province:
            queryset = queryset.filter(province_id=province)

        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)

        # ========== مرتب‌سازی ==========
        sort_by = self.request.GET.get('sort')
        if sort_by == 'name':
            queryset = queryset.order_by('channel_name')
        elif sort_by == 'followers_asc':
            queryset = queryset.order_by('followers_count')
        elif sort_by == 'followers_desc':
            queryset = queryset.order_by('-followers_count')
        elif sort_by == 'rating':
            queryset = queryset.order_by('-avg_rating_')
        elif sort_by == 'revenue':
            queryset = queryset.order_by('-total_revenue_')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_regional = user.is_regional_manager and user.province_id

        # آمار پایه (بر اساس دسترسی کاربر)
        base_qs = Channel.objects.all()
        if is_regional:
            base_qs = base_qs.filter(province=user.province)

        context['total_count'] = base_qs.count()
        context['pending_count'] = base_qs.filter(status='pending').count()
        context['approved_count'] = base_qs.filter(status='approved').count()
        context['rejected_count'] = base_qs.filter(status='rejected').count()
        context['active_count'] = base_qs.filter(is_active=True).count()

        context['current_status'] = self.request.GET.get('status', '')
        context['current_platform'] = self.request.GET.get('platform', '')
        context['current_province'] = self.request.GET.get('province', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['current_search'] = self.request.GET.get('q', '')
        context['current_sort'] = self.request.GET.get('sort', '')

        context['platforms'] = Platform.objects.filter(is_active=True)
        # اگه Regional هست، فقط استان خودش رو توی فیلتر نشون بده
        if is_regional:
            context['provinces'] = Province.objects.filter(id=user.province_id)
        else:
            context['provinces'] = Province.objects.all().order_by('name')
        context['categories'] = Category.objects.filter(is_active=True)
        context['status_choices'] = Channel.STATUS_CHOICES

        influencer_id = self.request.GET.get('influencer')
        if influencer_id and influencer_id.isdigit():
            try:
                influencer = InfluencerProfile.objects.get(id=int(influencer_id))
                context['filtered_influencer_name'] = influencer.user.nickname
            except InfluencerProfile.DoesNotExist:
                pass

        return context


# ============================================================
#                       Campaign List
# ============================================================
class CampaignListView(PublishManagerRequiredMixin, RegionalFilterMixin, ListView):
    """
    لیست کمپین‌ها

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: از طریق تبلیغ‌دهنده
    """
    model = Campaign
    template_name = 'support/campaigns/campaign_list.html'
    context_object_name = 'campaigns'
    paginate_by = 20

    province_field_path = 'advertiser__user__province'

    def get_queryset(self):
        queryset = Campaign.objects.select_related(
            'advertiser', 'platform', 'content_type', 'ad_type', 'advertiser__user'
        ).prefetch_related('influencer_bookings')

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            queryset = queryset.filter(advertiser__user__province=user.province)

        # ========== فیلترها ==========
        advertiser_id = self.request.GET.get('advertiser')
        if advertiser_id and advertiser_id.isdigit():
            queryset = queryset.filter(advertiser_id=int(advertiser_id))

        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(advertiser__business_name__icontains=search_query) |
                Q(advertiser__user__phone_number__icontains=search_query) |
                Q(advertiser__user__nickname__icontains=search_query)
            )

        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        date_filter = self.request.GET.get('date_filter')
        today = timezone.now().date()

        if date_filter == 'today':
            queryset = queryset.filter(created_at__date=today)
        elif date_filter == 'week':
            week_ago = today - timedelta(days=7)
            queryset = queryset.filter(created_at__date__gte=week_ago)
        elif date_filter == 'month':
            month_ago = today - timedelta(days=30)
            queryset = queryset.filter(created_at__date__gte=month_ago)
        elif date_filter == 'year':
            year_ago = today - timedelta(days=365)
            queryset = queryset.filter(created_at__date__gte=year_ago)

        # ========== مرتب‌سازی بر اساس اولویت وضعیت ==========
        status_order = {
            'pending': 0,
            'approved': 1,
            'running': 2,
            'completed': 3,
            'draft': 4,
            'cancelled': 5,
        }

        all_campaigns = list(queryset)
        all_campaigns.sort(key=lambda c: status_order.get(c.status, 99))

        return all_campaigns

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_regional = user.is_regional_manager and user.province_id

        # آمار پایه (بر اساس دسترسی کاربر)
        base_qs = Campaign.objects.all()
        if is_regional:
            base_qs = base_qs.filter(advertiser__user__province=user.province)

        context['total_count'] = base_qs.count()
        context['pending_count'] = base_qs.filter(status='pending').count()
        context['approved_count'] = base_qs.filter(status='approved').count()
        context['running_count'] = base_qs.filter(status='running').count()
        context['completed_count'] = base_qs.filter(status='completed').count()
        context['draft_count'] = base_qs.filter(status='draft').count()
        context['cancelled_count'] = base_qs.filter(status='cancelled').count()

        context['current_status'] = self.request.GET.get('status', '')
        context['current_date_filter'] = self.request.GET.get('date_filter', '')
        context['current_search'] = self.request.GET.get('q', '')
        context['current_advertiser'] = self.request.GET.get('advertiser', '')

        context['status_choices'] = Campaign.Status.choices

        if context['current_advertiser']:
            try:
                advertiser = AdvertiserProfile.objects.get(id=context['current_advertiser'])
                context['filtered_advertiser_name'] = advertiser.business_name
            except:
                pass

        return context


# ============================================================
#                        Report List
# ============================================================
class ReportListView(PublishManagerRequiredMixin, RegionalFilterMixin, ListView):
    """
    لیست گزارشات در انتظار بررسی

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: از طریق کانال
    """
    model = CampaignReport
    template_name = 'support/reports/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    ordering = ['-created_at']

    province_field_path = 'campaign_influencer__channel__province'

    def get_queryset(self):
        qs = super().get_queryset().filter(
            status='pending'
        ).select_related(
            'campaign_influencer',
            'campaign_influencer__campaign',
            'campaign_influencer__campaign__advertiser',
            'campaign_influencer__channel',
            'campaign_influencer__channel__influencer',
            'campaign_influencer__channel__platform'
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(
                campaign_influencer__channel__province=user.province
            )

        return qs


# ============================================================
#                         User List
# ============================================================
class UserListView(BaseSupportMixin, RegionalFilterMixin, ListView):
    """
    لیست تمام کاربران

    دسترسی: همه نقش‌ها
    فیلتر Regional: کاربر استان خودش
    """
    model = User
    template_name = 'support/users/user_list.html'
    context_object_name = 'users'
    paginate_by = 50

    province_field_path = 'province'

    def get_queryset(self):
        queryset = User.objects.select_related('province', 'wallet').annotate(
            advertiser_count=Count('advertiser_profile', distinct=True),
            influencer_count=Count('influencer_profile', distinct=True),
            team_member_count=Count('team_member', distinct=True),
            ticket_count=Count('tickets', distinct=True),
            campaign_count=Count('advertiser_profile__campaigns', distinct=True),
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            queryset = queryset.filter(province=user.province)

        # ========== فیلتر نقش ==========
        role = self.request.GET.get('role')
        if role == 'advertiser':
            queryset = queryset.filter(advertiser_profile__isnull=False)
        elif role == 'influencer':
            queryset = queryset.filter(influencer_profile__isnull=False)
        elif role == 'team_member':
            queryset = queryset.filter(team_member__isnull=False)
        elif role == 'none':
            queryset = queryset.filter(
                advertiser_profile__isnull=True,
                influencer_profile__isnull=True,
                team_member__isnull=True
            )

        # ========== جستجو ==========
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(phone_number__icontains=search) |
                Q(nickname__icontains=search) |
                Q(advertiser_profile__business_name__icontains=search) |
                Q(influencer_profile__user__nickname__icontains=search)
            ).distinct()

        return queryset.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_regional = user.is_regional_manager and user.province_id

        # آمار پایه
        user_qs = User.objects.all()
        adv_qs = AdvertiserProfile.objects.all()
        inf_qs = InfluencerProfile.objects.all()

        if is_regional:
            user_qs = user_qs.filter(province=user.province)
            adv_qs = adv_qs.filter(user__province=user.province)
            inf_qs = inf_qs.filter(user__province=user.province)

        context['total_users'] = user_qs.count()
        context['advertisers_count'] = adv_qs.count()
        context['influencers_count'] = inf_qs.count()
        context['team_members_count'] = ContentTeamMember.objects.count()
        context['current_role'] = self.request.GET.get('role', '')
        context['current_search'] = self.request.GET.get('q', '')
        return context


# ============================================================
#                    Campaign Booking List
# ============================================================
class CampaignBookingListView(PublishManagerRequiredMixin, RegionalFilterMixin, ListView):
    """
    لیست رزروهای اینفلوئنسر

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: از طریق کانال
    """
    model = ChannelBooking
    template_name = 'support/campaigns/booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 50

    province_field_path = 'channel__province'

    def get_queryset(self):
        queryset = ChannelBooking.objects.select_related(
            'campaign',
            'campaign__advertiser',
            'channel',
            'channel__platform',
            'channel__influencer',
            'channel__province',
            'service_rate',
            'service_rate__ad_type',
        ).prefetch_related(
            Prefetch('report', queryset=CampaignReport.objects.all())
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            queryset = queryset.filter(channel__province=user.province)

        # ========== فیلترها ==========
        influencer_id = self.request.GET.get('influencer')
        if influencer_id and influencer_id.isdigit():
            queryset = queryset.filter(channel__influencer_id=int(influencer_id))

        campaign_id = self.request.GET.get('campaign')
        if campaign_id and campaign_id.isdigit():
            queryset = queryset.filter(campaign_id=int(campaign_id))

        channel_id = self.request.GET.get('channel')
        if channel_id and channel_id.isdigit():
            queryset = queryset.filter(channel_id=int(channel_id))

        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        payment_status = self.request.GET.get('payment_status')
        if payment_status == 'paid':
            queryset = queryset.filter(is_paid=True)
        elif payment_status == 'unpaid':
            queryset = queryset.filter(is_paid=False)

        platform = self.request.GET.get('platform')
        if platform:
            queryset = queryset.filter(channel__platform_id=platform)

        province = self.request.GET.get('province')
        if province:
            queryset = queryset.filter(channel__province_id=province)

        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(channel__channel_name__icontains=search) |
                Q(channel__channel_id__icontains=search) |
                Q(channel__influencer__user__nickname__icontains=search) |
                Q(campaign__name__icontains=search)
            )

        # ========== مرتب‌سازی ==========
        sort_by = self.request.GET.get('sort')
        if sort_by == 'price_asc':
            queryset = queryset.order_by('price')
        elif sort_by == 'price_desc':
            queryset = queryset.order_by('-price')
        elif sort_by == 'followers_asc':
            queryset = queryset.order_by('channel__followers_count')
        elif sort_by == 'followers_desc':
            queryset = queryset.order_by('-channel__followers_count')
        elif sort_by == 'oldest':
            queryset = queryset.order_by('created_at')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_regional = user.is_regional_manager and user.province_id

        context['current_influencer'] = self.request.GET.get('influencer', '')
        context['current_campaign'] = self.request.GET.get('campaign', '')
        context['current_channel'] = self.request.GET.get('channel', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_payment_status'] = self.request.GET.get('payment_status', '')
        context['current_platform'] = self.request.GET.get('platform', '')
        context['current_province'] = self.request.GET.get('province', '')
        context['current_search'] = self.request.GET.get('q', '')
        context['current_sort'] = self.request.GET.get('sort', '')

        influencer_id = self.request.GET.get('influencer')
        if influencer_id and influencer_id.isdigit():
            try:
                influencer = InfluencerProfile.objects.get(id=int(influencer_id))
                context['filtered_influencer_name'] = influencer.user.nickname
                context['filtered_influencer_id'] = influencer_id
            except InfluencerProfile.DoesNotExist:
                pass

        campaign_id = self.request.GET.get('campaign')
        if campaign_id and campaign_id.isdigit():
            try:
                campaign = Campaign.objects.get(id=int(campaign_id))
                context['filtered_campaign_name'] = campaign.name
                context['filtered_campaign_id'] = campaign_id
            except Campaign.DoesNotExist:
                pass

        channel_id = self.request.GET.get('channel')
        if channel_id and channel_id.isdigit():
            try:
                channel = Channel.objects.get(id=int(channel_id))
                context['filtered_channel_name'] = channel.channel_name
                context['filtered_channel_id'] = channel_id
            except Channel.DoesNotExist:
                pass

        # آمار پایه با فیلتر Regional
        base_qs = ChannelBooking.objects.all()
        if is_regional:
            base_qs = base_qs.filter(channel__province=user.province)

        context['total_count'] = base_qs.count()
        context['pending_count'] = base_qs.filter(status='pending').count()
        context['accepted_count'] = base_qs.filter(status='accepted').count()
        context['rejected_count'] = base_qs.filter(status='rejected').count()
        context['completed_count'] = base_qs.filter(status='completed').count()
        context['paid_count'] = base_qs.filter(is_paid=True).count()
        context['unpaid_count'] = base_qs.filter(is_paid=False).count()
        context['platforms'] = Platform.objects.filter(is_active=True)

        if is_regional:
            context['provinces'] = Province.objects.filter(id=user.province_id)
        else:
            context['provinces'] = Province.objects.all().order_by('name')

        context['status_choices'] = ChannelBooking.Status.choices

        return context


# ============================================================
#                        Team List
# ============================================================
class TeamListView(ContentManagerRequiredMixin, RegionalFilterMixin, ListView):
    """
    لیست تیم‌های تولید محتوا

    دسترسی: CEO + Dev + Content Manager
    فیلتر Regional: خود ContentTeam فیلد province داره
    """
    model = ContentTeam
    template_name = 'support/content_team/team_list.html'
    context_object_name = 'teams'
    paginate_by = 20

    province_field_path = 'province'

    def get_queryset(self):
        queryset = ContentTeam.objects.annotate(
            members_count_=Count('members', filter=Q(members__is_active=True)),
            orders_count_=Count('orders'),
            completed_orders_count_=Count('orders', filter=Q(orders__status='completed')),
            avg_rating_=Avg('reviews__rating'),
            total_revenue=Sum('orders__price', filter=Q(orders__status='completed'))
        ).select_related('score', 'province')

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            queryset = queryset.filter(province=user.province)

        # ========== جستجو ==========
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(members__user__phone_number__icontains=search) |
                Q(members__user__nickname__icontains=search)
            ).distinct()

        # ========== فیلتر وضعیت ==========
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)

        # ========== مرتب‌سازی ==========
        sort_by = self.request.GET.get('sort')
        if sort_by == 'name':
            queryset = queryset.order_by('name')
        elif sort_by == 'members':
            queryset = queryset.order_by('-members_count_')
        elif sort_by == 'orders':
            queryset = queryset.order_by('-orders_count_')
        elif sort_by == 'rating':
            queryset = queryset.order_by('-avg_rating_')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_regional = user.is_regional_manager and user.province_id

        # آمار پایه با فیلتر Regional
        base_qs = ContentTeam.objects.all()
        if is_regional:
            base_qs = base_qs.filter(province=user.province)

        context['total_count'] = base_qs.count()
        context['active_count'] = base_qs.filter(is_active=True).count()
        context['inactive_count'] = base_qs.filter(is_active=False).count()

        context['current_search'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_sort'] = self.request.GET.get('sort', '')

        return context


# ============================================================
#                     Content Order List
# ============================================================
class ContentOrderListView(ContentManagerRequiredMixin, RegionalFilterComplexMixin, ListView):
    """
    لیست سفارش‌های تولید محتوا

    دسترسی: CEO + Dev + Content Manager
    فیلتر Regional: پیچیده (هم از کمپین، هم از standalone)
    """
    model = ContentOrder
    template_name = 'support/content_team/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    @staticmethod
    def province_q_object(province):
        """
        فیلتر پیچیده برای Regional Manager
        """
        return (
                Q(campaign__advertiser__user__province=province) |
                Q(standalone_user__province=province)
        )

    def get_queryset(self):
        queryset = ContentOrder.objects.select_related(
            'campaign',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'campaign__platform',
            'team',
            'plan',
            'plan__service_type',
        ).prefetch_related(
            Prefetch('brief', queryset=ContentOrderDescription.objects.all()),
            Prefetch('files', queryset=ContentOrderFile.objects.all()),
            Prefetch('deliveries', queryset=ContentDelivery.objects.all()),
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            queryset = queryset.filter(
                Q(campaign__advertiser__user__province=user.province) |
                Q(standalone_user__province=user.province)
            )

        # ========== فیلترها ==========
        team_id = self.request.GET.get('team')
        if team_id and team_id.isdigit():
            queryset = queryset.filter(team_id=int(team_id))

        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(campaign__name__icontains=search) |
                Q(campaign__advertiser__business_name__icontains=search) |
                Q(campaign__advertiser__user__phone_number__icontains=search) |
                Q(campaign__advertiser__user__nickname__icontains=search) |
                Q(team__name__icontains=search) |
                Q(plan__name__icontains=search) |
                Q(plan__service_type__name__icontains=search)
            )

        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        date_filter = self.request.GET.get('date_filter')
        today = timezone.now().date()

        if date_filter == 'today':
            queryset = queryset.filter(created_at__date=today)
        elif date_filter == 'week':
            week_ago = today - timedelta(days=7)
            queryset = queryset.filter(created_at__date__gte=week_ago)
        elif date_filter == 'month':
            month_ago = today - timedelta(days=30)
            queryset = queryset.filter(created_at__date__gte=month_ago)

        # ========== مرتب‌سازی ==========
        sort_by = self.request.GET.get('sort')
        if sort_by == 'price_asc':
            queryset = queryset.order_by('price')
        elif sort_by == 'price_desc':
            queryset = queryset.order_by('-price')
        elif sort_by == 'oldest':
            queryset = queryset.order_by('created_at')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_regional = user.is_regional_manager and user.province_id

        team_id = self.request.GET.get('team')

        # آمار پایه با فیلتر Regional
        base_qs = ContentOrder.objects.all()
        if is_regional:
            base_qs = base_qs.filter(
                Q(campaign__advertiser__user__province=user.province) |
                Q(standalone_user__province=user.province)
            )

        if team_id and team_id.isdigit():
            base_qs = base_qs.filter(team_id=int(team_id))

        context['total_count'] = base_qs.count()
        context['pending_count'] = base_qs.filter(status='pending').count()
        context['in_progress_count'] = base_qs.filter(status='in_progress').count()
        context['completed_count'] = base_qs.filter(status='completed').count()
        context['cancelled_count'] = base_qs.filter(status='cancelled').count()
        context['review_pending_count'] = base_qs.filter(status='review_pending').count()
        context['done_count'] = base_qs.filter(status='done').count()

        context['current_status'] = self.request.GET.get('status', '')
        context['current_team'] = self.request.GET.get('team', '')
        context['current_search'] = self.request.GET.get('q', '')
        context['current_date_filter'] = self.request.GET.get('date_filter', '')
        context['current_sort'] = self.request.GET.get('sort', '')

        # تیم‌ها (با فیلتر Regional اگه لازم باشه)
        teams_qs = ContentTeam.objects.filter(is_active=True)
        if is_regional:
            teams_qs = teams_qs.filter(province=user.province)
        context['teams'] = teams_qs

        context['status_choices'] = ContentOrder.Status.choices

        if team_id and team_id.isdigit():
            try:
                team = ContentTeam.objects.get(id=int(team_id))
                context['filtered_team_name'] = team.name
            except ContentTeam.DoesNotExist:
                pass

        return context


# ============================================================
#                    Notification List
# ============================================================
class NotificationListView(BaseSupportMixin, RegionalFilterMixin, ListView):
    """
    لیست نوتیفیکیشن‌ها

    دسترسی: همه نقش‌ها
    فیلتر Regional: نوتیفیکیشن کاربر استان خودش
    """
    model = Notification
    template_name = 'support/notification/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 100

    province_field_path = 'user__province'

    def get_queryset(self):
        queryset = Notification.objects.select_related('user').order_by('-created_at')

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            queryset = queryset.filter(user__province=user.province)

        # ========== فیلترها ==========
        user_id = self.request.GET.get('user')
        if user_id and user_id.isdigit():
            queryset = queryset.filter(user_id=int(user_id))

        is_read = self.request.GET.get('is_read')
        if is_read == 'read':
            queryset = queryset.filter(is_read=True)
        elif is_read == 'unread':
            queryset = queryset.filter(is_read=False)

        notification_type = self.request.GET.get('type')
        if notification_type:
            queryset = queryset.filter(type=notification_type)

        date_filter = self.request.GET.get('date_filter')
        today = timezone.now().date()

        if date_filter == 'today':
            queryset = queryset.filter(created_at__date=today)
        elif date_filter == 'week':
            week_ago = today - timedelta(days=7)
            queryset = queryset.filter(created_at__date__gte=week_ago)
        elif date_filter == 'month':
            month_ago = today - timedelta(days=30)
            queryset = queryset.filter(created_at__date__gte=month_ago)

        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(message__icontains=search) |
                Q(user__phone_number__icontains=search) |
                Q(user__nickname__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_regional = user.is_regional_manager and user.province_id

        context['current_user'] = self.request.GET.get('user', '')
        context['current_is_read'] = self.request.GET.get('is_read', '')
        context['current_type'] = self.request.GET.get('type', '')
        context['current_date_filter'] = self.request.GET.get('date_filter', '')
        context['current_search'] = self.request.GET.get('q', '')

        user_id = self.request.GET.get('user')
        if user_id and user_id.isdigit():
            try:
                user_obj = CustomUser.objects.get(id=int(user_id))
                context['filtered_user_name'] = user_obj.nickname or user_obj.phone_number
            except CustomUser.DoesNotExist:
                pass

        # آمار پایه با فیلتر Regional
        base_qs = Notification.objects.all()
        if is_regional:
            base_qs = base_qs.filter(user__province=user.province)

        if user_id and user_id.isdigit():
            base_qs = base_qs.filter(user_id=int(user_id))

        context['total_count'] = base_qs.count()
        context['unread_count'] = base_qs.filter(is_read=False).count()
        context['read_count'] = base_qs.filter(is_read=True).count()

        context['type_choices'] = Notification.Type.choices

        return context