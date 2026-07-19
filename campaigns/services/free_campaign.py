from influencers.models import InfluencerServiceRate
from campaigns.models import CampaignInfluencer
import uuid


def create_free_campaign_bookings(campaign):
    """
    برای کمپین رایگان، تمام کانال‌های فعال و تایید شده‌ای که برای پلتفرم و نوع تبلیغ
    کمپین نرخ فعال دارند را پیدا کرده و به عنوان CampaignInfluencer با قیمت ۰ ثبت می‌کند.
    """

    campaign.influencer_bookings.all().delete()

    rates = InfluencerServiceRate.objects.filter(
        channel__platform=campaign.platform,
        ad_type=campaign.ad_type,
        is_active=True,
        channel__is_active=True,
        channel__status='approved',
    ).select_related('channel')

    bookings = []
    for rate in rates:
        bookings.append(
            CampaignInfluencer(
                campaign=campaign,
                channel=rate.channel,
                service_rate=rate,
                price=0,
                status=CampaignInfluencer.Status.PENDING,
                tracking_code=uuid.uuid4().hex[:8]  # ← اضافه کن
            )
        )

    if bookings:
        CampaignInfluencer.objects.bulk_create(bookings)

    return len(bookings)
