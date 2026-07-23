from django.utils import timezone
from payment.models import Transaction


def pay_influencer(campaign_influencer):
    """
    پرداخت به اینفلوئنسر بعد از اینکه ادمین وضعیت رو COMPLETED کرد
    """
    influencer_user = campaign_influencer.channel.influencer.user
    amount = campaign_influencer.price

    wallet = influencer_user.wallet
    wallet.balance += amount
    wallet.save()

    Transaction.objects.create(
        user=influencer_user,
        amount=amount,
        type=Transaction.Type.INFLUENCER_PAYMENT,
        status=Transaction.Status.SUCCESS,
        campaign=campaign_influencer.campaign,
        description=f"پرداخت بابت کمپین {campaign_influencer.campaign.name}",
        reference_id=campaign_influencer.tracking_code
    )

    campaign_influencer.is_paid = True
    campaign_influencer.paid_at = timezone.now()
    campaign_influencer.save(update_fields=['is_paid', 'paid_at'])
