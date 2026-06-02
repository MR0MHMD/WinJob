from django.db import transaction

from campaigns.models import CampaignInfluencer
from content_team.models import TeamReview, ContentOrder
from gamification.services import update_score
from influencers.models import InfluencerReview

def submit_team_review_service(order, advertiser, rating, comment=""):
    """
    سرویس ثبت نظر تبلیغ‌دهنده برای تیم تولید محتوا
    فقط در صورتی که سفارش واقعی و تکمیل شده باشد امتیاز تعلق می‌گیرد.
    """
    with transaction.atomic():
        review = TeamReview.objects.create(
            team=order.team,
            order=order,
            advertiser=advertiser,
            rating=rating,
            comment=comment
        )

        # فقط در صورتی که سفارش تکمیل شده باشد امتیاز بده
        if order.status == ContentOrder.Status.COMPLETED:
            # امتیاز برای تبلیغ‌دهنده
            update_score(
                advertiser,
                5,
                'advertiser_submit_team_review',
                f'ثبت نظر برای تیم {order.team.name} (سفارش تکمیل شده)'
            )

            # امتیاز برای تیم بر اساس امتیاز داده شده
            if rating == 5:
                update_score(order.team, 15, 'team_5_star', f'دریافت ۵ ستاره در سفارش {order.campaign.name}')
            elif rating == 4:
                update_score(order.team, 5, 'team_4_star', f'دریافت ۴ ستاره در سفارش {order.campaign.name}')
            elif rating == 2:
                update_score(order.team, -10, 'team_2_star', f'دریافت ۲ ستاره در سفارش {order.campaign.name}')
            elif rating == 1:
                update_score(order.team, -20, 'team_1_star', f'دریافت ۱ ستاره در سفارش {order.campaign.name}')
        # اگر سفارش تکمیل نشده باشد (که نباید پیش آید) امتیازی نمی‌دهیم

        return review


def submit_influencer_review_service(campaign_booking, advertiser, rating, comment=""):
    with transaction.atomic():
        review = InfluencerReview.objects.create(
            channel=campaign_booking.channel,
            campaign_booking=campaign_booking,
            advertiser=advertiser,
            rating=rating,
            comment=comment
        )
        # فقط در صورتی که کمپین تکمیل شده باشد امتیاز بده
        if campaign_booking.status == CampaignInfluencer.Status.COMPLETED:
            update_score(
                advertiser,
                5,
                'advertiser_submit_influencer_review',
                f'ثبت نظر برای کانال {campaign_booking.channel.channel_name} (کمپین تکمیل شده)'
            )
            channel = campaign_booking.channel
            if rating == 5:
                update_score(channel, 15, 'channel_5_star', f'دریافت ۵ ستاره در کمپین {campaign_booking.campaign.name}')
            elif rating == 4:
                update_score(channel, 5, 'channel_4_star', f'دریافت ۴ ستاره در کمپین {campaign_booking.campaign.name}')
            elif rating == 2:
                update_score(channel, -20, 'channel_2_star', f'دریافت ۲ ستاره در کمپین {campaign_booking.campaign.name}')
            elif rating == 1:
                update_score(channel, -30, 'channel_1_star', f'دریافت ۱ ستاره در کمپین {campaign_booking.campaign.name}')
        # اگر کمپین تکمیل نشده باشد، امتیازی نمی‌دهیم
        return review
