from gamification.services import update_score
from notifications.models import Notification
from content_team.models import ContentOrder
from django.db import transaction
from celery import shared_task
from .models import Campaign
import logging

logger = logging.getLogger(__name__)


@shared_task
def penalize_unaccepted_content_orders(campaign_id):
    """بررسی می‌کند که آیا تیم محتوا سفارش‌های این کمپین را ظرف ۲۴ ساعت پذیرفته یا نه"""
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        logger.error(f"❌ کمپین با ID {campaign_id} وجود ندارد")
        return

    if campaign.status != campaign.Status.APPROVED:
        logger.info(f"⏭️ کمپین {campaign.name} در وضعیت {campaign.status} است، تسک اجرا نشد.")
        return

    content_order = ContentOrder.objects.filter(campaign=campaign, status='pending').first()
    if not content_order:
        logger.info(f"⏭️ کمپین {campaign.name} سفارش محتوای در انتظار ندارد.")
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

    logger.info(f"✅ تسک penalize_unaccepted_content_orders برای کمپین {campaign.name} انجام شد.")


@shared_task(bind=True)
def auto_approve_campaign_after_rejection(self, campaign_id):
    """
    اگر کمپین بعد از رد شدن ناشر، ۶۰ ثانیه (برای تست) در حالت REVISION_NEEDED بماند،
    به طور خودکار به APPROVED برمی‌گردد
    """
    logger.info(f"🚀 شروع تسک auto_approve_campaign_after_rejection برای کمپین ID: {campaign_id}")

    try:
        campaign = Campaign.objects.get(id=campaign_id)
        logger.info(
            f"📋 کمپین پیدا شد: {campaign.name} (ID: {campaign.id}) - وضعیت: {campaign.status} - replacement_mode: {campaign.replacement_mode}")
    except Campaign.DoesNotExist:
        logger.error(f"❌ کمپین با ID {campaign_id} وجود ندارد")
        return

    if campaign.status != Campaign.Status.REVISION_NEEDED:
        logger.info(f"⏭️ کمپین {campaign.name} در وضعیت {campaign.status} است (نه REVISION_NEEDED). تسک اجرا نشد.")
        return

    if not campaign.replacement_mode:
        logger.info(f"⏭️ کمپین {campaign.name} replacement_mode=False است. تسک اجرا نشد.")
        return

    logger.info(f"✅ شرایط تسک برقرار است. در حال اجرا...")

    with transaction.atomic():

        # ========== کمپین رو به APPROVED برگردون ==========
        campaign.status = Campaign.Status.APPROVED
        campaign.replacement_mode = False
        campaign.save(update_fields=['status', 'replacement_mode'])

        # ========== نوتیف به کاربر ==========
        from notifications.utils import notify_advertiser_campaign_auto_approved
        notify_advertiser_campaign_auto_approved(campaign)

        logger.info(
            f"✅ کمپین {campaign.name} (ID: {campaign.id}) به صورت خودکار پس از ۱ دقیقه APPROVED شد. {rejected_count} ناشر رد شده نادیده گرفته شدند.")
