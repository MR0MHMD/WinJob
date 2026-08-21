from ..mixins import SupportRequiredMixin, SuperUserRequiredMixin
from payment.models import Transaction, Wallet, Invoice
from content_team.models import ContentOrder, ContentTeam
from influencers.models import ChannelBooking, Channel
from campaigns.models import Campaign, CampaignReport
from django.contrib.auth import get_user_model
from django.views.generic import TemplateView
from notifications.models import Notification
from django.db.models import Avg, Sum
from tickets.models import Ticket
from django.utils import timezone
from datetime import timedelta
import jdatetime

User = get_user_model()


class FinanceDashboardView(SuperUserRequiredMixin, TemplateView):
    """داشبورد مالی و مدیریت هزینه‌ها - فقط برای سوپر یوزر"""
    template_name = 'support/finance/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ============================================================ #
        #                    ۱. آمار واقعی از فاکتورها                 #
        # ============================================================ #

        # فاکتورهای پرداخت شده
        paid_invoices = Invoice.objects.filter(is_paid=True)

        # ===== هزینه ناشران (اینفلوئنسرها) =====
        total_influencer_cost = paid_invoices.aggregate(
            total=Sum('influencer_cost')
        )['total'] or 0

        # ===== هزینه تولید محتوا (تیم‌ها) =====
        total_content_cost = paid_invoices.aggregate(
            total=Sum('content_cost')
        )['total'] or 0

        # ===== سود خالص واقعی سامانه (کمیسیون) =====
        total_commission = paid_invoices.aggregate(
            total=Sum('commission')
        )['total'] or 0

        # ✅ کل درآمد ناخالص واقعی = جمع سه بخش (قبل از تخفیف)
        total_gross_income = total_influencer_cost + total_content_cost + total_commission

        # ===== کل تخفیف‌های اعمال شده =====
        total_discount = paid_invoices.aggregate(
            total=Sum('discount_amount')
        )['total'] or 0

        # ===== مبلغ قابل پرداخت نهایی (بعد از تخفیف) =====
        total_payable = paid_invoices.aggregate(
            total=Sum('payable_amount')
        )['total'] or 0

        # تعداد فاکتورهای پرداخت شده
        paid_invoices_count = paid_invoices.count()

        # ============================================================ #
        #                    ۲. موجودی کیف پول (اطلاعاتی)              #
        # ============================================================ #

        total_wallet_balance = Wallet.objects.aggregate(
            total=Sum('balance')
        )['total'] or 0

        users_with_wallet = Wallet.objects.filter(balance__gt=0).count()
        avg_wallet_balance = Wallet.objects.aggregate(
            avg=Avg('balance')
        )['avg'] or 0

        # ============================================================ #
        #                    ۳. تراکنش‌های موفق                        #
        # ============================================================ #

        successful_transactions = Transaction.objects.filter(status='success')
        total_volume = successful_transactions.aggregate(
            total=Sum('amount')
        )['total'] or 0

        # ============================================================ #
        #                    ۴. آمار تفکیکی تراکنش‌ها                  #
        # ============================================================ #

        advertiser_deposits = Transaction.objects.filter(
            status='success', type='deposit'
        ).aggregate(total=Sum('amount'))['total'] or 0

        gateway_income = Transaction.objects.filter(
            status='success', type='gateway_payment'
        ).aggregate(total=Sum('amount'))['total'] or 0

        influencer_payments = Transaction.objects.filter(
            status='success', type='influencer_payment'
        ).aggregate(total=Sum('amount'))['total'] or 0

        team_payments = Transaction.objects.filter(
            status='success', type='team_payment'
        ).aggregate(total=Sum('amount'))['total'] or 0

        refunds = Transaction.objects.filter(
            status='success',
            type__in=['campaign_refund', 'gateway_refund']
        ).aggregate(total=Sum('amount'))['total'] or 0

        # ============================================================ #
        #                    ۵. آمار کمپین‌ها                          #
        # ============================================================ #

        avg_campaign_cost = paid_invoices.aggregate(
            avg=Avg('payable_amount')
        )['avg'] or 0

        free_campaigns = Campaign.objects.filter(is_free=True).count()
        total_campaigns = Campaign.objects.count()

        # ============================================================ #
        #                    ۶. آمار بدهکاری‌ها                        #
        # ============================================================ #

        influencer_debts = ChannelBooking.objects.filter(
            status='completed', is_paid=False
        ).aggregate(total=Sum('price'))['total'] or 0

        influencer_debt_count = ChannelBooking.objects.filter(
            status='completed', is_paid=False
        ).count()

        team_debts = ContentOrder.objects.filter(
            status='completed'
        ).aggregate(total=Sum('price'))['total'] or 0

        # ============================================================ #
        #                    ۷. آمار روزانه، هفتگی، ماهانه             #
        # ============================================================ #

        today = timezone.now().date()
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        today_end = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.max.time())
        )

        # ✅ امروز - سود از فاکتورها
        today_invoices = Invoice.objects.filter(
            is_paid=True,
            created_at__range=(today_start, today_end)
        )
        today_commission = today_invoices.aggregate(
            total=Sum('commission')
        )['total'] or 0

        # ✅ هفته گذشته - سود از فاکتورها
        week_ago = timezone.now() - timedelta(days=7)
        week_invoices = Invoice.objects.filter(
            is_paid=True,
            created_at__gte=week_ago
        )
        week_commission = week_invoices.aggregate(
            total=Sum('commission')
        )['total'] or 0

        # ✅ ماه گذشته - سود از فاکتورها
        month_ago = timezone.now() - timedelta(days=30)
        month_invoices = Invoice.objects.filter(
            is_paid=True,
            created_at__gte=month_ago
        )
        month_commission = month_invoices.aggregate(
            total=Sum('commission')
        )['total'] or 0

        # ============================================================ #
        #                    ۸. داده‌های نمودارها                      #
        # ============================================================ #

        weekdays_fa = {
            0: 'شنبه', 1: 'یکشنبه', 2: 'دوشنبه',
            3: 'سه‌شنبه', 4: 'چهارشنبه', 5: 'پنجشنبه', 6: 'جمعه'
        }

        # نمودار سهم‌بندی فاکتورها
        revenue_breakdown = {
            'labels': ['هزینه ناشران', 'هزینه تولید محتوا', 'کمیسیون سامانه'],
            'data': [
                total_influencer_cost,
                total_content_cost,
                total_commission,
            ]
        }

        # نمودار درآمد و سود ۷ روز اخیر
        chart_daily_labels = []
        chart_daily_income = []
        chart_daily_commission = []

        for i in range(6, -1, -1):
            day = timezone.now() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

            jalali_date = jdatetime.date.fromgregorian(date=day.date())
            weekday_fa = weekdays_fa.get(jalali_date.weekday(), '')
            chart_daily_labels.append(weekday_fa)

            day_invoices = Invoice.objects.filter(
                is_paid=True,
                created_at__range=(day_start, day_end)
            )

            # ✅ درآمد ناخالص روز = جمع سه بخش
            day_influencer = day_invoices.aggregate(total=Sum('influencer_cost'))['total'] or 0
            day_content = day_invoices.aggregate(total=Sum('content_cost'))['total'] or 0
            day_commission = day_invoices.aggregate(total=Sum('commission'))['total'] or 0

            chart_daily_income.append(day_influencer + day_content + day_commission)
            chart_daily_commission.append(day_commission)

        # ============================================================ #
        #                    ۹. تراکنش‌های اخیر                       #
        # ============================================================ #

        recent_transactions = Transaction.objects.select_related(
            'user', 'campaign'
        ).order_by('-created_at')[:10]

        # ============================================================ #
        #                    ۱۰. اطلاعات تقویم شمسی                    #
        # ============================================================ #

        today_jalali = jdatetime.date.today()
        months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
        jalali_date_str = f"{today_jalali.day} {months[today_jalali.month - 1]} {today_jalali.year}"
        jalali_weekday = weekdays_fa.get(today_jalali.weekday(), '')

        # ============================================================ #
        #                    ۱۱. آمار تکمیلی                          #
        # ============================================================ #

        total_transactions = Transaction.objects.count()
        failed_transactions = Transaction.objects.filter(status='failed').count()
        success_rate = (successful_transactions.count() / total_transactions * 100) if total_transactions > 0 else 0

        def calc_percent(value, total):
            if total == 0:
                return 0
            return round((value / total) * 100, 1)

        # ✅ درصدها از کل درآمد ناخالص واقعی حساب میشن
        influencer_percent = calc_percent(total_influencer_cost, total_gross_income)
        content_percent = calc_percent(total_content_cost, total_gross_income)
        commission_percent = calc_percent(total_commission, total_gross_income)

        # ============================================================ #
        #                    ۱۲. خروجی نهایی                          #
        # ============================================================ #

        context.update({
            # ===== آمار واقعی از فاکتورها =====
            'total_gross_income': total_gross_income,  # ✅ درآمد ناخالص واقعی
            'total_commission': total_commission,
            'total_influencer_cost': total_influencer_cost,
            'total_content_cost': total_content_cost,
            'total_discount': total_discount,
            'total_payable': total_payable,  # مبلغ قابل پرداخت نهایی
            'paid_invoices_count': paid_invoices_count,

            # ===== درصدها =====
            'influencer_percent': influencer_percent,
            'content_percent': content_percent,
            'commission_percent': commission_percent,

            # ===== موجودی کیف پول (اطلاعاتی) =====
            'total_wallet_balance': total_wallet_balance,
            'users_with_wallet': users_with_wallet,
            'avg_wallet_balance': avg_wallet_balance,

            # ===== تراکنش‌ها =====
            'total_volume': total_volume,
            'advertiser_deposits': advertiser_deposits,
            'gateway_income': gateway_income,
            'influencer_payments': influencer_payments,
            'team_payments': team_payments,
            'refunds': refunds,

            # ===== آمار کمپین‌ها =====
            'avg_campaign_cost': avg_campaign_cost,
            'free_campaigns': free_campaigns,
            'total_campaigns': total_campaigns,

            # ===== بدهکاری‌ها =====
            'influencer_debts': influencer_debts,
            'influencer_debt_count': influencer_debt_count,
            'team_debts': team_debts,

            # ===== آمار روزانه/هفتگی/ماهانه =====
            'today_commission': today_commission,
            'week_commission': week_commission,
            'month_commission': month_commission,

            # ===== داده‌های نمودارها =====
            'chart_daily_labels': chart_daily_labels,
            'chart_daily_income': chart_daily_income,
            'chart_daily_commission': chart_daily_commission,
            'revenue_breakdown': revenue_breakdown,

            # ===== تراکنش‌های اخیر =====
            'recent_transactions': recent_transactions,
            'total_transactions': total_transactions,
            'failed_transactions': failed_transactions,
            'success_rate': success_rate,

            # ===== اطلاعات تقویم =====
            'jalali_date': jalali_date_str,
            'jalali_weekday': jalali_weekday,
        })

        return context


class DashboardView(SupportRequiredMixin, TemplateView):
    template_name = 'support/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ===== آمار کلی =====
        total_users = User.objects.count()
        total_advertisers = User.objects.filter(advertiser_profile__isnull=False).count()
        total_influencers = User.objects.filter(influencer_profile__isnull=False).count()
        total_teams = ContentTeam.objects.count()

        # ===== آمار کمپین‌ها =====
        total_campaigns = Campaign.objects.count()
        pending_campaigns = Campaign.objects.filter(status='pending').count()
        running_campaigns = Campaign.objects.filter(status='running').count()
        completed_campaigns = Campaign.objects.filter(status='completed').count()

        # ===== آمار کانال‌ها =====
        total_channels = Channel.objects.count()
        pending_channels = Channel.objects.filter(status='pending').count()
        approved_channels = Channel.objects.filter(status='approved').count()

        # ===== آمار سفارشات =====
        total_orders = ContentOrder.objects.count()
        pending_orders = ContentOrder.objects.filter(status='pending').count()
        in_progress_orders = ContentOrder.objects.filter(status='in_progress').count()
        completed_orders = ContentOrder.objects.filter(status='completed').count()

        # ===== آمار تیکت‌ها =====
        total_tickets = Ticket.objects.count()
        open_tickets = Ticket.objects.exclude(status='close').count()
        waiting_tickets = Ticket.objects.filter(status='waiting_admin').count()
        closed_tickets = Ticket.objects.filter(status='closed').count()

        # ===== آمار نوتیفیکیشن‌ها =====
        total_notifications = Notification.objects.count()
        unread_notifications = Notification.objects.filter(is_read=False).count()

        # ===== آمار مالی =====
        total_revenue = Transaction.objects.filter(
            status='success',
            type__in=['influencer_payment', 'team_payment']
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_deposits = Transaction.objects.filter(
            status='success',
            type='deposit'
        ).aggregate(total=Sum('amount'))['total'] or 0

        # ===== آمار ۷ روز اخیر =====
        week_ago = timezone.now() - timedelta(days=7)
        new_users_week = User.objects.filter(date_joined__gte=week_ago).count()
        new_campaigns_week = Campaign.objects.filter(created_at__gte=week_ago).count()
        new_orders_week = ContentOrder.objects.filter(created_at__gte=week_ago).count()
        new_tickets_week = Ticket.objects.filter(created_at__gte=week_ago).count()

        # ===== آمار روزانه برای چارت =====
        weekdays_fa = {
            0: 'شنبه',
            1: 'یکشنبه',
            2: 'دوشنبه',
            3: 'سه‌شنبه',
            4: 'چهارشنبه',
            5: 'پنجشنبه',
            6: 'جمعه',
        }

        chart_labels = []
        chart_users = []
        chart_campaigns = []
        chart_orders = []
        chart_tickets = []

        for i in range(6, -1, -1):
            day = timezone.now() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

            jalali_date = jdatetime.date.fromgregorian(date=day.date())
            weekday_fa = weekdays_fa.get(jalali_date.weekday(), '')
            chart_labels.append(weekday_fa)

            chart_users.append(User.objects.filter(date_joined__range=(day_start, day_end)).count())
            chart_campaigns.append(Campaign.objects.filter(created_at__range=(day_start, day_end)).count())
            chart_orders.append(ContentOrder.objects.filter(created_at__range=(day_start, day_end)).count())
            chart_tickets.append(Ticket.objects.filter(created_at__range=(day_start, day_end)).count())

        # ===== آیتم‌های نیازمند اقدام (Pending Actions) =====
        pending_actions = []

        # کمپین‌های در انتظار تایید
        pending_campaigns_list = Campaign.objects.filter(status='pending').select_related('advertiser').order_by(
            '-created_at')[:5]
        for campaign in pending_campaigns_list:
            pending_actions.append({
                'type': 'campaign',
                'id': campaign.id,
                'title': campaign.name,
                'subtitle': f'تبلیغ دهنده: {campaign.advertiser.business_name}',
                'icon': 'fi-flag',
                'color': '#fd5631',
                'url': 'support:campaign_detail',
                'action_url': 'support:campaign_approve',
                'action_label': 'تایید',
                'action_color': 'success',
                'created_at': campaign.created_at,
            })

        # کانال‌های در انتظار تایید
        pending_channels_list = Channel.objects.filter(status='pending').select_related(
            'influencer').order_by('-created_at')[:5]
        for channel in pending_channels_list:
            pending_actions.append({
                'type': 'channel',
                'id': channel.id,
                'title': channel.channel_name,
                'subtitle': f'اینفلوئنسر: {channel.influencer.user.nickname or channel.influencer.user.phone_number}',
                'icon': 'fi-device-desktop',
                'color': '#3c76f2',
                'url': 'support:channel_detail',
                'action_url': 'support:channel_approve',
                'action_label': 'تایید',
                'action_color': 'success',
                'created_at': channel.created_at,
            })

        # گزارشات در انتظار تایید
        pending_reports = CampaignReport.objects.filter(status='pending').select_related(
            'campaign_influencer__campaign',
            'campaign_influencer__channel__influencer'
        ).order_by('-created_at')[:5]
        for report in pending_reports:
            pending_actions.append({
                'type': 'report',
                'id': report.id,
                'title': f'گزارش {report.campaign_influencer.campaign.name}',
                'subtitle': f'اینفلوئنسر: {report.campaign_influencer.channel.influencer.user.nickname or report.campaign_influencer.channel.influencer.user.phone_number}',
                'icon': 'fi-file-clean',
                'color': '#fdbc31',
                'url': 'support:report_detail',
                'action_url': 'support:report_approve',
                'action_label': 'بررسی',
                'action_color': 'primary',
                'created_at': report.created_at,
            })

        # تیکت‌های باز
        open_tickets_list = Ticket.objects.filter(status='open').select_related('user').order_by('-created_at')[:5]
        for ticket in open_tickets_list:
            pending_actions.append({
                'type': 'ticket',
                'id': ticket.id,
                'title': ticket.get_display_title(),
                'subtitle': f'کاربر: {ticket.user.phone_number}',
                'icon': 'fi-chat-right',
                'color': '#07c98b',
                'url': 'support:ticket_detail',
                'action_url': None,
                'action_label': 'پاسخ',
                'action_color': 'primary',
                'created_at': ticket.created_at,
            })

        # مرتب‌سازی بر اساس زمان ایجاد (جدیدترین اول)
        pending_actions.sort(key=lambda x: x['created_at'], reverse=True)
        pending_actions = pending_actions[:10]  # فقط ۱۰ مورد آخر

        # ===== آخرین فعالیت‌ها =====
        recent_campaigns = Campaign.objects.select_related('advertiser').order_by('-created_at')[:5]
        recent_orders = ContentOrder.objects.select_related('campaign', 'team').order_by('-created_at')[:5]
        recent_tickets = Ticket.objects.select_related('user').order_by('-created_at')[:5]
        recent_users = User.objects.order_by('-date_joined')[:5]

        # ===== وضعیت امروز =====
        today = timezone.now().date()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        today_end = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))

        today_users = User.objects.filter(date_joined__range=(today_start, today_end)).count()
        today_campaigns = Campaign.objects.filter(created_at__range=(today_start, today_end)).count()
        today_orders = ContentOrder.objects.filter(created_at__range=(today_start, today_end)).count()
        today_tickets = Ticket.objects.filter(created_at__range=(today_start, today_end)).count()

        # ===== اطلاعات تقویم شمسی =====
        today_jalali = jdatetime.date.today()
        jalali_date_str = f"{today_jalali.day} {['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'][today_jalali.month - 1]} {today_jalali.year}"
        jalali_weekday = weekdays_fa.get(today_jalali.weekday(), '')

        context.update({
            # آمار کلی
            'total_users': total_users,
            'total_advertisers': total_advertisers,
            'total_influencers': total_influencers,
            'total_teams': total_teams,

            # آمار کمپین‌ها
            'total_campaigns': total_campaigns,
            'pending_campaigns': pending_campaigns,
            'running_campaigns': running_campaigns,
            'completed_campaigns': completed_campaigns,

            # آمار کانال‌ها
            'total_channels': total_channels,
            'pending_channels': pending_channels,
            'approved_channels': approved_channels,

            # آمار سفارشات
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'in_progress_orders': in_progress_orders,
            'completed_orders': completed_orders,

            # آمار تیکت‌ها
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'waiting_tickets': waiting_tickets,
            'closed_tickets': closed_tickets,

            # آمار نوتیفیکیشن‌ها
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,

            # آمار مالی
            'total_revenue': total_revenue,
            'total_deposits': total_deposits,

            # آمار ۷ روز اخیر
            'new_users_week': new_users_week,
            'new_campaigns_week': new_campaigns_week,
            'new_orders_week': new_orders_week,
            'new_tickets_week': new_tickets_week,

            # دیتاهای چارت
            'chart_labels': chart_labels,
            'chart_users': chart_users,
            'chart_campaigns': chart_campaigns,
            'chart_orders': chart_orders,
            'chart_tickets': chart_tickets,

            # آیتم‌های نیازمند اقدام
            'pending_actions': pending_actions,
            'pending_count': len(pending_actions),

            # آخرین فعالیت‌ها
            'recent_campaigns': recent_campaigns,
            'recent_orders': recent_orders,
            'recent_tickets': recent_tickets,
            'recent_users': recent_users,

            # وضعیت امروز
            'today_users': today_users,
            'today_campaigns': today_campaigns,
            'today_orders': today_orders,
            'today_tickets': today_tickets,

            # اطلاعات تقویم شمسی
            'jalali_date': jalali_date_str,
            'jalali_weekday': jalali_weekday,
        })

        return context
