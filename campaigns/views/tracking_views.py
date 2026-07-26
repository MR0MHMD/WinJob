from django.shortcuts import redirect, get_object_or_404
from ..models import CampaignChannel, CampaignClick
from django.db.models import F


def track_click(request, code):
    influencer = get_object_or_404(
        CampaignChannel,
        tracking_code=code
    )

    tracking = influencer.tracking_link
    ip = request.META.get("REMOTE_ADDR")
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    is_unique = not CampaignClick.objects.filter(
        tracking_link=tracking,
        ip_address=ip
    ).exists()

    CampaignClick.objects.create(
        tracking_link=tracking,
        ip_address=ip,
        user_agent=user_agent
    )

    tracking.clicks = F("clicks") + 1
    if is_unique:
        tracking.unique_clicks = F("unique_clicks") + 1
    tracking.save(update_fields=["clicks", "unique_clicks"])

    campaign = influencer.campaign
    content = campaign.content

    if content.utm_enabled:
        destination_url = content.get_utm_link(influencer)
    else:
        destination_url = content.link

    return redirect(destination_url)
