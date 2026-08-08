"""
سرویس محاسبه مالیات بر ارزش افزوده برای کمپین‌ها
"""

from typing import Dict, Optional
from campaigns.models import Campaign
from influencers.models import ChannelBooking
from content_team.models import ContentOrder
from django.db import models


class CampaignTaxCalculator:
    """
    کلاس محاسبه مالیات کمپین در حالت‌های مختلف
    """

    VAT_PERCENT = 0.10  # 10 درصد
    PLATFORM_COMMISSION = 0.15  # 15 درصد

    def __init__(self, campaign: Campaign):
        self.campaign = campaign

    def get_current_tax_data(self) -> Dict:
        """
        دریافت داده‌های مالیاتی فعلی کمپین (قبل از تغییرات)
        """
        if hasattr(self.campaign, 'invoice') and self.campaign.invoice:
            invoice = self.campaign.invoice
            return {
                'influencer_cost': int(invoice.influencer_cost),
                'content_cost': int(invoice.content_cost),
                'commission': int(invoice.commission),
                'influencer_vat': int(invoice.influencer_vat),
                'content_vat': int(invoice.content_vat),
                'commission_vat': int(invoice.commission_vat),
                'total_vat': int(invoice.total_vat),
                'total_amount': int(invoice.total_amount),
                'payable_amount': int(invoice.payable_amount),
            }
        else:
            # اگر فاکتور وجود نداشت، از داده‌های موجود محاسبه کن
            influencer_cost = self._calculate_current_influencer_cost()
            content_cost = self._calculate_current_content_cost()

            # ✅ تبدیل به int برای جلوگیری از خطا
            influencer_cost = int(influencer_cost)
            content_cost = int(content_cost)

            commission = int((influencer_cost + content_cost) * self.PLATFORM_COMMISSION)

            influencer_vat = int(influencer_cost * self.VAT_PERCENT)
            content_vat = int(content_cost * self.VAT_PERCENT)
            commission_vat = int(commission * self.VAT_PERCENT)
            total_vat = influencer_vat + content_vat + commission_vat
            total_amount = influencer_cost + content_cost + commission
            payable_amount = total_amount + total_vat

            return {
                'influencer_cost': influencer_cost,
                'content_cost': content_cost,
                'commission': commission,
                'influencer_vat': influencer_vat,
                'content_vat': content_vat,
                'commission_vat': commission_vat,
                'total_vat': total_vat,
                'total_amount': total_amount,
                'payable_amount': payable_amount,
            }

    def _calculate_current_influencer_cost(self) -> int:
        """محاسبه هزینه فعلی ناشران (با احتساب فقط کانال‌های فعال)"""
        total = self.campaign.influencer_bookings.exclude(
            status__in=[
                ChannelBooking.Status.REJECTED,
                ChannelBooking.Status.REPLACED
            ]
        ).aggregate(total=models.Sum('price'))['total'] or 0
        return int(total)

    def _calculate_current_content_cost(self) -> int:
        """محاسبه هزینه فعلی تولید محتوا"""
        total = self.campaign.content_orders.exclude(
            status=ContentOrder.Status.CANCELLED
        ).aggregate(total=models.Sum('price'))['total'] or 0
        return int(total)

    def calculate_new_tax_data(
            self,
            new_influencer_cost: int = 0,
            new_content_cost: Optional[int] = None,
            new_commission: Optional[int] = None,
            keep_commission_constant: bool = False  # ✅ پارامتر جدید
    ) -> Dict:
        """
        محاسبه داده‌های مالیاتی جدید بر اساس هزینه‌های جدید

        Args:
            new_influencer_cost: هزینه جدید ناشران
            new_content_cost: هزینه جدید تولید محتوا
            new_commission: کمیسیون جدید (اگر null باشه خودش محاسبه می‌کنه)
            keep_commission_constant: آیا کمیسیون باید ثابت بمونه؟ (برای حالت جایگزینی)
        """
        current = self.get_current_tax_data()

        new_influencer_cost = int(new_influencer_cost)

        if new_content_cost is None:
            new_content_cost = current['content_cost']
        else:
            new_content_cost = int(new_content_cost)

        # ========== محاسبه کمیسیون ==========
        if keep_commission_constant:
            # ✅ در حالت جایگزینی، کمیسیون رو ثابت نگه می‌داریم
            new_commission = current['commission']
        elif new_commission is None:
            # در حالت عادی، کمیسیون رو محاسبه می‌کنیم
            new_subtotal = new_influencer_cost + new_content_cost
            new_commission = int(new_subtotal * self.PLATFORM_COMMISSION)
        else:
            new_commission = int(new_commission)

        # محاسبه مالیات جدید
        new_influencer_vat = int(new_influencer_cost * self.VAT_PERCENT)
        new_content_vat = int(new_content_cost * self.VAT_PERCENT)
        new_commission_vat = int(new_commission * self.VAT_PERCENT)
        new_total_vat = new_influencer_vat + new_content_vat + new_commission_vat

        new_total_amount = new_influencer_cost + new_content_cost + new_commission
        new_payable_amount = new_total_amount + new_total_vat

        return {
            'influencer_cost': new_influencer_cost,
            'content_cost': new_content_cost,
            'commission': new_commission,
            'influencer_vat': new_influencer_vat,
            'content_vat': new_content_vat,
            'commission_vat': new_commission_vat,
            'total_vat': new_total_vat,
            'total_amount': new_total_amount,
            'payable_amount': new_payable_amount,
        }

    def calculate_diff(self, new_data: Dict) -> Dict:
        """
        محاسبه مابه‌التفاوت‌ها بین داده‌های فعلی و جدید

        Returns:
            Dict شامل:
            - commission_diff: مابه‌التفاوت کمیسیون (مثبت یا منفی)
            - vat_diff: مابه‌التفاوت مالیات (مثبت یا منفی)
            - commission_to_pay: مبلغ کمیسیون قابل پرداخت (فقط اگر مثبت)
            - vat_to_pay: مبلغ مالیات قابل پرداخت (مثبت یا منفی)
            - total_diff: مجموع مابه‌التفاوت‌ها
        """
        current = self.get_current_tax_data()

        # مابه‌التفاوت کمیسیون
        commission_diff = new_data['commission'] - current['commission']

        # مابه‌التفاوت مالیات
        vat_diff = new_data['total_vat'] - current['total_vat']

        # مبلغ نهایی قابل پرداخت (مثبت یعنی باید پرداخت کنه، منفی یعنی باید برگشت داده بشه)
        total_diff = commission_diff + vat_diff

        return {
            'commission_diff': commission_diff,
            'vat_diff': vat_diff,
            'commission_to_pay': max(commission_diff, 0),  # فقط اگر مثبت
            'vat_to_pay': vat_diff,  # می‌تونه منفی یا مثبت باشه
            'total_diff': total_diff,
            'old_commission': current['commission'],
            'new_commission': new_data['commission'],
            'old_vat': current['total_vat'],
            'new_vat': new_data['total_vat'],
            'old_influencer_cost': current['influencer_cost'],
            'new_influencer_cost': new_data['influencer_cost'],
            'old_content_cost': current['content_cost'],
            'new_content_cost': new_data['content_cost'],
        }

    def calculate_replacement_amount(
            self,
            new_selected_cost: int = 0,
            new_content_cost: Optional[int] = None
    ) -> Dict:
        """
        محاسبه مبلغ نهایی برای حالت جایگزینی
        """
        # دریافت داده‌های فعلی
        current = self.get_current_tax_data()
        new_selected_cost = int(new_selected_cost)

        # محاسبه هزینه جدید ناشران
        if new_content_cost is None:
            # حالت جایگزینی کانال
            new_influencer_cost = current['influencer_cost'] + new_selected_cost
            new_content_cost = current['content_cost']
            base_cost = new_selected_cost
        else:
            # حالت جایگزینی تیم محتوا
            new_content_cost = int(new_content_cost)
            new_influencer_cost = current['influencer_cost']
            base_cost = new_content_cost - current['content_cost']

        # ========== محاسبه کمیسیون جدید (با احتساب هزینه‌های جدید) ==========
        new_subtotal = new_influencer_cost + new_content_cost
        new_commission = int(new_subtotal * self.PLATFORM_COMMISSION)

        # ========== محاسبه مابه‌التفاوت کمیسیون ==========
        commission_diff = new_commission - current['commission']
        commission_to_pay = max(commission_diff, 0)  # فقط اگر مثبت باشه

        # ========== محاسبه مبلغ پایه برای مالیات جدید ==========
        # ✅ فرمول درست:
        # مالیات جدید = (هزینه ناشران قبلی + هزینه ناشران جدید + کمیسیون قبلی + max(0, کمیسیون جدید - کمیسیون قبلی)) × ۰.۱۰
        # یعنی: (current['influencer_cost'] + new_selected_cost + current['commission'] + commission_to_pay) × ۰.۱۰

        tax_base = current['influencer_cost'] + new_selected_cost + current['commission'] + commission_to_pay
        new_total_vat = int(tax_base * self.VAT_PERCENT)

        # ========== محاسبه مابه‌التفاوت مالیات ==========
        old_vat = current['total_vat']
        vat_diff = new_total_vat - old_vat

        # ========== محاسبه مبلغ نهایی قابل پرداخت ==========
        total_deduct = new_selected_cost + commission_to_pay + vat_diff

        # ساخت جزییات برای نمایش
        breakdown = self._build_breakdown(
            base_cost=new_selected_cost,
            commission_diff=commission_diff,
            vat_diff=vat_diff,
            total_deduct=total_deduct
        )

        return {
            'total_deduct': total_deduct,
            'commission_diff': commission_diff,
            'vat_diff': vat_diff,
            'base_cost': new_selected_cost,
            'is_refund': total_deduct < 0,
            'refund_amount': abs(total_deduct) if total_deduct < 0 else 0,
            'charge_amount': total_deduct if total_deduct > 0 else 0,
            'breakdown': breakdown,
            'new_data': {
                'influencer_cost': new_influencer_cost,
                'content_cost': new_content_cost,
                'commission': new_commission,
                'total_vat': new_total_vat,
            },
            'diff_data': {
                'commission_diff': commission_diff,
                'vat_diff': vat_diff,
            },
            'old_data': current,
        }

    def _build_breakdown(self, base_cost: int, commission_diff: int, vat_diff: int, total_deduct: int) -> list:
        """ساخت جزییات نمایشی"""
        breakdown = []

        # ۱. هزینه پایه
        if base_cost > 0:
            breakdown.append({
                'label': 'هزینه کانال‌های جدید',
                'amount': base_cost,
                'formatted': f"{base_cost:,}",
            })
        elif base_cost < 0:
            breakdown.append({
                'label': 'کاهش هزینه تیم محتوا',
                'amount': abs(base_cost),
                'formatted': f"-{abs(base_cost):,}",
                'is_success': True,
            })

        # ۲. مابه‌التفاوت کمیسیون (فقط اگر مثبت باشه)
        if commission_diff > 0:
            breakdown.append({
                'label': 'ما به التفاوت حق‌العمل',
                'amount': commission_diff,
                'formatted': f"+{commission_diff:,}",
                'is_warning': True,
            })
        # اگر کمیسیون منفی شد، اصلاً نمایش نمی‌دیم

        # ۳. مابه‌التفاوت مالیات
        if vat_diff > 0:
            breakdown.append({
                'label': 'ما به التفاوت مالیات (افزایش)',
                'amount': vat_diff,
                'formatted': f"+{vat_diff:,}",
                'is_warning': True,
            })
        elif vat_diff < 0:
            breakdown.append({
                'label': 'کاهش مالیات (کمک هزینه)',
                'amount': abs(vat_diff),
                'formatted': f"-{abs(vat_diff):,}",
                'is_success': True,
            })

        # ۴. مبلغ نهایی
        breakdown.append({
            'label': 'مبلغ قابل پرداخت',
            'amount': total_deduct,
            'formatted': f"{total_deduct:,}",
            'is_total': True,
            'is_highlight': True,
        })

        return breakdown


# تابع کمکی برای راحتی کار
def calculate_replacement_tax(
    campaign: Campaign,
    new_selected_cost: int = 0,
    new_content_cost: Optional[int] = None
) -> Dict:
    """
    تابع کمکی برای محاسبه مالیات در حالت جایگزینی

    Args:
        campaign: کمپین مورد نظر
        new_selected_cost: هزینه کانال‌های جدید انتخاب شده (برای جایگزینی کانال)
        new_content_cost: هزینه جدید تیم محتوا (برای جایگزینی تیم محتوا)
    """
    calculator = CampaignTaxCalculator(campaign)
    return calculator.calculate_replacement_amount(
        new_selected_cost=new_selected_cost,
        new_content_cost=new_content_cost
    )