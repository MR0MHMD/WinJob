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


@receiver(pre_save, sender=CampaignInfluencer)
def save_old_status(sender, instance, **kwargs):
    """قبل از ذخیره، وضعیت قبلی رو ذخیره می‌کنیم"""
    if instance.pk:
        old = sender.objects.get(pk=instance.pk)
        instance._old_status = old.status
        instance._was_paid = old.is_paid
    else:
        instance._old_status = None
        instance._was_paid = False


@receiver(post_save, sender=CampaignInfluencer)
def pay_influencer_on_completed(sender, instance, created, **kwargs):
    """
    بعد از ذخیره، اگر وضعیت به COMPLETED تغییر کرده بود و پرداخت نشده بود،
    پول رو به اینفلوئنسر واریز کن
    """
    # اگه تازه ساخته شده، کاری نکن
    if created:
        return

    # اگه وضعیت تغییر نکرده، کاری نکن
    if instance._old_status == instance.status:
        return

    # اگه وضعیت جدید COMPLETED هست و قبلاً پرداخت نشده
    if instance.status == CampaignInfluencer.Status.COMPLETED and not instance._was_paid:
        from accounts.payment_service import pay_influencer
        pay_influencer(instance)
