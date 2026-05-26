from django.db import transaction
from collections import defaultdict
from accounts.models import Wallet, Transaction
from content_team.models import ContentOrderRevision
from accounts.services.payment_service import pay_influencer
from influencers.models import CampaignReport
from campaigns.models import CampaignInfluencer, CampaignContent
from campaigns.models import Campaign
from django.utils import timezone
from content_team.models import ContentDelivery
from notifications.utils import (
    notify_advertiser_content_order_accepted,
    notify_advertiser_content_order_rejected,
    notify_advertiser_content_delivered,
    notify_advertiser_revision_accepted,
    notify_advertiser_revision_rejected,
    notify_advertiser_campaign_approved,
    notify_advertiser_campaign_rejected,
    notify_advertiser_campaign_pending,
    notify_advertiser_campaign_completed,
    notify_advertiser_campaign_running,
    notify_influencer_new_campaign_orders,
    notify_influencer_report_approved,
    notify_influencer_report_rejected,
    notify_content_team_new_order,
    notify_content_team_revision_requested,
    notify_content_team_order_accepted,
)


def submit_campaign_for_review(campaign):
    """انتقال کمپین از پیش‌نویس به در انتظار تایید پس از پرداخت"""
    if campaign.status == 'draft':
        campaign.status = 'pending'
        campaign.save(update_fields=['status'])

        notify_advertiser_campaign_pending(campaign)
    return campaign


def approve_campaign_by_admin(campaign):
    if campaign.status == 'pending':
        campaign.status = 'approved'
        campaign.save(update_fields=['status'])

        notify_advertiser_campaign_approved(campaign)

        influencer_counts = defaultdict(int)
        bookings = campaign.influencer_bookings.select_related('channel__influencer__user')

        for booking in bookings:
            user = booking.channel.influencer.user
            influencer_counts[user] += 1

        for user, count in influencer_counts.items():
            notify_influencer_new_campaign_orders(user, campaign, count)

        content_order = campaign.content_orders.select_related(
            'team', 'plan', 'plan__service_type'
        ).first()

        if content_order:
            active_team_members = content_order.team.members.filter(is_active=True).select_related('user')

            for member in active_team_members:
                notify_content_team_new_order(member.user, content_order)


def reject_campaign_by_admin(campaign, reason):
    if campaign.status == 'pending':
        campaign.status = 'cancelled'
        campaign.save(update_fields=['status'])
        notify_advertiser_campaign_rejected(campaign, reason)


def accept_content_order_service(order):
    """سرویس قبول سفارش توسط تیم محتوا"""
    with transaction.atomic():
        order.status = 'in_progress'
        order.save(update_fields=['status'])

        notify_advertiser_content_order_accepted(order)


def reject_content_order_service(order):
    """سرویس رد سفارش توسط تیم محتوا"""
    with transaction.atomic():
        order.status = 'cancelled'
        order.save(update_fields=['status'])

        notify_advertiser_content_order_rejected(order)


def deliver_content_order_service(order, team_member, notes, file, new_version):
    """سرویس تحویل فایل سفارش و اتمام آن"""
    with transaction.atomic():
        delivery = ContentDelivery.objects.create(
            order=order,
            status='delivered',
            delivered_by=team_member,
            delivered_at=timezone.now(),
            notes=notes,
            version=new_version,
            file=file,
            file_name=file.name,
            file_size=file.size
        )

        order.status = 'completed'
        order.save(update_fields=['status'])

        notify_advertiser_content_delivered(delivery)
        return delivery


def accept_revision_service(order, revision):
    """سرویس قبول درخواست ویرایش"""
    with transaction.atomic():
        revision.status = 'accepted'
        revision.save(update_fields=['status'])

        order.status = 'in_progress'
        order.save(update_fields=['status'])

        if hasattr(order, 'delivery'):
            order.delivery.status = 'revision_requested'
            order.delivery.save(update_fields=['status'])

        notify_advertiser_revision_accepted(revision)


def reject_revision_service(order, revision):
    """سرویس رد درخواست ویرایش"""
    with transaction.atomic():
        revision.status = 'rejected'
        revision.save(update_fields=['status'])

        order.status = 'completed'
        order.save(update_fields=['status'])

        if hasattr(order, 'delivery'):
            order.delivery.status = 'delivered'
            order.delivery.save(update_fields=['status'])

        notify_advertiser_revision_rejected(revision)


def submit_influencer_report_service(order, post_link, screenshot):
    """
    سرویس ثبت گزارش ناشر، مدیریت وضعیت‌های کمپین و ارسال نوتیفیکیشن‌های مربوطه
    """
    campaign = order.campaign

    with transaction.atomic():
        CampaignReport.objects.create(
            campaign_influencer=order,
            post_link=post_link,
            screenshot=screenshot,
            status='pending'
        )

        order.status = CampaignInfluencer.Status.COMPLETED
        order.save(update_fields=['status'])

        total_reports = CampaignReport.objects.filter(
            campaign_influencer__campaign=campaign
        ).count()

        if total_reports == 1 and campaign.status != Campaign.Status.RUNNING:
            campaign.status = Campaign.Status.RUNNING
            campaign.save(update_fields=['status'])

            try:
                notify_advertiser_campaign_running(campaign)
            except ImportError:
                pass

        from django.db import models
        pending_or_accepted_without_report = CampaignInfluencer.objects.filter(
            campaign=campaign
        ).filter(
            models.Q(status=CampaignInfluencer.Status.PENDING) |
            models.Q(status=CampaignInfluencer.Status.ACCEPTED, report__isnull=True)
        ).count()

        if pending_or_accepted_without_report == 0:
            if campaign.status != Campaign.Status.COMPLETED:
                campaign.status = Campaign.Status.COMPLETED
                campaign.save(update_fields=['status'])

                notify_advertiser_campaign_completed(campaign)


def respond_to_influencer_order_service(order, action):
    """
    مدیریت پاسخ اینفلوئنسر به سفارش (تایید یا رد)
    """
    with transaction.atomic():
        if action == 'accept':
            order.status = 'accepted'
            order.save(update_fields=['status'])

            from notifications.utils import notify_advertiser_influencer_accepted
            notify_advertiser_influencer_accepted(order)

        elif action == 'reject':
            order.status = 'rejected'
            order.save(update_fields=['status'])


def approve_influencer_report_service(report):
    """سرویس تایید گزارش ناشر توسط ادمین و پرداخت به کیف پول"""
    with transaction.atomic():
        if report.status != 'approved':
            report.status = 'approved'
            report.save(update_fields=['status'])

            ci = report.campaign_influencer
            if not ci.is_paid:
                pay_influencer(ci)

            notify_influencer_report_approved(ci)


def reject_influencer_report_service(report, reason=''):
    """سرویس رد گزارش ناشر توسط ادمین"""
    with transaction.atomic():
        if report.status != 'rejected':
            report.status = 'rejected'
            report.save(update_fields=['status'])

            notify_influencer_report_rejected(report.campaign_influencer, reason)


def create_revision_request_service(order, requested_by, feedback, file=None):
    """
    سرویس ثبت درخواست ویرایش، آپدیت وضعیت‌ها و ارسال نوتیفیکیشن
    """
    with transaction.atomic():
        revision = ContentOrderRevision.objects.create(
            order=order,
            requested_by=requested_by,
            feedback=feedback.strip(),
            status='pending'
        )

        if file:
            revision.file = file
            revision.file_name = file.name
            revision.file_size = file.size
            revision.save(update_fields=['file', 'file_name', 'file_size'])

        order.status = 'review_pending'
        order.save(update_fields=['status'])

        if hasattr(order, 'delivery'):
            order.delivery.status = 'revision_requested'
            order.delivery.save(update_fields=['status'])

        active_team_members = order.team.members.filter(is_active=True).select_related('user')
        for member in active_team_members:
            notify_content_team_revision_requested(member.user, revision)

    return revision


def accept_content_order_delivery(order, content_cost, team_members):
    """
    سرویس تأیید نهایی سفارش، تقسیم وجه بین اعضا، ذخیره فایل کمپین و ارسال نوتیفیکیشن
    """
    with transaction.atomic():
        for member in team_members:
            share_amount = int((content_cost * member.revenue_share_percent) / 100)

            if share_amount <= 0:
                continue

            wallet, created = Wallet.objects.get_or_create(user=member.user)
            wallet.balance += share_amount
            wallet.save(update_fields=['balance'])

            Transaction.objects.create(
                user=member.user,
                amount=share_amount,
                type=Transaction.Type.TEAM_PAYMENT,
                status=Transaction.Status.SUCCESS,
                campaign=order.campaign,
                invoice=order.campaign.invoice if hasattr(order.campaign, 'invoice') else None,
                team_member=member,
                description=f'پرداخت سهم از سفارش #{order.id} - تیم {order.team.name} - {member.revenue_share_percent}% - مبلغ: {share_amount:,} تومان'
            )

            notify_content_team_order_accepted(member.user, order, share_amount)

        campaign_content, created = CampaignContent.objects.get_or_create(
            campaign=order.campaign,
            defaults={
                'media': order.delivery.file,
                'notes': f'محتوای تولید شده توسط تیم {order.team.name}',
            }
        )

        if not created:
            campaign_content.media = order.delivery.file
            campaign_content.notes = f'محتوای تولید شده توسط تیم {order.team.name} در تاریخ {timezone.now()}'
            campaign_content.save(update_fields=['media', 'notes'])

        order.delivery.status = 'final_accepted'
        order.delivery.accepted_at = timezone.now()
        order.delivery.save(update_fields=['status', 'accepted_at'])

    return True
