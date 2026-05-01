from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import CampaignReport

@receiver(pre_save, sender=CampaignReport)
def save_old_report_status(sender, instance, **kwargs):
    if instance.pk:
        instance._old_status = sender.objects.get(pk=instance.pk).status
    else:
        instance._old_status = None

@receiver(post_save, sender=CampaignReport)
def pay_influencer_when_report_approved(sender, instance, created, **kwargs):
    print("********** SIGNAL CALLED **********")
    if created:
        print("CREATED, RETURN")
        return
    old = getattr(instance, '_old_status', None)
    if old is None or old == instance.status:
        return
    if instance.status == CampaignReport.Status.APPROVED:
        ci = instance.campaign_influencer
        if not ci.is_paid:
            from accounts.services.payment_service import pay_influencer
            if pay_influencer(ci):
                ci.is_paid = True
                ci.paid_at = timezone.now()
                ci.save(update_fields=['is_paid', 'paid_at'])
