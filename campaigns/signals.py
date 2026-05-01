from django.db.models.signals import pre_save, post_save
from .models import CampaignTrackingLink
from .models import CampaignInfluencer
from django.dispatch import receiver


@receiver(post_save, sender=CampaignInfluencer)
def create_tracking_link(sender, instance, created, **kwargs):
    if created:
        CampaignTrackingLink.objects.create(
            campaign_influencer=instance
        )
