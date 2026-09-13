"""
داشبوردهای پنل Support

- FinanceDashboardView: فقط CEO و Developer
- DashboardView: همه نقش‌ها (با فیلتر Regional Manager)
"""

from django.contrib.auth import get_user_model
from django.db.models import Avg, Sum, Q
from django.utils import timezone
from django.views.generic import TemplateView
from datetime import timedelta
import jdatetime

from ..mixins import TopManagerRequiredMixin, BaseSupportMixin
from payment.models import Transaction, Wallet, Invoice, Payment, CommissionSplit
from content_team.models import ContentOrder, ContentTeam
from influencers.models import ChannelBooking, Channel
from campaigns.models import Campaign, CampaignReport
from notifications.models import Notification
from tickets.models import Ticket

User = get_user_model()


# ============================================================
#                            داشبورد مالی
# ============================================================
class FinanceDashboardView(TopManagerRequiredMixin, TemplateView):
    """
    داشبورد مالی و مدیریت هزینه‌ها

    دسترسی: فقط مدیرعامل و توسعه‌دهنده
    """
    template_name = 'support/finance/dashboard.html'

    # ==================== توابع کمکی ====================

    @staticmethod
    def _get_current_jalali_month_range():
        today_j = jdatetime.date.today()

        start_jalali = jdatetime.date(today_j.year, today_j.month, 1)
        if today_j.month == 12:
            next_month_first = jdatetime.date(today_j.year + 1, 1, 1)
        else:
            next_month_first = jdatetime.date(today_j.year, today_j.month + 1, 1)
        end_jalali = next_month_first - timedelta(days=1)

        start_gregorian = start_jalali.togregorian()
        end_gregorian = end_jalali.togregorian()

        start_dt = timezone.make_aware(
            timezone.datetime.combine(start_gregorian, timezone.datetime.min.time())
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(end_gregorian, timezone.datetime.max.time())
        )

        months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
        month_name = months[today_j.month - 1]

        return {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'start_jalali': start_jalali,
            'end_jalali': end_jalali,
            'today_jalali': today_j,
            'month_name': month_name,
            'year': today_j.year,
            'month': today_j.month,
        }

    @staticmethod
    def _get_n_months_ago_jalali(n):
        today_j = jdatetime.date.today()

        target_month = today_j.month - n
        target_year = today_j.year

        while target_month <= 0:
            target_month += 12
            target_year -= 1

        start_jalali = jdatetime.date(target_year, target_month, 1)
        if target_month == 12:
            next_month_first = jdatetime.date(target_year + 1, 1, 1)
        else:
            next_month_first = jdatetime.date(target_year, target_month + 1, 1)
        end_jalali = next_month_first - timedelta(days=1)

        start_gregorian = start_jalali.togregorian()
        end_gregorian = end_jalali.togregorian()

        start_dt = timezone.make_aware(
            timezone.datetime.combine(start_gregorian, timezone.datetime.min.time())
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(end_gregorian, timezone.datetime.max.time())
        )

        months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']

        return {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'month_name': months[target_month - 1],
            'year': target_year,
            'month': target_month,
            'jalali_date': start_jalali,
        }

    @staticmethod
    def _calculate_input_amount(invoices_qs):
        """
        محاسبه ورودی کل (فقط فاکتورهایی که از درگاه پرداخت شدن)

        فاکتورهایی که با کیف پول پرداخت شدن، ورودی جدید نیستن
        """
        gateway_invoice_ids = Payment.objects.filter(
            invoice__in=invoices_qs,
            payment_method=Payment.Method.GATEWAY,
            status=Payment.Status.SUCCESS,
        ).values_list('invoice_id', flat=True).distinct()

        result = invoices_qs.filter(
            id__in=gateway_invoice_ids
        ).aggregate(total=Sum('payable_amount'))['total'] or 0

        return result

    @staticmethod
    def _aggregate_month_data(month_info):
        """
        جمع‌آوری داده‌های یک ماه شمسی

        - ورودی کل: فقط فاکتورهای gateway
        - درآمد کل: همه فاکتورها به‌جز type=wallet
        - سود: Sum(commission) از فاکتورهای درآمدی
        - مالیات: Sum(total_vat)
        - سهم نقش‌ها: از CommissionSplit
        """
        start_dt = month_info['start_dt']
        end_dt = month_info['end_dt']

        # همه فاکتورهای پرداخت‌شده در این بازه
        all_paid_invoices = Invoice.objects.filter(
            is_paid=True,
            paid_at__range=(start_dt, end_dt)
        )

        # 🔑 درآمد = به‌جز فاکتورهای wallet
        income_invoices = all_paid_invoices.exclude(type=Invoice.Type.WALLET)

        income_agg = income_invoices.aggregate(
            influencer=Sum('influencer_cost'),
            content=Sum('content_cost'),
            commission=Sum('commission'),
            vat=Sum('total_vat'),
            payable=Sum('payable_amount'),
        )

        influencer = income_agg['influencer'] or 0
        content = income_agg['content'] or 0
        commission = income_agg['commission'] or 0
        total_vat = income_agg['vat'] or 0
        gross_income = income_agg['payable'] or 0

        # 🔑 ورودی کل = فقط gateway
        input_amount = FinanceDashboardView._calculate_input_amount(all_paid_invoices)

        # تراکنش‌ها (فقط برای شمارش)
        transactions = Transaction.objects.filter(
            status='success',
            created_at__range=(start_dt, end_dt)
        )
        tx_count = transactions.count()

        # 🔑 تسهیم‌های این ماه — از CommissionSplit
        splits = CommissionSplit.objects.filter(
            invoice__in=income_invoices
        )

        split_agg = splits.aggregate(
            ceo=Sum('ceo_amount'),
            developer=Sum('developer_amount'),
            publish=Sum('publish_manager_amount'),
            content_mgr=Sum('content_manager_amount'),
            regional=Sum('regional_manager_amount'),
            site=Sum('site_maintenance_amount'),
        )

        ceo_amount = split_agg['ceo'] or 0
        developer_amount = split_agg['developer'] or 0
        publish_manager_amount = split_agg['publish'] or 0
        content_manager_amount = split_agg['content_mgr'] or 0
        regional_manager_amount = split_agg['regional'] or 0
        site_maintenance = split_agg['site'] or 0

        commission_paid_to_roles = (
                ceo_amount + developer_amount +
                publish_manager_amount + content_manager_amount +
                regional_manager_amount
        )

        # تفکیک کمیسیون هر نقش
        role_breakdown = {
            'commission_ceo': {'label': 'مدیرعامل', 'amount': ceo_amount},
            'commission_developer': {'label': 'توسعه‌دهنده', 'amount': developer_amount},
            'commission_publish_manager': {'label': 'مدیر نشر', 'amount': publish_manager_amount},
            'commission_content_manager': {'label': 'مدیر محتوا', 'amount': content_manager_amount},
            'commission_regional_manager': {'label': 'مدیر استانی', 'amount': regional_manager_amount},
            'site_maintenance': {'label': 'هزینه نگهداری سایت', 'amount': site_maintenance},
        }

        return {
            'month_name': month_info['month_name'],
            'year': month_info['year'],
            'month': month_info['month'],
            'input_amount': input_amount,
            'influencer_cost': influencer,
            'content_cost': content,
            'commission': commission,
            'total_vat': total_vat,
            'payable': gross_income,
            'gross_income': gross_income,
            'commission_total': commission,
            'commission_paid_to_roles': commission_paid_to_roles,
            'site_maintenance': site_maintenance,
            'invoices_count': income_invoices.count(),
            'transactions_count': tx_count,
            'role_breakdown': role_breakdown,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ============================================================ #
        #                    ۱. بازه ماه‌ها                            #
        # ============================================================ #
        current_month = self._get_current_jalali_month_range()
        prev_month_1 = self._get_n_months_ago_jalali(1)
        prev_month_2 = self._get_n_months_ago_jalali(2)

        # ============================================================ #
        #                    ۲. آمار کلی (کل دوره)                    #
        # ============================================================ #
        all_paid_invoices = Invoice.objects.filter(is_paid=True)
        income_invoices = all_paid_invoices.exclude(type=Invoice.Type.WALLET)

        total_agg = income_invoices.aggregate(
            influencer=Sum('influencer_cost'),
            content=Sum('content_cost'),
            commission=Sum('commission'),
            vat=Sum('total_vat'),
            payable=Sum('payable_amount'),
        )

        total_influencer_cost = total_agg['influencer'] or 0
        total_content_cost = total_agg['content'] or 0
        total_commission = total_agg['commission'] or 0
        total_vat = total_agg['vat'] or 0
        total_gross_income = total_agg['payable'] or 0

        # 🔑 ورودی کل (فقط gateway)
        total_input_amount = self._calculate_input_amount(all_paid_invoices)

        paid_invoices_count = income_invoices.count()

        # 🔑 کیف پول کاربران (پول مردم)
        total_wallet_balance = Wallet.objects.aggregate(
            total=Sum('balance')
        )['total'] or 0

        users_with_wallet = Wallet.objects.filter(balance__gt=0).count()

        # ============================================================ #
        #                    ۳. آمار ماه‌ها                            #
        # ============================================================ #
        current_month_data = self._aggregate_month_data(current_month)
        prev_month_1_data = self._aggregate_month_data(prev_month_1)
        prev_month_2_data = self._aggregate_month_data(prev_month_2)

        # ============================================================ #
        #                    ۴. تراکنش‌ها                              #
        # ============================================================ #
        successful_transactions = Transaction.objects.filter(status='success')
        total_volume = successful_transactions.aggregate(
            total=Sum('amount')
        )['total'] or 0

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
        avg_campaign_cost = income_invoices.aggregate(
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

        # 🔑 بدهی به تیم محتوا
        team_debts = ContentOrder.objects.filter(
            status__in=['review_pending', 'in_progress', 'done']
        ).aggregate(total=Sum('price'))['total'] or 0

        # ============================================================ #
        #                    ۷. آمار زمانی                             #
        # ============================================================ #
        today = timezone.now().date()
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        today_end = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.max.time())
        )

        today_commission = income_invoices.filter(
            paid_at__range=(today_start, today_end)
        ).aggregate(total=Sum('commission'))['total'] or 0

        week_ago = timezone.now() - timedelta(days=7)
        week_commission = income_invoices.filter(
            paid_at__gte=week_ago
        ).aggregate(total=Sum('commission'))['total'] or 0

        month_ago = timezone.now() - timedelta(days=30)
        month_commission = income_invoices.filter(
            paid_at__gte=month_ago
        ).aggregate(total=Sum('commission'))['total'] or 0

        # ============================================================ #
        #                    ۸. داده‌های نمودارها                      #
        # ============================================================ #
        weekdays_fa = {
            0: 'شنبه', 1: 'یکشنبه', 2: 'دوشنبه',
            3: 'سه‌شنبه', 4: 'چهارشنبه', 5: 'پنجشنبه', 6: 'جمعه'
        }

        # Pie سهم‌بندی درآمد (۴ بخش)
        revenue_breakdown = {
            'labels': [
                'هزینه ناشران',
                'هزینه تولید محتوا',
                'کمیسیون سامانه',
                'مالیات ارزش افزوده',
            ],
            'data': [
                total_influencer_cost,
                total_content_cost,
                total_commission,
                total_vat,
            ]
        }

        # نمودار روزانه ماه جاری
        current_month_daily_labels = []
        current_month_daily_income = []
        current_month_daily_commission = []

        today_j = current_month['today_jalali']
        current_day = today_j.day

        for day_num in range(1, current_day + 1):
            try:
                day_jalali = jdatetime.date(today_j.year, today_j.month, day_num)
                day_gregorian = day_jalali.togregorian()
            except ValueError:
                break

            day_start = timezone.make_aware(
                timezone.datetime.combine(day_gregorian, timezone.datetime.min.time())
            )
            day_end = timezone.make_aware(
                timezone.datetime.combine(day_gregorian, timezone.datetime.max.time())
            )

            day_agg = income_invoices.filter(
                paid_at__range=(day_start, day_end)
            ).aggregate(
                payable=Sum('payable_amount'),
                commission=Sum('commission'),
            )

            current_month_daily_labels.append(str(day_num))
            current_month_daily_income.append(day_agg['payable'] or 0)
            current_month_daily_commission.append(day_agg['commission'] or 0)

        # مقایسه ۳ ماه
        compare_months_labels = [
            prev_month_2_data['month_name'],
            prev_month_1_data['month_name'],
            current_month_data['month_name'],
        ]

        compare_months_income = [
            prev_month_2_data['gross_income'],
            prev_month_1_data['gross_income'],
            current_month_data['gross_income'],
        ]

        compare_months_commission = [
            prev_month_2_data['commission'],
            prev_month_1_data['commission'],
            current_month_data['commission'],
        ]

        # ============================================================ #
        #  🔑 درآمد نقش‌ها (کل) — از CommissionSplit (نه Transaction)
        # ============================================================ #
        all_splits = CommissionSplit.objects.all()

        split_total_agg = all_splits.aggregate(
            ceo=Sum('ceo_amount'),
            developer=Sum('developer_amount'),
            publish=Sum('publish_manager_amount'),
            content_mgr=Sum('content_manager_amount'),
            regional=Sum('regional_manager_amount'),
            site=Sum('site_maintenance_amount'),
        )

        role_breakdown_total = {
            'commission_ceo': {
                'label': 'مدیرعامل',
                'amount': split_total_agg['ceo'] or 0,
            },
            'commission_developer': {
                'label': 'توسعه‌دهنده',
                'amount': split_total_agg['developer'] or 0,
            },
            'commission_publish_manager': {
                'label': 'مدیر نشر',
                'amount': split_total_agg['publish'] or 0,
            },
            'commission_content_manager': {
                'label': 'مدیر محتوا',
                'amount': split_total_agg['content_mgr'] or 0,
            },
            'commission_regional_manager': {
                'label': 'مدیر استانی',
                'amount': split_total_agg['regional'] or 0,
            },
            'site_maintenance': {
                'label': 'هزینه نگهداری سایت',
                'amount': split_total_agg['site'] or 0,
            },
        }

        role_breakdown_merged = {}
        for role_key in role_breakdown_total.keys():
            if role_key == 'site_maintenance':
                amount_month = current_month_data.get('site_maintenance', 0)
            else:
                amount_month = current_month_data['role_breakdown'].get(
                    role_key, {'amount': 0}
                )['amount']

            role_breakdown_merged[role_key] = {
                'label': role_breakdown_total[role_key]['label'],
                'amount_total': role_breakdown_total[role_key]['amount'],
                'amount_month': amount_month,
            }

        roles_chart_labels = [v['label'] for v in role_breakdown_total.values()]
        roles_chart_data = [v['amount'] for v in role_breakdown_total.values()]

        # تراکنش‌های ماه جاری
        current_month_transactions = Transaction.objects.filter(
            created_at__range=(current_month['start_dt'], current_month['end_dt'])
        ).select_related('user').order_by('-created_at')[:50]

        # ============================================================ #
        #                    ۹. تراکنش‌های اخیر                        #
        # ============================================================ #
        recent_transactions = Transaction.objects.select_related(
            'user', 'campaign'
        ).order_by('-created_at')[:10]

        # ============================================================ #
        #                    ۱۰. تقویم شمسی                            #
        # ============================================================ #
        today_jalali = jdatetime.date.today()
        months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
        jalali_date_str = f"{today_jalali.day} {months[today_jalali.month - 1]} {today_jalali.year}"
        jalali_weekday = weekdays_fa.get(today_jalali.weekday(), '')

        # ============================================================ #
        #                    ۱۱. آمار تکمیلی                            #
        # ============================================================ #
        total_transactions = Transaction.objects.count()
        failed_transactions = Transaction.objects.filter(status='failed').count()
        success_rate = (
            successful_transactions.count() / total_transactions * 100
            if total_transactions > 0 else 0
        )

        def calc_percent(value, total):
            if total == 0:
                return 0
            return round((value / total) * 100, 1)

        influencer_percent = calc_percent(total_influencer_cost, total_gross_income)
        content_percent = calc_percent(total_content_cost, total_gross_income)
        commission_percent = calc_percent(total_commission, total_gross_income)
        vat_percent = calc_percent(total_vat, total_gross_income)

        # ============================================================ #
        #                    ۱۲. خروجی نهایی                            #
        # ============================================================ #
        context.update({
            # === ماه‌ها ===
            'current_month_name': current_month['month_name'],
            'current_month_year': current_month['year'],
            'prev_month_1_name': prev_month_1_data['month_name'],
            'prev_month_2_name': prev_month_2_data['month_name'],

            # === آمار کلی ===
            'total_input_amount': total_input_amount,
            'total_gross_income': total_gross_income,
            'total_commission': total_commission,
            'total_influencer_cost': total_influencer_cost,
            'total_content_cost': total_content_cost,
            'total_vat': total_vat,
            'total_wallet_balance': total_wallet_balance,
            'users_with_wallet': users_with_wallet,
            'paid_invoices_count': paid_invoices_count,

            'influencer_percent': influencer_percent,
            'content_percent': content_percent,
            'commission_percent': commission_percent,
            'vat_percent': vat_percent,

            # === آمار ماه جاری ===
            'current_month_data': current_month_data,
            'prev_month_1_data': prev_month_1_data,
            'prev_month_2_data': prev_month_2_data,

            # === تراکنش‌ها ===
            'total_volume': total_volume,
            'advertiser_deposits': advertiser_deposits,
            'gateway_income': gateway_income,
            'influencer_payments': influencer_payments,
            'team_payments': team_payments,
            'refunds': refunds,

            # === کمپین‌ها ===
            'avg_campaign_cost': avg_campaign_cost,
            'free_campaigns': free_campaigns,
            'total_campaigns': total_campaigns,

            # === بدهکاری ===
            'influencer_debts': influencer_debts,
            'influencer_debt_count': influencer_debt_count,
            'team_debts': team_debts,

            # === آمار زمانی ===
            'today_commission': today_commission,
            'week_commission': week_commission,
            'month_commission': month_commission,

            # === چارت‌ها ===
            'current_month_daily_labels': current_month_daily_labels,
            'current_month_daily_income': current_month_daily_income,
            'current_month_daily_commission': current_month_daily_commission,
            'revenue_breakdown': revenue_breakdown,

            'compare_months_labels': compare_months_labels,
            'compare_months_income': compare_months_income,
            'compare_months_commission': compare_months_commission,

            'roles_chart_labels': roles_chart_labels,
            'roles_chart_data': roles_chart_data,

            'role_breakdown_total': role_breakdown_total,
            'role_breakdown_merged': role_breakdown_merged,

            # === تراکنش‌ها ===
            'recent_transactions': recent_transactions,
            'current_month_transactions': current_month_transactions,
            'total_transactions': total_transactions,
            'failed_transactions': failed_transactions,
            'success_rate': success_rate,

            # === تقویم ===
            'jalali_date': jalali_date_str,
            'jalali_weekday': jalali_weekday,
        })

        return context


# ============================================================
#                            داشبورد اصلی
# ============================================================
class DashboardView(BaseSupportMixin, TemplateView):
    """
    داشبورد اصلی پنل Support

    دسترسی: همه نقش‌ها

    تفاوت با قبل:
    - Regional Manager فقط آمار استان خودش رو می‌بینه
    """
    template_name = 'support/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # ============================================================
        #  تشخیص نوع دسترسی (Regional یا Global)
        # ============================================================
        is_regional = user.is_regional_manager and user.province_id
        regional_province = user.province if is_regional else None

        # ============================================================
        #  ۱. آمار کاربران
        # ============================================================
        users_qs = User.objects.all()
        advertisers_qs = User.objects.filter(advertiser_profile__isnull=False)
        influencers_qs = User.objects.filter(influencer_profile__isnull=False)

        if is_regional:
            users_qs = users_qs.filter(province=regional_province)
            advertisers_qs = advertisers_qs.filter(province=regional_province)
            influencers_qs = influencers_qs.filter(province=regional_province)

        total_users = users_qs.count()
        total_advertisers = advertisers_qs.count()
        total_influencers = influencers_qs.count()

        # ============================================================
        #  ۲. آمار تیم‌های محتوا
        # ============================================================
        teams_qs = ContentTeam.objects.all()
        if is_regional:
            teams_qs = teams_qs.filter(province=regional_province)
        total_teams = teams_qs.count()

        # ============================================================
        #  ۳. آمار کمپین‌ها
        # ============================================================
        campaigns_qs = Campaign.objects.all()
        if is_regional:
            campaigns_qs = campaigns_qs.filter(
                advertiser__user__province=regional_province
            )

        total_campaigns = campaigns_qs.count()
        pending_campaigns = campaigns_qs.filter(status='pending').count()
        running_campaigns = campaigns_qs.filter(status='running').count()
        completed_campaigns = campaigns_qs.filter(status='completed').count()

        # ============================================================
        #  ۴. آمار کانال‌ها
        # ============================================================
        channels_qs = Channel.objects.all()
        if is_regional:
            channels_qs = channels_qs.filter(province=regional_province)

        total_channels = channels_qs.count()
        pending_channels = channels_qs.filter(status='pending').count()
        approved_channels = channels_qs.filter(status='approved').count()

        # ============================================================
        #  ۵. آمار سفارشات محتوا
        # ============================================================
        orders_qs = ContentOrder.objects.all()
        if is_regional:
            orders_qs = orders_qs.filter(
                Q(campaign__advertiser__user__province=regional_province) |
                Q(standalone_user__province=regional_province)
            )

        total_orders = orders_qs.count()
        pending_orders = orders_qs.filter(status='pending').count()
        in_progress_orders = orders_qs.filter(status='in_progress').count()
        completed_orders = orders_qs.filter(status='completed').count()

        # ============================================================
        #  ۶. آمار تیکت‌ها
        # ============================================================
        tickets_qs = Ticket.objects.all()
        if is_regional:
            tickets_qs = tickets_qs.filter(user__province=regional_province)

        total_tickets = tickets_qs.count()
        open_tickets = tickets_qs.exclude(status='closed').count()
        waiting_tickets = tickets_qs.filter(status='waiting_admin').count()
        closed_tickets = tickets_qs.filter(status='closed').count()

        # ============================================================
        #  ۷. آمار نوتیفیکیشن‌ها
        # ============================================================
        notifications_qs = Notification.objects.all()
        if is_regional:
            notifications_qs = notifications_qs.filter(user__province=regional_province)

        total_notifications = notifications_qs.count()
        unread_notifications = notifications_qs.filter(is_read=False).count()

        # ============================================================
        #  ۸. آمار مالی
        # ============================================================
        tx_qs = Transaction.objects.filter(
            status='success',
            type__in=['influencer_payment', 'team_payment']
        )
        deposit_qs = Transaction.objects.filter(status='success', type='deposit')

        if is_regional:
            tx_qs = tx_qs.filter(user__province=regional_province)
            deposit_qs = deposit_qs.filter(user__province=regional_province)

        total_revenue = tx_qs.aggregate(total=Sum('amount'))['total'] or 0
        total_deposits = deposit_qs.aggregate(total=Sum('amount'))['total'] or 0

        # ============================================================
        #  ۹. آمار ۷ روز اخیر
        # ============================================================
        week_ago = timezone.now() - timedelta(days=7)

        new_users_week = users_qs.filter(date_joined__gte=week_ago).count()
        new_campaigns_week = campaigns_qs.filter(created_at__gte=week_ago).count()
        new_orders_week = orders_qs.filter(created_at__gte=week_ago).count()
        new_tickets_week = tickets_qs.filter(created_at__gte=week_ago).count()

        # ============================================================
        #  ۱۰. آمار روزانه برای چارت
        # ============================================================
        weekdays_fa = {
            0: 'شنبه', 1: 'یکشنبه', 2: 'دوشنبه',
            3: 'سه‌شنبه', 4: 'چهارشنبه', 5: 'پنجشنبه', 6: 'جمعه',
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

            chart_users.append(users_qs.filter(date_joined__range=(day_start, day_end)).count())
            chart_campaigns.append(campaigns_qs.filter(created_at__range=(day_start, day_end)).count())
            chart_orders.append(orders_qs.filter(created_at__range=(day_start, day_end)).count())
            chart_tickets.append(tickets_qs.filter(created_at__range=(day_start, day_end)).count())

        # ============================================================
        #  ۱۱. آیتم‌های نیازمند اقدام
        # ============================================================
        pending_actions = []

        # کمپین‌های در انتظار تایید
        pending_campaigns_list = campaigns_qs.filter(status='pending').select_related(
            'advertiser'
        ).order_by('-created_at')[:5]
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
        pending_channels_list = channels_qs.filter(status='pending').select_related(
            'influencer'
        ).order_by('-created_at')[:5]
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
        reports_qs = CampaignReport.objects.filter(status='pending')
        if is_regional:
            reports_qs = reports_qs.filter(
                campaign_influencer__channel__province=regional_province
            )

        pending_reports = reports_qs.select_related(
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
        open_tickets_list = tickets_qs.filter(status='waiting_admin').select_related(
            'user'
        ).order_by('-created_at')[:5]
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

        # مرتب‌سازی و محدودسازی
        pending_actions.sort(key=lambda x: x['created_at'], reverse=True)
        pending_actions = pending_actions[:10]

        # ============================================================
        #  ۱۲. آخرین فعالیت‌ها
        # ============================================================
        recent_campaigns = campaigns_qs.select_related('advertiser').order_by('-created_at')[:5]
        recent_orders = orders_qs.select_related('campaign', 'team').order_by('-created_at')[:5]
        recent_tickets = tickets_qs.select_related('user').order_by('-created_at')[:5]
        recent_users = users_qs.order_by('-date_joined')[:5]

        # ============================================================
        #  ۱۳. وضعیت امروز
        # ============================================================
        today = timezone.now().date()
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        today_end = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.max.time())
        )

        today_users = users_qs.filter(date_joined__range=(today_start, today_end)).count()
        today_campaigns = campaigns_qs.filter(created_at__range=(today_start, today_end)).count()
        today_orders = orders_qs.filter(created_at__range=(today_start, today_end)).count()
        today_tickets = tickets_qs.filter(created_at__range=(today_start, today_end)).count()

        # ============================================================
        #  ۱۴. اطلاعات تقویم شمسی
        # ============================================================
        today_jalali = jdatetime.date.today()
        jalali_date_str = (
            f"{today_jalali.day} "
            f"{['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'][today_jalali.month - 1]} "
            f"{today_jalali.year}"
        )
        jalali_weekday = weekdays_fa.get(today_jalali.weekday(), '')


        # ============================================================
        #  ۱۶. دسترسی‌های داشبورد (بر اساس نقش)
        # ============================================================
        dash_perms = {
            # مالی: فقط CEO و Dev
            'can_see_finance': user.is_top_manager,

            # کمپین‌ها: CEO + Dev + Publish Manager + Regional
            'can_see_campaigns': (
                user.is_top_manager or
                user.is_publish_manager or
                user.is_regional_manager
            ),

            # کانال‌ها: CEO + Dev + Publish Manager + Regional
            'can_see_channels': (
                user.is_top_manager or
                user.is_publish_manager or
                user.is_regional_manager
            ),

            # سفارشات محتوا: CEO + Dev + Content Manager + Regional
            'can_see_content': (
                user.is_top_manager or
                user.is_content_manager or
                user.is_regional_manager
            ),

            # تیم‌ها: CEO + Dev + Content Manager + Regional
            'can_see_teams': (
                user.is_top_manager or
                user.is_content_manager or
                user.is_regional_manager
            ),

            # کاربران، تیکت‌ها، اعلان‌ها: همه
            'can_see_users': True,
            'can_see_tickets': True,
            'can_see_notifications': True,

            # درآمد کل: فقط CEO و Dev
            'can_see_total_revenue': user.is_top_manager,

            # برچسب دامنه دسترسی
            'scope_label': (
                f'استان {user.province.name}'
                if is_regional else 'کل پلتفرم'
            ),

            # آیا کاربر محدود به استان خودشه؟
            'is_regional_scope': is_regional,
        }

        # ============================================================
        #  ۱۷. محاسبه تعداد کارت‌های اصلی (برای layout داینامیک)
        # ============================================================
        main_cards_count = 0
        if dash_perms['can_see_users']:
            main_cards_count += 1
        if dash_perms['can_see_campaigns']:
            main_cards_count += 1
        if dash_perms['can_see_content']:
            main_cards_count += 1
        if dash_perms['can_see_total_revenue'] or dash_perms['can_see_channels']:
            main_cards_count += 1

        # کلاس عرض ستون بر اساس تعداد
        # (اعداد Tailwind-like برای Bootstrap 5)
        main_col_class_map = {
            1: 'col-12',
            2: 'col-12 col-md-6',
            3: 'col-12 col-md-6 col-xl-4',
            4: 'col-12 col-sm-6 col-xl-3',
        }
        main_col_class = main_col_class_map.get(main_cards_count, 'col-12 col-sm-6 col-xl-3')

        dash_perms['main_cards_count'] = main_cards_count
        dash_perms['main_col_class'] = main_col_class

        # ============================================================
        #  ۱۵. خروجی نهایی
        # ============================================================
        context.update({
            # وضعیت دسترسی
            'is_regional_manager_view': is_regional,
            'regional_province': regional_province,
            'dash_perms': dash_perms,

            # آمار کلی
            'total_users': total_users,
            'total_advertisers': total_advertisers,
            'total_influencers': total_influencers,
            'total_teams': total_teams,

            # کمپین‌ها
            'total_campaigns': total_campaigns,
            'pending_campaigns': pending_campaigns,
            'running_campaigns': running_campaigns,
            'completed_campaigns': completed_campaigns,

            # کانال‌ها
            'total_channels': total_channels,
            'pending_channels': pending_channels,
            'approved_channels': approved_channels,

            # سفارشات
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'in_progress_orders': in_progress_orders,
            'completed_orders': completed_orders,

            # تیکت‌ها
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'waiting_tickets': waiting_tickets,
            'closed_tickets': closed_tickets,

            # نوتیفیکیشن‌ها
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,

            # مالی
            'total_revenue': total_revenue,
            'total_deposits': total_deposits,

            # ۷ روز اخیر
            'new_users_week': new_users_week,
            'new_campaigns_week': new_campaigns_week,
            'new_orders_week': new_orders_week,
            'new_tickets_week': new_tickets_week,

            # چارت‌ها
            'chart_labels': chart_labels,
            'chart_users': chart_users,
            'chart_campaigns': chart_campaigns,
            'chart_orders': chart_orders,
            'chart_tickets': chart_tickets,

            # اقدامات
            'pending_actions': pending_actions,
            'pending_count': len(pending_actions),

            # آخرین فعالیت‌ها
            'recent_campaigns': recent_campaigns,
            'recent_orders': recent_orders,
            'recent_tickets': recent_tickets,
            'recent_users': recent_users,

            # امروز
            'today_users': today_users,
            'today_campaigns': today_campaigns,
            'today_orders': today_orders,
            'today_tickets': today_tickets,

            # تقویم
            'jalali_date': jalali_date_str,
            'jalali_weekday': jalali_weekday,
        })

        return context
