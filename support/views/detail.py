from influencers.models import InfluencerServiceRate, InfluencerReview, CampaignReport, InfluencerChannel
from django.views.generic import DetailView
from campaigns.models import Coupon, CampaignInfluencer, Campaign
from ..mixins import SupportRequiredMixin
from django.db.models import Avg, Prefetch, Sum
from accounts.models import Transaction
from django.contrib.auth import get_user_model
from ..forms import TicketReplyForm
from tickets.models import Ticket
import json
from content_team.models import (
    ContentOrder,
    ContentTeam,
    TeamReview,
    ContentServicePlan,
    ContentTeamMember,
    ContentOrderDescription,
    ContentOrderFile,
    ContentDelivery,
    ContentOrderRevision
)

User = get_user_model()


class TicketDetailView(SupportRequiredMixin, DetailView):
    model = Ticket
    template_name = 'support/tickets/ticket_detail.html'
    context_object_name = 'ticket'

    def get_queryset(self):
        return super().get_queryset().select_related('user', 'category', 'title', 'campaign')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages'] = self.object.messages.select_related('sender').prefetch_related(
            'attachments'
        ).order_by('created_at')
        context['form'] = TicketReplyForm()
        return context


class ChannelDetailView(SupportRequiredMixin, DetailView):
    """جزئیات کامل یک کانال اینفلوئنسر"""
    model = InfluencerChannel
    template_name = 'support/channels/channel_detail.html'
    context_object_name = 'channel'
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'influencer',
            'influencer__user',
            'platform',
            'province',
            'category',
            'score',
            'score__badge',
        ).prefetch_related(
            Prefetch('service_rates',
                     queryset=InfluencerServiceRate.objects.select_related('ad_type').filter(is_active=True)),
            Prefetch('campaign_bookings', queryset=CampaignInfluencer.objects.select_related(
                'campaign',
                'campaign__advertiser',
                'service_rate__ad_type'
            ).order_by('-created_at')),
            Prefetch('reviews', queryset=InfluencerReview.objects.select_related(
                'advertiser',
                'advertiser__user'
            ).order_by('-created_at')),
            Prefetch('coupons', queryset=Coupon.objects.filter(is_active=True)),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        channel = self.object

        # ===== اطلاعات اینفلوئنسر =====
        context['influencer'] = channel.influencer

        # ===== نرخ‌های خدمات =====
        context['service_rates'] = channel.service_rates.filter(is_active=True)

        # ===== سفارش‌های اخیر (۵ تا آخر) =====
        all_bookings = channel.campaign_bookings.all().order_by('-created_at')
        context['recent_bookings'] = all_bookings[:5]
        context['bookings_count'] = all_bookings.count()

        # ===== آمار سفارش‌ها =====
        context['completed_bookings'] = channel.campaign_bookings.filter(status='completed').count()
        context['pending_bookings'] = channel.campaign_bookings.filter(status='pending').count()
        context['accepted_bookings'] = channel.campaign_bookings.filter(status='accepted').count()
        context['rejected_bookings'] = channel.campaign_bookings.filter(status='rejected').count()

        # ===== جمع درآمد =====
        total_revenue = channel.campaign_bookings.filter(
            status='completed'
        ).aggregate(total=Sum('price'))['total'] or 0
        context['total_revenue'] = total_revenue

        # ===== نظرات اخیر (۵ تا آخر) =====
        all_reviews = channel.reviews.all().order_by('-created_at')
        context['recent_reviews'] = all_reviews[:5]
        context['reviews_count'] = all_reviews.count()

        # ===== میانگین امتیاز =====
        context['avg_rating'] = channel.reviews.aggregate(avg=Avg('rating'))['avg']
        if context['avg_rating']:
            context['avg_rating'] = round(context['avg_rating'], 1)

        # ===== کوپن‌های فعال =====
        context['coupons'] = channel.coupons.filter(is_active=True)

        # ===== لینک یکتا =====
        context['channel_url'] = channel.url or f"@{channel.channel_id}"

        return context


class CampaignDetailView(SupportRequiredMixin, DetailView):
    model = Campaign
    template_name = 'support/campaigns/campaign_detail.html'
    context_object_name = 'campaign'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'advertiser__user',
            'advertiser__user__province',
            'platform',
            'content_type',
            'ad_type',
            'invoice',
            'content_service_type',
            'influencer_coupon',
            'content_team_coupon',
            'platform_coupon',
        ).prefetch_related(
            Prefetch(
                'influencer_bookings',
                queryset=CampaignInfluencer.objects.select_related(
                    'channel',
                    'channel__platform',
                    'channel__influencer',
                    'service_rate',
                    'service_rate__ad_type'
                ).prefetch_related(
                    'channel__score'
                )
            ),
            Prefetch(
                'content_orders',
                queryset=ContentOrder.objects.select_related(
                    'team',
                    'plan',
                    'plan__service_type'
                ).prefetch_related(
                    'brief',
                    'files',
                    'delivery'
                )
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = self.object

        # ===== دریافت رزروهای اینفلوئنسر (با اطمینان از وجود دیتا) =====
        influencer_bookings = campaign.influencer_bookings.all()
        context['influencer_bookings'] = influencer_bookings[:5]

        # ===== محتوای کمپین =====
        campaign_content = None
        if hasattr(campaign, 'content') and campaign.content:
            campaign_content = campaign.content
        context['campaign_content'] = campaign_content

        # ===== اطلاعات مورد نیاز برای پیش‌نمایش =====
        if campaign_content:
            context['media_url'] = campaign_content.media.url if campaign_content.media else None
            context['is_video'] = campaign_content.is_video if campaign_content.media else False
            context['caption'] = campaign_content.caption
            context['link'] = campaign_content.link
            context['notes'] = campaign_content.notes
            context['utm_enabled'] = campaign_content.utm_enabled
            context['utm_params'] = {
                'source': campaign_content.utm_source,
                'medium': campaign_content.utm_medium,
                'campaign': campaign_content.utm_campaign,
                'content': campaign_content.utm_content,
                'term': campaign_content.utm_term,
            }
        else:
            context['media_url'] = None
            context['is_video'] = False
            context['caption'] = None
            context['link'] = None
            context['notes'] = None
            context['utm_enabled'] = False
            context['utm_params'] = {}

        # ===== محتوای کمپین =====
        if hasattr(campaign, 'content') and campaign.content:
            context['campaign_content'] = campaign.content
        else:
            context['campaign_content'] = None

        # ===== سفارش‌های تولید محتوا =====
        content_orders = campaign.content_orders.all()
        context['content_orders'] = content_orders

        # ===== گزارشات =====
        reports = CampaignReport.objects.filter(
            campaign_influencer__campaign=campaign
        ).select_related(
            'campaign_influencer',
            'campaign_influencer__channel'
        )
        context['reports'] = reports

        # ===== پرداخت‌ها =====
        payments = campaign.payments.all() if hasattr(campaign, 'payments') else []
        context['payments'] = payments

        # ===== تراکنش‌ها =====
        transactions = campaign.transactions.all() if hasattr(campaign, 'transactions') else []
        context['transactions'] = transactions

        # ===== آمار =====
        context['influencer_count'] = influencer_bookings.count()
        context['orders_count'] = content_orders.count()
        context['reports_count'] = reports.count()

        return context


class ReportDetailView(SupportRequiredMixin, DetailView):
    """جزئیات کامل یک گزارش کمپین"""
    model = CampaignReport
    template_name = 'support/reports/report_detail.html'
    context_object_name = 'report'
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'campaign_influencer',
            'campaign_influencer__campaign',
            'campaign_influencer__campaign__advertiser',
            'campaign_influencer__campaign__advertiser__user',
            'campaign_influencer__campaign__platform',
            'campaign_influencer__channel',
            'campaign_influencer__channel__platform',
            'campaign_influencer__channel__influencer',
            'campaign_influencer__channel__influencer__user',
            'campaign_influencer__channel__province',
            'campaign_influencer__service_rate',
            'campaign_influencer__service_rate__ad_type',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.object
        booking = report.campaign_influencer

        # اطلاعات کمپین
        context['campaign'] = booking.campaign

        # اطلاعات کانال و اینفلوئنسر
        context['channel'] = booking.channel
        context['influencer'] = booking.channel.influencer

        # اطلاعات رزرو
        context['booking'] = booking

        auto_details = report.auto_check_details or {}
        context['auto_details'] = auto_details
        context['auto_details_json'] = json.dumps(auto_details, indent=2, ensure_ascii=False) if auto_details else None

        # امتیاز کلی
        context['overall_score'] = auto_details.get('overall_score') if auto_details else None

        # تراکنش‌های مرتبط
        context['transactions'] = Transaction.objects.filter(
            campaign=booking.campaign,
            user=booking.channel.influencer.user
        ).order_by('-created_at')[:5]

        return context


class UserDetailView(SupportRequiredMixin, DetailView):
    model = User
    template_name = 'support/users/user_detail.html'
    context_object_name = 'user'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'province', 'wallet'
        ).prefetch_related(
            Prefetch('transactions', queryset=Transaction.objects.order_by('-created_at')),
            Prefetch('tickets', queryset=Ticket.objects.order_by('-created_at')),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object

        # کیف پول
        context['wallet'] = getattr(user, 'wallet', None)

        # تراکنش‌ها (۱۰ تا آخر)
        all_transactions = user.transactions.all().order_by('-created_at')
        context['transactions'] = all_transactions[:5]
        context['transactions_count'] = all_transactions.count()

        # پروفایل تبلیغ‌دهنده
        if hasattr(user, 'advertiser_profile'):
            context['advertiser_profile'] = user.advertiser_profile
            campaigns_qs = user.advertiser_profile.campaigns.all().order_by('-created_at')
            context['campaigns'] = campaigns_qs[:5]
            context['campaigns_count'] = campaigns_qs.count()
        else:
            context['advertiser_profile'] = None
            context['campaigns'] = []
            context['campaigns_count'] = 0

        # پروفایل اینفلوئنسر
        if hasattr(user, 'influencer_profile'):
            context['influencer_profile'] = user.influencer_profile
            channels_qs = user.influencer_profile.channels.all().order_by('-created_at')
            context['channels'] = channels_qs[:5]
            context['channels_count'] = channels_qs.count()

            bookings_qs = CampaignInfluencer.objects.filter(
                channel__influencer=user.influencer_profile
            ).order_by('-created_at')
            context['campaign_bookings'] = bookings_qs[:5]
            context['bookings_count'] = bookings_qs.count()
        else:
            context['influencer_profile'] = None
            context['channels'] = []
            context['channels_count'] = 0
            context['campaign_bookings'] = []
            context['bookings_count'] = 0

        # عضو تیم تولید محتوا
        context['team_member'] = getattr(user, 'team_member', None)

        # تیکت‌ها (۵ تا آخر)
        all_tickets = user.tickets.all().order_by('-created_at')
        context['tickets'] = all_tickets[:5]
        context['tickets_count'] = all_tickets.count()

        # ===== نوتیفیکیشن‌ها (۵ تا آخر) =====
        all_notifications = user.notifications.all().order_by('-created_at')
        context['notifications'] = all_notifications[:5]
        context['notifications_count'] = all_notifications.count()
        context['unread_notifications_count'] = user.notifications.filter(is_read=False).count()

        return context


class TeamDetailView(SupportRequiredMixin, DetailView):
    """جزئیات کامل یک تیم تولید محتوا"""
    model = ContentTeam
    template_name = 'support/content_team/team_detail.html'
    context_object_name = 'team'
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'score'
        ).prefetch_related(
            Prefetch('members', queryset=ContentTeamMember.objects.select_related('user').filter(is_active=True)),
            Prefetch('service_plans',
                     queryset=ContentServicePlan.objects.select_related('service_type').filter(is_active=True)),
            Prefetch('orders',
                     queryset=ContentOrder.objects.select_related('campaign', 'plan').order_by('-created_at')),
            Prefetch('reviews', queryset=TeamReview.objects.select_related('advertiser__user').order_by('-created_at')),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object

        # ===== اعضای تیم =====
        context['members'] = team.members.filter(is_active=True)
        context['members_count'] = context['members'].count()

        # ===== پلن‌های خدمت =====
        context['plans'] = team.service_plans.filter(is_active=True)
        context['plans_count'] = context['plans'].count()

        # ===== سفارش‌ها (۵ تا آخر) =====
        all_orders = team.orders.all().order_by('-created_at')
        context['recent_orders'] = all_orders[:5]
        context['orders_count'] = all_orders.count()

        # ===== آمار سفارش‌ها =====
        context['completed_orders'] = team.orders.filter(status='completed').count()
        context['pending_orders'] = team.orders.filter(status='pending').count()
        context['in_progress_orders'] = team.orders.filter(status='in_progress').count()
        context['cancelled_orders'] = team.orders.filter(status='cancelled').count()

        # ===== نظرات (۵ تا آخر) =====
        all_reviews = team.reviews.all().order_by('-created_at')
        context['recent_reviews'] = all_reviews[:5]
        context['reviews_count'] = all_reviews.count()

        # ===== میانگین امتیاز =====
        context['avg_rating'] = team.reviews.aggregate(avg=Avg('rating'))['avg']
        if context['avg_rating']:
            context['avg_rating'] = round(context['avg_rating'], 1)

        # ===== جمع درآمد =====
        total_revenue = team.orders.filter(status='completed').aggregate(
            total=Sum('price')
        )['total'] or 0
        context['total_revenue'] = total_revenue

        # ===== آیا مجموع درصد سهام valid هست؟ =====
        context['is_revenue_valid'] = team.is_revenue_share_valid()

        return context


class ContentOrderDetailView(SupportRequiredMixin, DetailView):
    """جزئیات کامل یک سفارش تولید محتوا"""
    model = ContentOrder
    template_name = 'support/content_team/order_detail.html'
    context_object_name = 'order'
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'campaign',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'campaign__platform',
            'campaign__content_type',
            'campaign__ad_type',
            'team',
            'plan',
            'plan__service_type',
        ).prefetch_related(
            Prefetch('brief', queryset=ContentOrderDescription.objects.all()),
            Prefetch('files', queryset=ContentOrderFile.objects.all()),
            Prefetch('delivery', queryset=ContentDelivery.objects.all()),
            Prefetch('revisions',
                     queryset=ContentOrderRevision.objects.select_related('requested_by').order_by('-created_at')),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # بریف
        context['brief'] = getattr(order, 'brief', None)

        # فایل‌ها
        context['files'] = order.files.all()

        # تحویل نهایی
        context['delivery'] = getattr(order, 'delivery', None)

        # ویرایش‌ها
        context['revisions'] = order.revisions.all().order_by('-created_at')[:5]
        context['revisions_count'] = order.revisions.count()

        # نظرات تیم
        context['team_reviews'] = TeamReview.objects.filter(
            order=order
        ).select_related('advertiser__user')[:5]
        context['reviews_count'] = TeamReview.objects.filter(order=order).count()

        # تراکنش‌های مرتبط
        context['transactions'] = Transaction.objects.filter(
            campaign=order.campaign
        ).order_by('-created_at')[:10]
        context['transactions_count'] = Transaction.objects.filter(campaign=order.campaign).count()

        return context
