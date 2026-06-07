from celery import shared_task
from .models import Campaign
from content_team.models import ContentOrder
from gamification.services import update_score
from notifications.models import Notification

@shared_task
def penalize_unaccepted_content_orders(campaign_id):
    """
    بررسی می‌کند که آیا تیم محتوا سفارش‌های این کمپین را ظرف ۲ دقیقه (تست) پذیرفته یا نه.
    اگر نه، ۸۰ امتیاز منفی می‌دهد.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return

    if campaign.status != campaign.Status.APPROVED:
        return

    content_order = ContentOrder.objects.filter(campaign=campaign, status='pending').first()
    if not content_order:
        return

    team = content_order.team
    update_score(team, -80, 'عدم پذیرش به موقع سفارش',
                 f'سفارش #{content_order.id} مربوط به کمپین {campaign.name} ظرف 24 ساعت پس از تایید پذیرفته نشد.')

    manager = team.members.filter(role='manager').first()
    if manager and manager.user:
        Notification.objects.create(
            user=manager.user,
            type='penalty',
            title='جریمه عدم پذیرش سفارش',
            message=f'سفارش #{content_order.id} ظرف زمان مقرر پذیرفته نشد. ۸۰ امتیاز از تیم {team.name} کسر شد.',
            related_object_id=campaign.id,
            related_content_type='campaign'
        )
