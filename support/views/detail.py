# support/views/detail.py

"""
DetailView های پنل Support

هر View بر اساس نقش، دسترسی و فیلتر استانی مناسب داره.
اگه کاربر به آبجکت دسترسی نداشت، 404 می‌گیره.
"""

from django.contrib.auth import get_user_model
from django.db.models import Avg, Prefetch, Sum, Q
from django.views.generic import DetailView
from django.utils import timezone
import json

from ..mixins import (
    BaseSupportMixin,
    ContentManagerRequiredMixin,
    PublishManagerRequiredMixin,
    RegionalFilterMixin,
    RegionalFilterComplexMixin,
)
from ..forms import TicketReplyForm
from influencers.models import ChannelBooking, ChannelServiceRate, ChannelReview, Channel
from payment.models import Transaction, Coupon, Payment
from campaigns.models import Campaign, CampaignReport
from tickets.models import Ticket
from content_team.models import (
    ContentOrder,
    ContentTeam,
    TeamReview,
    ContentServicePlan,
    ContentTeamMember,
    ContentOrderDescription,
    ContentOrderFile,
    ContentDelivery,
    ContentOrderRevision,
    ContentDeliveryFile,
)

User = get_user_model()


# ============================================================
#                        Ticket Detail
# ============================================================
class TicketDetailView(BaseSupportMixin, RegionalFilterMixin, DetailView):
    """
    جزئیات تیکت

    دسترسی: همه نقش‌ها
    فیلتر Regional: تیکت‌های استان خودش
    """
    model = Ticket
    template_name = 'support/tickets/ticket_detail.html'
    context_object_name = 'ticket'

    province_field_path = 'user__province'

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'user', 'category', 'title', 'campaign'
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(user__province=user.province)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages'] = self.object.messages.select_related('sender').prefetch_related(
            'attachments'
        ).order_by('created_at')
        context['form'] = TicketReplyForm()
        return context


# ============================================================
#                       Channel Detail
# ============================================================
class ChannelDetailView(PublishManagerRequiredMixin, RegionalFilterMixin, DetailView):
    """
    جزئیات کامل یک کانال اینفلوئنسر

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: کانال استان خودش
    """
    model = Channel
    template_name = 'support/channels/channel_detail.html'
    context_object_name = 'channel'
    pk_url_kwarg = 'pk'

    province_field_path = 'province'

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'influencer',
            'influencer__user',
            'platform',
            'province',
            'category',
            'score',
            'score__badge',
        ).prefetch_related(
            Prefetch(
                'service_rates',
                queryset=ChannelServiceRate.objects.select_related('ad_type').filter(is_active=True)
            ),
            Prefetch(
                'campaign_bookings',
                queryset=ChannelBooking.objects.select_related(
                    'campaign',
                    'campaign__advertiser',
                    'service_rate__ad_type'
                ).order_by('-created_at')
            ),
            Prefetch(
                'reviews',
                queryset=ChannelReview.objects.select_related(
                    'advertiser',
                    'advertiser__user'
                ).order_by('-created_at')
            ),
            Prefetch('coupons', queryset=Coupon.objects.filter(is_active=True)),
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(province=user.province)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        channel = self.object

        context['influencer'] = channel.influencer
        context['service_rates'] = channel.service_rates.filter(is_active=True)

        all_bookings = channel.campaign_bookings.all().order_by('-created_at')
        context['recent_bookings'] = all_bookings[:5]
        context['bookings_count'] = all_bookings.count()

        context['completed_bookings'] = channel.campaign_bookings.filter(status='completed').count()
        context['pending_bookings'] = channel.campaign_bookings.filter(status='pending').count()
        context['accepted_bookings'] = channel.campaign_bookings.filter(status='accepted').count()
        context['rejected_bookings'] = channel.campaign_bookings.filter(status='rejected').count()

        total_revenue = channel.campaign_bookings.filter(
            status='completed'
        ).aggregate(total=Sum('price'))['total'] or 0
        context['total_revenue'] = total_revenue

        all_reviews = channel.reviews.all().order_by('-created_at')
        context['recent_reviews'] = all_reviews[:5]
        context['reviews_count'] = all_reviews.count()

        context['avg_rating'] = channel.reviews.aggregate(avg=Avg('rating'))['avg']
        if context['avg_rating']:
            context['avg_rating'] = round(context['avg_rating'], 1)

        context['coupons'] = channel.coupons.filter(is_active=True)
        context['channel_url'] = channel.url or f"@{channel.channel_id}"

        return context


# ============================================================
#                       Campaign Detail
# ============================================================
class CampaignDetailView(PublishManagerRequiredMixin, RegionalFilterMixin, DetailView):
    """
    جزئیات کامل یک کمپین

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: از طریق تبلیغ‌دهنده
    """
    model = Campaign
    template_name = 'support/campaigns/campaign_detail.html'
    context_object_name = 'campaign'

    province_field_path = 'advertiser__user__province'

    def get_queryset(self):
        qs = super().get_queryset().select_related(
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
            'content',
        ).prefetch_related(
            Prefetch(
                'influencer_bookings',
                queryset=ChannelBooking.objects.select_related(
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
                    'revisions',
                    Prefetch(
                        'deliveries',
                        queryset=ContentDelivery.objects.prefetch_related(
                            Prefetch('files', queryset=ContentDeliveryFile.objects.all())
                        )
                    ),
                )
            ),
            Prefetch(
                'invoice__payments',
                queryset=Payment.objects.select_related('user').all()
            ),
            Prefetch(
                'transactions',
                queryset=Transaction.objects.select_related('user').all()
            ),
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(advertiser__user__province=user.province)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = self.object

        # ===== دریافت رزروهای اینفلوئنسر =====
        influencer_bookings = campaign.influencer_bookings.all()
        context['influencer_bookings'] = influencer_bookings[:5]
        context['influencer_count'] = influencer_bookings.count()

        # ===== محتوای کمپین =====
        campaign_content = getattr(campaign, 'content', None)
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

        # ===== سفارش‌های تولید محتوا =====
        content_orders = campaign.content_orders.all()
        context['content_orders'] = content_orders
        context['orders_count'] = content_orders.count()

        # ===== فایل انتخاب شده برای هر سفارش =====
        for order in content_orders:
            selected_file = None
            for delivery in order.deliveries.all():
                selected_file = delivery.files.filter(is_selected=True).first()
                if selected_file:
                    break
            order._selected_file = selected_file

        # ===== گزارشات =====
        reports = CampaignReport.objects.filter(
            campaign_influencer__campaign=campaign
        ).select_related(
            'campaign_influencer',
            'campaign_influencer__channel'
        )
        context['reports'] = reports
        context['reports_count'] = reports.count()

        # ===== پرداخت‌ها =====
        if hasattr(campaign, 'invoice') and campaign.invoice:
            payments = campaign.invoice.payments.all()
        else:
            payments = []
        context['payments'] = payments

        # ===== تراکنش‌ها =====
        context['transactions'] = campaign.transactions.all()

        return context


# ============================================================
#                        Report Detail
# ============================================================
class ReportDetailView(PublishManagerRequiredMixin, RegionalFilterMixin, DetailView):
    """
    جزئیات کامل یک گزارش کمپین

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: از طریق کانال
    """
    model = CampaignReport
    template_name = 'support/reports/report_detail.html'
    context_object_name = 'report'
    pk_url_kwarg = 'pk'

    province_field_path = 'campaign_influencer__channel__province'

    def get_queryset(self):
        qs = super().get_queryset().select_related(
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

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(
                campaign_influencer__channel__province=user.province
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.object
        booking = report.campaign_influencer

        context['campaign'] = booking.campaign
        context['channel'] = booking.channel
        context['influencer'] = booking.channel.influencer
        context['booking'] = booking

        auto_details = report.auto_check_details or {}
        context['auto_details'] = auto_details
        context['auto_details_json'] = (
            json.dumps(auto_details, indent=2, ensure_ascii=False)
            if auto_details else None
        )

        context['overall_score'] = auto_details.get('overall_score') if auto_details else None

        context['transactions'] = Transaction.objects.filter(
            campaign=booking.campaign,
            user=booking.channel.influencer.user
        ).order_by('-created_at')[:5]

        return context


# ============================================================
#                        User Detail
# ============================================================
class UserDetailView(BaseSupportMixin, RegionalFilterMixin, DetailView):
    """
    جزئیات کامل یک کاربر

    دسترسی: همه نقش‌ها
    فیلتر Regional: کاربر استان خودش
    """
    model = User
    template_name = 'support/users/user_detail.html'
    context_object_name = 'user'

    province_field_path = 'province'

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'province', 'wallet'
        ).prefetch_related(
            Prefetch('transactions', queryset=Transaction.objects.order_by('-created_at')),
            Prefetch('tickets', queryset=Ticket.objects.order_by('-created_at')),
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(province=user.province)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.object

        # کیف پول
        context['wallet'] = getattr(user_obj, 'wallet', None)

        # تراکنش‌ها
        all_transactions = user_obj.transactions.all().order_by('-created_at')
        context['transactions'] = all_transactions[:5]
        context['transactions_count'] = all_transactions.count()

        # پروفایل تبلیغ دهنده
        if hasattr(user_obj, 'advertiser_profile'):
            context['advertiser_profile'] = user_obj.advertiser_profile
            campaigns_qs = user_obj.advertiser_profile.campaigns.all().order_by('-created_at')
            context['campaigns'] = campaigns_qs[:5]
            context['campaigns_count'] = campaigns_qs.count()
        else:
            context['advertiser_profile'] = None
            context['campaigns'] = []
            context['campaigns_count'] = 0

        # پروفایل اینفلوئنسر
        if hasattr(user_obj, 'influencer_profile'):
            context['influencer_profile'] = user_obj.influencer_profile
            channels_qs = user_obj.influencer_profile.channels.all().order_by('-created_at')
            context['channels'] = channels_qs[:5]
            context['channels_count'] = channels_qs.count()

            bookings_qs = ChannelBooking.objects.filter(
                channel__influencer=user_obj.influencer_profile
            ).order_by('-created_at')
            context['campaign_bookings'] = bookings_qs[:5]
            context['bookings_count'] = bookings_qs.count()
        else:
            context['influencer_profile'] = None
            context['channels'] = []
            context['channels_count'] = 0
            context['campaign_bookings'] = []
            context['bookings_count'] = 0

        # عضو تیم
        context['team_member'] = getattr(user_obj, 'team_member', None)

        # تیکت‌ها
        all_tickets = user_obj.tickets.all().order_by('-created_at')
        context['tickets'] = all_tickets[:5]
        context['tickets_count'] = all_tickets.count()

        # نوتیفیکیشن‌ها
        all_notifications = user_obj.notifications.all().order_by('-created_at')
        context['notifications'] = all_notifications[:5]
        context['notifications_count'] = all_notifications.count()
        context['unread_notifications_count'] = user_obj.notifications.filter(is_read=False).count()
        context['user_obj'] = user_obj

        return context


# ============================================================
#                        Team Detail
# ============================================================
class TeamDetailView(ContentManagerRequiredMixin, RegionalFilterMixin, DetailView):
    """
    جزئیات کامل یک تیم تولید محتوا

    دسترسی: CEO + Dev + Content Manager
    فیلتر Regional: تیم استان خودش
    """
    model = ContentTeam
    template_name = 'support/content_team/team_detail.html'
    context_object_name = 'team'
    pk_url_kwarg = 'pk'

    province_field_path = 'province'

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'score', 'province'
        ).prefetch_related(
            Prefetch(
                'members',
                queryset=ContentTeamMember.objects.select_related('user').filter(is_active=True)
            ),
            Prefetch(
                'service_plans',
                queryset=ContentServicePlan.objects.select_related('service_type').filter(is_active=True)
            ),
            Prefetch(
                'orders',
                queryset=ContentOrder.objects.select_related('campaign', 'plan').order_by('-created_at')
            ),
            Prefetch(
                'reviews',
                queryset=TeamReview.objects.select_related('advertiser__user').order_by('-created_at')
            ),
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(province=user.province)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object

        context['members'] = team.members.filter(is_active=True)
        context['members_count'] = context['members'].count()

        context['plans'] = team.service_plans.filter(is_active=True)
        context['plans_count'] = context['plans'].count()

        all_orders = team.orders.all().order_by('-created_at')
        context['recent_orders'] = all_orders[:5]
        context['orders_count'] = all_orders.count()

        context['completed_orders'] = team.orders.filter(status='completed').count()
        context['pending_orders'] = team.orders.filter(status='pending').count()
        context['in_progress_orders'] = team.orders.filter(status='in_progress').count()
        context['cancelled_orders'] = team.orders.filter(status='cancelled').count()

        all_reviews = team.reviews.all().order_by('-created_at')
        context['recent_reviews'] = all_reviews[:5]
        context['reviews_count'] = all_reviews.count()

        context['avg_rating'] = team.reviews.aggregate(avg=Avg('rating'))['avg']
        if context['avg_rating']:
            context['avg_rating'] = round(context['avg_rating'], 1)

        total_revenue = team.orders.filter(status='completed').aggregate(
            total=Sum('price')
        )['total'] or 0
        context['total_revenue'] = total_revenue

        context['is_revenue_valid'] = team.is_revenue_share_valid()

        return context


# ============================================================
#                     Content Order Detail
# ============================================================
class ContentOrderDetailView(ContentManagerRequiredMixin, RegionalFilterComplexMixin, DetailView):
    """
    جزئیات کامل یک سفارش تولید محتوا

    دسترسی: CEO + Dev + Content Manager
    فیلتر Regional: پیچیده (کمپین یا مستقل)
    """
    model = ContentOrder
    template_name = 'support/content_team/order_detail.html'
    context_object_name = 'order'
    pk_url_kwarg = 'pk'

    @staticmethod
    def province_q_object(province):
        """فیلتر پیچیده برای Regional Manager"""
        return (
                Q(campaign__advertiser__user__province=province) |
                Q(standalone_user__province=province)
        )

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'campaign',
            'campaign__advertiser',
            'campaign__advertiser__user',
            'campaign__platform',
            'campaign__content_type',
            'campaign__ad_type',
            'team',
            'plan',
            'plan__service_type',
            'standalone_user',
        ).prefetch_related(
            Prefetch('brief', queryset=ContentOrderDescription.objects.all()),
            Prefetch('files', queryset=ContentOrderFile.objects.all()),
            Prefetch(
                'deliveries',
                queryset=ContentDelivery.objects.select_related(
                    'delivered_by__user'
                ).order_by('-version')
            ),
            Prefetch(
                'revisions',
                queryset=ContentOrderRevision.objects.select_related(
                    'requested_by'
                ).order_by('-created_at')
            ),
        )

        # ========== فیلتر Regional ==========
        user = self.request.user
        if user.is_regional_manager and user.province_id:
            qs = qs.filter(
                Q(campaign__advertiser__user__province=user.province) |
                Q(standalone_user__province=user.province)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # ===== بریف =====
        context['brief'] = getattr(order, 'brief', None)

        # ===== فایل‌های پیوست =====
        context['files'] = order.files.all()

        # ===== تحویل‌ها =====
        deliveries = order.deliveries.all().order_by('-version')
        context['deliveries'] = deliveries
        context['deliveries_count'] = deliveries.count()

        context['latest_delivery'] = deliveries.first() if deliveries.exists() else None

        # ===== فایل‌های تحویل =====
        delivery_files = ContentDeliveryFile.objects.filter(
            delivery__order=order
        ).select_related('delivery')
        context['delivery_files'] = delivery_files
        context['delivery_files_count'] = delivery_files.count()

        # ===== ویرایش‌ها =====
        revisions = order.revisions.all().order_by('-created_at')
        context['revisions'] = revisions[:5]
        context['revisions_count'] = revisions.count()
        context['pending_revisions'] = revisions.filter(status='pending').count()

        # ===== نظرات تیم =====
        team_reviews = TeamReview.objects.filter(
            order=order
        ).select_related('advertiser__user')
        context['team_reviews'] = team_reviews[:5]
        context['reviews_count'] = team_reviews.count()

        # ===== تراکنش‌های مرتبط =====
        transactions = Transaction.objects.filter(
            campaign=order.campaign
        ).select_related('user').order_by('-created_at')
        context['transactions'] = transactions[:10]
        context['transactions_count'] = transactions.count()

        # ===== اطلاعات اضافی =====
        context['now'] = timezone.now()

        # ===== وضعیت ددلاین =====
        if order.deadline:
            deadline_dt = (
                order.deadline.togregorian()
                if hasattr(order.deadline, 'togregorian')
                else order.deadline
            )
            if timezone.is_naive(deadline_dt):
                deadline_dt = timezone.make_aware(deadline_dt)
            context['is_deadline_passed'] = deadline_dt < timezone.now()
        else:
            context['is_deadline_passed'] = False

        return context
