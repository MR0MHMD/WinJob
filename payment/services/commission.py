"""
سرویس محاسبه تقسیم کمیسیون

این ماژول منطق تقسیم کمیسیون بین:
- مدیرعامل
- توسعه‌دهنده
- مدیر نشر
- مدیر تولید محتوا
- مدیر استانی
- هزینه نگهداری سایت

را پیاده‌سازی می‌کند.

استفاده:
    from payment.services.commission import calculate_commission_breakdown

    breakdown = calculate_commission_breakdown(
        source_id=campaign.id,
        source_type='campaign',
    )

    print(breakdown.ceo_amount)  # 360
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

from payment.constants import COMMISSION_SETTINGS
from payment.models import Invoice

# ==================== Enums & Constants ====================

CampaignType = Literal['publish_only', 'content_only', 'mixed']
SourceType = Literal['campaign', 'content_order']


# ==================== Data Classes ====================

@dataclass
class CommissionBreakdown:
    """
    نتیجه محاسبه تقسیم کمیسیون
    """
    # اطلاعات پایه
    total_commission: int
    campaign_type: CampaignType
    advertiser_province_id: Optional[int]

    # سهم‌ها (به تومان)
    ceo_amount: int = 0
    developer_amount: int = 0
    publish_manager_amount: int = 0
    content_manager_amount: int = 0
    regional_manager_amount: int = 0
    site_maintenance_amount: int = 0

    # اطلاعات کمکی (برای debug و نمایش)
    setting_snapshot: dict = field(default_factory=dict)

    @property
    def sum_of_shares(self) -> int:
        """جمع همه سهم‌ها (باید برابر total_commission باشه)"""
        return (
                self.ceo_amount
                + self.developer_amount
                + self.publish_manager_amount
                + self.content_manager_amount
                + self.regional_manager_amount
                + self.site_maintenance_amount
        )

    @property
    def is_balanced(self) -> bool:
        """آیا جمع سهم‌ها با کل کمیسیون برابره؟"""
        return self.sum_of_shares == self.total_commission

    def __str__(self):
        return (
            f"CommissionBreakdown("
            f"type={self.campaign_type}, "
            f"total={self.total_commission}, "
            f"ceo={self.ceo_amount}, "
            f"dev={self.developer_amount}, "
            f"publish={self.publish_manager_amount}, "
            f"content={self.content_manager_amount}, "
            f"regional={self.regional_manager_amount}, "
            f"site={self.site_maintenance_amount}"
            f")"
        )


# ==================== Exceptions ====================

class CommissionCalculationError(Exception):
    """خطا در محاسبه کمیسیون"""
    pass


# ==================== Helper Functions ====================

def _get_invoice(source_id: int, source_type: SourceType) -> Invoice:
    """
    پیدا کردن فاکتور مربوط به کمپین یا سفارش محتوا
    """
    if source_type == 'campaign':
        invoice = Invoice.objects.filter(
            campaign_id=source_id,
            type=Invoice.Type.CAMPAIGN,
        ).first()
    elif source_type == 'content_order':
        invoice = Invoice.objects.filter(
            content_order_id=source_id,
            type=Invoice.Type.CONTENT_ORDER,
        ).first()
    else:
        raise CommissionCalculationError(
            f"نوع منبع نامعتبر: {source_type}"
        )

    if not invoice:
        raise CommissionCalculationError(
            f"فاکتوری برای {source_type} با ID={source_id} پیدا نشد"
        )

    if not invoice.is_paid:
        raise CommissionCalculationError(
            f"فاکتور {invoice.invoice_number} هنوز پرداخت نشده است"
        )

    return invoice


def _detect_campaign_type(
        source_id: int,
        source_type: SourceType,
) -> CampaignType:
    """
    تشخیص نوع کمپین/سفارش

    Returns:
        - 'publish_only': کمپین بدون سفارش محتوا
        - 'content_only': سفارش محتوای مستقل
        - 'mixed': کمپین + سفارش محتوا
    """
    from campaigns.models import Campaign
    from content_team.models import ContentOrder

    if source_type == 'campaign':
        campaign = Campaign.objects.filter(pk=source_id).first()
        if not campaign:
            raise CommissionCalculationError(
                f"کمپین با ID={source_id} پیدا نشد"
            )

        has_content_order = campaign.content_orders.exists()
        return 'mixed' if has_content_order else 'publish_only'

    elif source_type == 'content_order':
        order = ContentOrder.objects.filter(pk=source_id).first()
        if not order:
            raise CommissionCalculationError(
                f"سفارش محتوا با ID={source_id} پیدا نشد"
            )

        if order.campaign_id:
            raise CommissionCalculationError(
                f"سفارش {source_id} وابسته به کمپین است. "
                f"لطفاً از source_type='campaign' استفاده کنید"
            )

        return 'content_only'

    else:
        raise CommissionCalculationError(
            f"نوع منبع نامعتبر: {source_type}"
        )


def _get_advertiser_province_id(
        source_id: int,
        source_type: SourceType,
) -> Optional[int]:
    """
    گرفتن ID استان تبلیغ‌دهنده
    """
    from campaigns.models import Campaign
    from content_team.models import ContentOrder

    if source_type == 'campaign':
        campaign = Campaign.objects.select_related(
            'advertiser__user__province'
        ).filter(pk=source_id).first()

        if campaign and campaign.advertiser.user.province_id:
            return campaign.advertiser.user.province_id

    elif source_type == 'content_order':
        order = ContentOrder.objects.select_related(
            'campaign__advertiser__user__province',
            'standalone_user__province',
        ).filter(pk=source_id).first()

        if order:
            if order.is_standalone and order.standalone_user:
                return order.standalone_user.province_id
            elif order.campaign and order.campaign.advertiser.user.province_id:
                return order.campaign.advertiser.user.province_id

    return None


# ==================== Main Service Function ====================

def calculate_commission_breakdown(
        source_id: int,
        source_type: SourceType,
) -> CommissionBreakdown:
    """
    محاسبه تقسیم کمیسیون

    Args:
        source_id: ID کمپین یا سفارش محتوا
        source_type: 'campaign' یا 'content_order'

    Returns:
        CommissionBreakdown با تمام سهم‌ها

    Raises:
        CommissionCalculationError: در صورت مشکل در پیدا کردن منابع
    """
    # ===== ۱. پیدا کردن فاکتور =====
    invoice = _get_invoice(source_id, source_type)

    # ===== ۲. گرفتن مبلغ کمیسیون =====
    total_commission = int(invoice.commission)

    if total_commission <= 0:
        raise CommissionCalculationError(
            f"مبلغ کمیسیون فاکتور {invoice.invoice_number} "
            f"صفر یا منفی است ({total_commission})"
        )

    # ===== ۳. تشخیص نوع کمپین =====
    campaign_type = _detect_campaign_type(source_id, source_type)

    # ===== ۴. گرفتن استان تبلیغ‌دهنده =====
    advertiser_province_id = _get_advertiser_province_id(
        source_id, source_type
    )

    # ===== ۵. محاسبه سهم‌ها =====
    return _calculate_shares(
        total_commission=total_commission,
        campaign_type=campaign_type,
        advertiser_province_id=advertiser_province_id,
    )


def _calculate_shares(
        total_commission: int,
        campaign_type: CampaignType,
        advertiser_province_id: Optional[int],
        settings: Optional[dict] = None,
) -> CommissionBreakdown:
    """
    محاسبه داخلی سهم‌ها

    این تابع خالص است (Pure) و به DB وابسته نیست.

    Args:
        total_commission: مبلغ کل کمیسیون
        campaign_type: نوع کمپین
        advertiser_province_id: ID استان تبلیغ‌دهنده (اختیاری)
        settings: تنظیمات کمیسیون (اگه None، از constants می‌خونه)
    """
    if settings is None:
        settings = COMMISSION_SETTINGS

    # ===== ۱. سهم مدیرعامل و توسعه‌دهنده =====
    pool = settings['top_managers_pool']
    pool_for_top_managers = total_commission * pool / 100

    ceo_amount = int(
        pool_for_top_managers * settings['ceo_share_from_pool'] / 100
    )
    developer_amount = int(
        pool_for_top_managers * settings['developer_share_from_pool'] / 100
    )

    # ===== ۲. سهم مدیرها =====
    publish_manager_amount = 0
    content_manager_amount = 0

    if campaign_type == 'publish_only':
        publish_manager_amount = int(
            total_commission * settings['publish_manager_share'] / 100
        )

    elif campaign_type == 'content_only':
        content_manager_amount = int(
            total_commission * settings['content_manager_share'] / 100
        )

    elif campaign_type == 'mixed':
        publish_manager_amount = int(
            total_commission * settings['mixed_publish_manager_share'] / 100
        )
        content_manager_amount = int(
            total_commission * settings['mixed_content_manager_share'] / 100
        )

    # ===== ۳. سهم مدیر استانی =====
    regional_manager_amount = 0

    if advertiser_province_id:
        regional_manager_amount = int(
            total_commission * settings['regional_manager_share'] / 100
        )

    # ===== ۴. باقی‌مونده → هزینه نگهداری سایت =====
    allocated = (
            ceo_amount
            + developer_amount
            + publish_manager_amount
            + content_manager_amount
            + regional_manager_amount
    )

    site_maintenance_amount = total_commission - allocated

    # ===== ۵. ساخت خروجی =====
    breakdown = CommissionBreakdown(
        total_commission=total_commission,
        campaign_type=campaign_type,
        advertiser_province_id=advertiser_province_id,
        ceo_amount=ceo_amount,
        developer_amount=developer_amount,
        publish_manager_amount=publish_manager_amount,
        content_manager_amount=content_manager_amount,
        regional_manager_amount=regional_manager_amount,
        site_maintenance_amount=site_maintenance_amount,
        setting_snapshot=settings.copy(),
    )

    # ===== ۶. چک نهایی =====
    if not breakdown.is_balanced:
        raise CommissionCalculationError(
            f"خطا در محاسبه: جمع سهم‌ها ({breakdown.sum_of_shares}) "
            f"با کل کمیسیون ({total_commission}) برابر نیست"
        )

    return breakdown