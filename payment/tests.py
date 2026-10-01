"""Regression coverage for platform-scoped managers and real wallet payouts."""
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from django.urls import resolve
from django.utils import timezone

from accounts.models import CustomUser
from advertisers.models import AdvertiserProfile
from campaigns.models import Campaign, CampaignReport
from content_team.models import ContentOrder, ContentTeam, ContentServicePlan
from core.models import Platform, AdType, ContentType, ContentServiceType, Province
from influencers.models import InfluencerProfile, Channel, ChannelServiceRate, ChannelBooking
from notifications.models import Notification
from tickets.models import Ticket, TicketCategory
from payment.models import Invoice, Wallet, Transaction, CommissionSplit
from payment.services.payout import payout_commission, PayoutError
from support.utils import scope_support_queryset, PlatformManagerAdminGuard
from support.views import list as lists, detail, api
from support.views.dashboard import DashboardView, FinanceDashboardView


@override_settings(ALLOWED_HOSTS=['testserver'], BASE_URL='http://testserver')
class PlatformManagerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.create(name='Test province')
        cls.users = {}
        for number, role in enumerate(CustomUser.Role.values, 1):
            cls.users[role] = CustomUser.objects.create_user(
                phone_number=f'09100000{number:03}', password='test-password', role=role,
                province=cls.province if role == 'regional_manager' else None,
            )
        cls.publisher = cls.users['publish_manager']
        cls.human = cls.users['human_media_manager']
        cls.owner = cls.users['none']
        cls.advertiser = AdvertiserProfile.objects.create(user=cls.owner, business_name='Shared owner')
        cls.influencer = InfluencerProfile.objects.create(user=cls.owner)
        cls.content_type = ContentType.objects.create(name='Ready', slug='ready-content')
        cls.category = TicketCategory.objects.create(name='Campaign', slug='campaign')
        cls.campaigns, cls.channels, cls.bookings, cls.reports, cls.tickets = {}, {}, {}, {}, {}
        for slug in ['instagram', 'bale', 'eitaa', 'rubika', 'soroush', 'telegram']:
            platform = Platform.objects.create(name=slug, slug=slug, logo='platform.png')
            ad_type = AdType.objects.create(platform=platform, name=slug, slug=slug)
            campaign = Campaign.objects.create(
                advertiser=cls.advertiser, platform=platform, content_type=cls.content_type,
                ad_type=ad_type, name=f'Campaign {slug}', status='pending',
                start_date=timezone.now().date() + timedelta(days=2),
                end_date=timezone.now().date() + timedelta(days=4),
            )
            channel = Channel.objects.create(influencer=cls.influencer, platform=platform,
                                             channel_name=f'Channel {slug}', channel_id=slug)
            rate = ChannelServiceRate.objects.create(channel=channel, ad_type=ad_type, price=1000)
            booking = ChannelBooking.objects.create(campaign=campaign, channel=channel,
                                                     service_rate=rate, price=1000)
            report = CampaignReport.objects.create(campaign_influencer=booking,
                                                     post_link='https://example.com/post', screenshot='test.png')
            ticket = Ticket.objects.create(user=cls.owner, category=cls.category, campaign=campaign,
                                           custom_title=f'Ticket {slug}')
            Notification.objects.create(user=cls.owner, type='campaign_pending', title=f'Notice {slug}',
                                        message=slug, related_content_type='Campaign', related_object_id=campaign.pk)
            cls.campaigns[slug], cls.channels[slug] = campaign, channel
            cls.bookings[slug], cls.reports[slug], cls.tickets[slug] = booking, report, ticket
        cls.team = ContentTeam.objects.create(name='Content team')
        cls.service = ContentServiceType.objects.create(name='Video', slug='video')
        cls.plan = ContentServicePlan.objects.create(team=cls.team, service_type=cls.service,
                                                    name='Plan', pricing_unit='quantity', price=1000)

    def request(self, user, path='/support/', method='get', data=None):
        request = getattr(RequestFactory(), method)(path, data=data or {})
        request.user = user
        return request

    def invoice(self, slug='instagram', mixed=False):
        campaign = self.campaigns[slug]
        if mixed:
            ContentOrder.objects.create(campaign=campaign, team=self.team, plan=self.plan, price=1000)
        return Invoice.objects.create(campaign=campaign, user=self.owner, invoice_number=f'TEST-{slug}',
                                      commission=10000, is_paid=True)

    def test_roles_and_support_access(self):
        self.assertTrue(self.human.has_support_access)
        self.assertTrue(self.human.is_human_media_manager)
        self.assertFalse(self.human.is_publish_manager)
        self.assertEqual(self.human.get_role_display(), 'مدیر انسان رسانه')

    def test_both_scopes_across_all_related_models(self):
        for model in [Campaign, Channel, ChannelBooking, CampaignReport, Ticket, Notification, Platform]:
            for user, count in [(self.human, 1), (self.publisher, 5), (self.users['ceo'], 6)]:
                with self.subTest(model=model.__name__, role=user.role):
                    self.assertEqual(scope_support_queryset(user, model.objects.all()).count(), count)

    def test_unknown_and_unlinked_data_fail_closed(self):
        Ticket.objects.create(user=self.owner, category=self.category, custom_title='Unlinked')
        Notification.objects.create(user=self.owner, type='new_order', title='Unknown', message='Unknown')
        for user in (self.publisher, self.human):
            self.assertFalse(scope_support_queryset(user, Ticket.objects.filter(campaign=None)).exists())
            self.assertFalse(scope_support_queryset(user, ContentTeam.objects.all()).exists())
            self.assertFalse(scope_support_queryset(user, Notification.objects.filter(title='Unknown')).exists())

    def test_malformed_cross_platform_booking_is_hidden_from_both_roles(self):
        booking = self.bookings['bale']
        ChannelBooking.objects.filter(pk=booking.pk).update(campaign=self.campaigns['instagram'])
        for user in (self.human, self.publisher):
            self.assertFalse(scope_support_queryset(user, ChannelBooking.objects.filter(pk=booking.pk)).exists())
            self.assertFalse(scope_support_queryset(user, CampaignReport.objects.filter(pk=self.reports['bale'].pk)).exists())

    def test_list_queries_cannot_override_scope_with_filters(self):
        for view_cls in [lists.ChannelListView, lists.CampaignListView, lists.CampaignBookingListView,
                         lists.ReportListView, lists.TicketListView, lists.NotificationListView]:
            for user, count in [(self.human, 1), (self.publisher, 5)]:
                with self.subTest(view=view_cls.__name__, role=user.role):
                    view = view_cls()
                    view.setup(self.request(user))
                    self.assertEqual(len(view.get_queryset()), count)
        response = lists.ChannelListView.as_view()(self.request(self.publisher, data={'platform': self.channels['instagram'].platform_id}))
        self.assertEqual(response.context_data['channels'].count(), 0)
        self.assertEqual(response.context_data['total_count'], 5)
        self.assertEqual(response.context_data['platforms'].count(), 5)

    def test_detail_urls_reject_other_platform(self):
        for view_cls, objects in [(detail.CampaignDetailView, self.campaigns),
                                  (detail.ChannelDetailView, self.channels),
                                  (detail.ReportDetailView, self.reports),
                                  (detail.TicketDetailView, self.tickets)]:
            for user, forbidden in [(self.publisher, 'instagram'), (self.human, 'bale')]:
                with self.subTest(view=view_cls.__name__, role=user.role):
                    with self.assertRaises(Http404):
                        view_cls.as_view()(self.request(user), pk=objects[forbidden].pk)

    def test_post_urls_reject_before_side_effects(self):
        for view_cls, objects in [(api.ChannelApproveView, self.channels), (api.ChannelRejectView, self.channels),
                                  (api.CampaignApproveView, self.campaigns), (api.CampaignRejectView, self.campaigns),
                                  (api.ReportApproveView, self.reports), (api.ReportRejectView, self.reports),
                                  (api.TicketReplyView, self.tickets)]:
            for user, forbidden in [(self.publisher, 'instagram'), (self.human, 'bale')]:
                with self.subTest(view=view_cls.__name__, role=user.role):
                    with self.assertRaises(Http404):
                        view_cls.as_view()(self.request(user, method='post', data={'message': 'Reply', 'reason': 'No'}), pk=objects[forbidden].pk)
        self.assertFalse(Transaction.objects.exists())
        self.assertEqual(Campaign.objects.filter(status='pending').count(), 6)
        self.assertEqual(Channel.objects.filter(status='pending').count(), 6)

    def test_permitted_detail_pages_render(self):
        for user, slug in [(self.publisher, 'bale'), (self.human, 'instagram')]:
            for view_cls, objects in [(detail.ChannelDetailView, self.channels), (detail.CampaignDetailView, self.campaigns),
                                      (detail.ReportDetailView, self.reports), (detail.TicketDetailView, self.tickets)]:
                with self.subTest(view=view_cls.__name__, role=user.role):
                    response = view_cls.as_view()(self.request(user), pk=objects[slug].pk)
                    self.assertEqual(response.status_code, 200)
                    response.render()

    def test_shared_user_detail_does_not_leak_other_platform(self):
        for user, count in [(self.human, 1), (self.publisher, 5)]:
            response = detail.UserDetailView.as_view()(self.request(user), pk=self.owner.pk)
            context = response.context_data
            for key in ['campaigns_count', 'channels_count', 'bookings_count', 'tickets_count', 'notifications_count']:
                self.assertEqual(context[key], count, key)
            self.assertIsNone(context['wallet'])
            self.assertNotIn('user', context)
            response.render()

    def test_dashboard_uses_scoped_counts_and_pending_actions(self):
        for user, count in [(self.human, 1), (self.publisher, 5)]:
            response = DashboardView.as_view()(self.request(user))
            context = response.context_data
            self.assertEqual(context['total_campaigns'], count)
            self.assertEqual(context['total_channels'], count)
            self.assertEqual(context['total_tickets'], count)
            self.assertTrue(context['dash_perms']['can_see_campaigns'])
            response.render()

    def test_other_departments_and_finance_are_denied(self):
        for user in (self.human, self.publisher):
            for view_cls in [lists.ContentOrderListView, lists.TeamListView, FinanceDashboardView]:
                with self.assertRaises(PermissionDenied):
                    view_cls.as_view()(self.request(user))

    def test_admin_guard_applies_even_with_superuser_flag(self):
        request = self.request(self.human, '/admin/')
        request.user.is_superuser = True
        request.user.is_staff = True
        request.resolver_match = resolve('/admin/')
        with self.assertRaises(PermissionDenied):
            PlatformManagerAdminGuard(lambda r: None).process_view(request, None, (), {})

    def test_anonymous_has_no_support_access(self):
        response = lists.CampaignListView.as_view()(self.request(AnonymousUser()))
        self.assertEqual(response.status_code, 302)

    def assert_payout(self, slug, mixed, recipient, amount):
        invoice = self.invoice(slug, mixed)
        result = payout_commission(invoice)
        self.assertTrue(result.success)
        tx = Transaction.objects.get(invoice=invoice, user=recipient)
        self.assertEqual(tx.amount, amount)
        self.assertEqual(tx.campaign_id, invoice.campaign_id)
        self.assertTrue(tx.is_income)
        self.assertEqual(Wallet.objects.get(user=recipient).balance, amount)
        other = self.publisher if recipient == self.human else self.human
        self.assertFalse(Transaction.objects.filter(invoice=invoice, user=other).exists())
        self.assertEqual(Wallet.objects.get(user=other).balance, 0)
        split = CommissionSplit.objects.get(invoice=invoice)
        self.assertEqual(split.snapshot['publishing_manager_role'], recipient.role)
        self.assertEqual(split.snapshot['publishing_manager_user_id'], recipient.pk)
        self.assertEqual(split.sum_of_shares, invoice.commission)
        return invoice, tx

    def test_instagram_publish_only_pays_thirty_percent_to_human(self):
        _, tx = self.assert_payout('instagram', False, self.human, 3000)
        self.assertEqual(tx.type, Transaction.Type.COMMISSION_HUMAN_MEDIA_MANAGER)

    def test_instagram_mixed_pays_fifteen_percent_to_human(self):
        self.assert_payout('instagram', True, self.human, 1500)
        self.assertEqual(Wallet.objects.get(user=self.users['content_manager']).balance, 1500)

    def test_other_platform_publish_only_pays_publisher(self):
        self.assert_payout('bale', False, self.publisher, 3000)

    def test_other_platform_mixed_pays_publisher(self):
        self.assert_payout('bale', True, self.publisher, 1500)

    def test_stale_invoice_cannot_pay_twice(self):
        invoice = self.invoice()
        self.assertTrue(payout_commission(invoice).success)
        self.assertFalse(payout_commission(invoice).success)
        self.assertEqual(Wallet.objects.get(user=self.human).balance, 3000)
        self.assertEqual(CommissionSplit.objects.count(), 1)

    def test_missing_recipient_rolls_back_every_wallet(self):
        self.human.is_active = False
        self.human.save()
        invoice = self.invoice()
        with self.assertRaises(PayoutError):
            payout_commission(invoice)
        self.assertFalse(Transaction.objects.exists())
        self.assertFalse(Wallet.objects.exclude(balance=0).exists())
        self.assertFalse(CommissionSplit.objects.exists())
        invoice.refresh_from_db()
        self.assertIsNone(invoice.commission_paid_at)

    def test_duplicate_recipient_rolls_back(self):
        CustomUser.objects.create_user(phone_number='09999999999', role='human_media_manager')
        with self.assertRaises(PayoutError):
            payout_commission(self.invoice())
        self.assertFalse(Transaction.objects.exists())
        self.assertFalse(Wallet.objects.exclude(balance=0).exists())

    def test_wrong_campaign_argument_is_rejected(self):
        with self.assertRaises(PayoutError):
            payout_commission(self.invoice(), campaign=self.campaigns['bale'])
        self.assertFalse(Transaction.objects.exists())

    def test_unpaid_invoice_cannot_pay(self):
        invoice = self.invoice()
        Invoice.objects.filter(pk=invoice.pk).update(is_paid=False)
        with self.assertRaises(PayoutError):
            payout_commission(invoice)
        self.assertFalse(Transaction.objects.exists())

    def test_historical_split_is_not_reclassified_by_current_platform(self):
        invoice = self.invoice()
        # Existing payouts have no recipient snapshot and remain the publisher's history.
        CommissionSplit.objects.create(invoice=invoice, publish_manager_amount=3000)
        data = FinanceDashboardView.as_view()(self.request(self.users['ceo'])).context_data
        self.assertEqual(data['role_breakdown_merged']['commission_publish_manager']['amount_total'], 3000)
        self.assertEqual(data['role_breakdown_merged']['commission_human_media_manager']['amount_total'], 0)

    def test_finance_reports_separate_actual_recipients(self):
        self.assert_payout('instagram', False, self.human, 3000)
        data = FinanceDashboardView.as_view()(self.request(self.users['ceo'])).context_data
        self.assertEqual(data['role_breakdown_merged']['commission_human_media_manager']['amount_total'], 3000)
        self.assertEqual(data['role_breakdown_merged']['commission_publish_manager']['amount_total'], 0)

    def test_standalone_content_does_not_pay_either_publishing_manager(self):
        order = ContentOrder.objects.create(standalone_user=self.owner, team=self.team, plan=self.plan, price=1000)
        invoice = Invoice.objects.create(type='content_order', content_order=order, invoice_number='CONTENT',
                                         commission=10000, is_paid=True)
        self.assertTrue(payout_commission(invoice).success)
        self.assertEqual(Wallet.objects.get(user=self.users['content_manager']).balance, 3000)
        self.assertEqual(Wallet.objects.get(user=self.human).balance, 0)
        self.assertEqual(Wallet.objects.get(user=self.publisher).balance, 0)

    def test_campaign_completion_flow_reaches_human_wallet(self):
        from campaigns.services.campaigns_notifications import _try_payout_commission
        invoice = self.invoice()
        Campaign.objects.filter(pk=invoice.campaign_id).update(status='completed')
        invoice = Invoice.objects.get(pk=invoice.pk)
        self.assertTrue(_try_payout_commission(invoice).success)
        self.assertEqual(Wallet.objects.get(user=self.human).balance, 3000)

    def test_mixed_completion_waits_for_content(self):
        from campaigns.services.campaigns_notifications import _try_payout_commission
        invoice = self.invoice(mixed=True)
        Campaign.objects.filter(pk=invoice.campaign_id).update(status='completed')
        invoice = Invoice.objects.get(pk=invoice.pk)
        self.assertIsNone(_try_payout_commission(invoice))
        self.assertFalse(Transaction.objects.exists())
        ContentOrder.objects.filter(campaign=invoice.campaign).update(status='completed')
        self.assertTrue(_try_payout_commission(invoice).success)
        self.assertEqual(Wallet.objects.get(user=self.human).balance, 1500)

    def test_scoped_list_templates_render(self):
        for user in (self.human, self.publisher):
            for view_cls in [lists.UserListView, lists.CampaignListView, lists.ChannelListView,
                             lists.CampaignBookingListView, lists.ReportListView,
                             lists.TicketListView, lists.NotificationListView]:
                with self.subTest(view=view_cls.__name__, role=user.role):
                    response = view_cls.as_view()(self.request(user))
                    self.assertEqual(response.status_code, 200)
                    response.render()

    def test_ordinary_ticket_routes_obey_scope_for_staff(self):
        from tickets.views import TicketListView, TicketDetailView
        for user, count, forbidden in [(self.human, 1, 'bale'), (self.publisher, 5, 'instagram')]:
            user.is_staff = True
            response = TicketListView.as_view()(self.request(user, '/tickets/'))
            self.assertEqual(response.context_data['total_count'], count)
            self.assertEqual(len(response.context_data['tickets']), count)
            with self.assertRaises(Http404):
                TicketDetailView.as_view()(self.request(user), pk=self.tickets[forbidden].pk)

    def test_missing_regional_manager_keeps_split_balanced(self):
        CustomUser.objects.filter(pk=self.owner.pk).update(province=self.province)
        CustomUser.objects.filter(role='regional_manager').update(is_active=False)
        invoice, _ = self.assert_payout('instagram', False, self.human, 3000)
        split = CommissionSplit.objects.get(invoice=invoice)
        self.assertEqual(split.regional_manager_amount, 0)
        self.assertEqual(split.sum_of_shares, invoice.commission)

    def test_finance_template_renders_new_role(self):
        self.assert_payout('instagram', True, self.human, 1500)
        response = FinanceDashboardView.as_view()(self.request(self.users['ceo']))
        response.render()
        self.assertContains(response, 'مدیر انسان رسانه')

    def test_regional_and_top_manager_roles_are_not_platform_restricted(self):
        for role in ('ceo', 'developer', 'regional_manager', 'content_manager'):
            user = self.users[role]
            self.assertEqual(scope_support_queryset(user, Campaign.objects.all()).count(), 6)
            self.assertEqual(scope_support_queryset(user, Channel.objects.all()).count(), 6)
