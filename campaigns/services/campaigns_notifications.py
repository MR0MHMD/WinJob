from django.db import transaction
from django.db import models
from django.utils import timezone
from collections import defaultdict
from django.conf import settings
from accounts.models import Wallet, Transaction
from content_team.models import ContentOrderRevision, ContentDelivery
from accounts.services.payment_service import pay_influencer
from influencers.models import CampaignReport
from campaigns.models import CampaignInfluencer, CampaignContent, Campaign
from campaigns.tasks import penalize_unaccepted_content_orders
from gamification.services import update_score
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
    """انتقال کمپین از پیش‌نویس به در انتظار تایید پس از پرداخت و اعمال امتیاز های تبلیغ ‌دهنده"""
    if campaign.status == 'draft':
        with transaction.atomic():
            campaign.status = 'pending'
            campaign.save(update_fields=['status'])
            notify_advertiser_campaign_pending(campaign)
            advertiser = campaign.advertiser
            is_first_campaign = not advertiser.campaigns.exclude(status='draft').exists()
            if is_first_campaign:
                update_score(advertiser, 70, 'ساخت اولین کمپین', 'امتیاز ثبت اولین کمپین در پلتفرم')

            if hasattr(campaign, 'invoice') and campaign.invoice:
                payable_amount = campaign.invoice.payable_amount
                if payable_amount < 10_000_000:
                    update_score(advertiser, 30, 'ثبت کمپین زیر 10 میلیون تومان', f'ثبت کمپین با بودجه زیر ۱۰ میلیون تومان (کمپین {campaign.name})')
                elif 10_000_000 <= payable_amount <= 30_000_000:
                    update_score(advertiser, 50, 'ثبت کمپین زیر 30 میلیون تومان', f'ثبت کمپین با بودجه بین ۱۰ تا ۳۰ میلیون تومان (کمپین {campaign.name})')
                elif payable_amount > 30_000_000:
                    update_score(advertiser, 70, 'ثبت کمپین بالای 30 میلیون تومان', f'ثبت کمپین با بودجه بالای ۳۰ میلیون تومان (کمپین {campaign.name})')

            if campaign.content_orders.exists():
                update_score(advertiser, 15, 'استفاده از تیم تولید محتوا', f'استفاده از خدمات تیم تولید محتوا در کمپین {campaign.name}')

    return campaign


def approve_campaign_by_admin(campaign):
    if campaign.status == 'pending':
        campaign.status = 'approved'
        campaign.approved_at = timezone.now()
        campaign.save()
        campaign.save(update_fields=['status', "approved_at"])

        if settings.CELERY_ENABLED:
            penalize_unaccepted_content_orders.apply_async(
                args=[campaign.id],
                countdown=60 * 60 * 24
            )

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
    """سرویس قبول سفارش توسط تیم محتوا (+۲۰ امتیاز برای تیم)"""
    with transaction.atomic():
        order.status = 'in_progress'
        order.save(update_fields=['status'])

        # --- سیستم گیمیفیکیشن ---
        update_score(order.team, 20, 'قبول کردن سفارش تبلیغ', f'قبول سفارش تولید محتوای کمپین{order.campaign.name}')

        notify_advertiser_content_order_accepted(order)


def reject_content_order_service(order):
    """سرویس رد سفارش توسط تیم محتوا (۵۰- امتیاز منفی برای تیم)"""
    with transaction.atomic():
        order.status = 'cancelled'
        order.save(update_fields=['status'])

        # --- سیستم گیمیفیکیشن ---
        update_score(order.team, -50, 'رد کردن سفارش تبلیغ', f'رد سفارش تولید محتوای کمپین{order.campaign.name}')

        notify_advertiser_content_order_rejected(order)


def deliver_content_order_service(order, team_member, notes, file, new_version):
    """سرویس تحویل فایل سفارش و بررسی تحویل قبل یا بعد از ضرب‌الاجل (Deadline)"""
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

        if order.deadline:
            if timezone.now() <= order.deadline:
                update_score(order.team, 30, 'تحویل به موقع',
                             f'تحویل به موقع فایل سفارش کمپین{order.campaign.name} قبل از ددلاین')
            else:
                update_score(order.team, -20, 'تحویل دیرکرد',
                             f'تحویل تاخیری فایل سفارش کمپین{order.campaign.name} بعد از ددلاین')
        else:
            update_score(order.team, 20, 'تحویل فایل سفارش',
                         f'تحویل فایل سفارش کمپین {order.campaign.name}')

        notify_advertiser_content_delivered(delivery)
        return delivery


def accept_revision_service(order, revision):
    """سرویس قبول درخواست ویرایش توسط تیم محتوا (+۱۰ امتیاز برای تیم)"""
    with transaction.atomic():
        revision.status = 'accepted'
        revision.save(update_fields=['status'])

        order.status = 'in_progress'
        order.save(update_fields=['status'])

        if hasattr(order, 'delivery'):
            order.delivery.status = 'revision_requested'
            order.delivery.save(update_fields=['status'])

        update_score(order.team, 10, 'قبول درخواست ویرایش', f'پذیرش و انجام اصلاحیه کمپین{revision.order.campaign.name}')

        notify_advertiser_revision_accepted(revision)


def reject_revision_service(order, revision):
    """سرویس رد درخواست ویرایش توسط تیم محتوا (۳۰- امتیاز منفی برای تیم)"""
    with transaction.atomic():
        revision.status = 'rejected'
        revision.save(update_fields=['status'])

        order.status = 'completed'
        order.save(update_fields=['status'])

        if hasattr(order, 'delivery'):
            order.delivery.status = 'delivered'
            order.delivery.save(update_fields=['status'])

        update_score(order.team, -30, 'در درخواست ویرایش', f'رد درخواست اصلاحیه کمپین{revision.order.campaign.name}')

        notify_advertiser_revision_rejected(revision)


def submit_influencer_report_service(order, post_link, screenshot):
    """سرویس ثبت گزارش ناشر و اتمام کار کانال (+۱۵ امتیاز برای کانال ناشر)"""
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

        # --- سیستم گیمیفیکیشن ---
        update_score(order.channel, 15, 'ارسال گزارش تبلیغ', f'ارسال گزارش عملکرد و اتمام کمپین {order.campaign.name} در کانال {order.channel.channel_name}در {order.channel.platform.name}')

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
    """مدیریت پاسخ اینفلوئنسر به سفارش (تایید: ۲۰+ امتیاز / رد: ۴۰- امتیاز برای کانال)"""
    with transaction.atomic():
        if action == 'accept':
            order.status = 'accepted'
            order.save(update_fields=['status'])

            # --- سیستم گیمیفیکیشن ---
            update_score(order.channel, 20, 'قبول کردن تبلیغ', f'قبول سفارش کمپین {order.campaign.name} در کانال {order.channel.channel_name}در {order.channel.platform.name}')

            from notifications.utils import notify_advertiser_influencer_accepted
            notify_advertiser_influencer_accepted(order)

        elif action == 'reject':
            order.status = 'rejected'
            order.save(update_fields=['status'])

            # --- سیستم گیمیفیکیشن ---
            update_score(order.channel, -40, 'رد کردن تبلیغ', f'رد سفارش کمپین {order.campaign.name} در کانال {order.channel.channel_name}در {order.channel.platform.name}')


def approve_influencer_report_service(report):
    """سرویس تایید گزارش ناشر توسط ادمین و پرداخت مالی (+۵ امتیاز برای کانال)"""
    with transaction.atomic():
        if report.status != 'approved':
            report.status = 'approved'
            report.save(update_fields=['status'])

            ci = report.campaign_influencer
            if not ci.is_paid:
                pay_influencer(ci)

            update_score(ci.channel, 5, 'تایید شدن گزارش', f'تایید نهایی گزارش عملکرد توسط ادمین برای کانال {ci.channel.channel_name} در {ci.channel.platform.name}')

            notify_influencer_report_approved(ci)


def reject_influencer_report_service(report, reason=''):
    """سرویس رد گزارش ناشر توسط ادمین"""
    with transaction.atomic():
        if report.status != 'rejected':
            report.status = 'rejected'
            report.save(update_fields=['status'])

            notify_influencer_report_rejected(report.campaign_influencer, reason)


def create_revision_request_service(order, requested_by, feedback, file=None):
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
    """سرویس تأیید نهایی سفارش، تقسیم وجه و بررسی بونوس تایید بدون اصلاحیه (+۳۰ امتیاز برای تیم)"""
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

        has_revisions = ContentOrderRevision.objects.filter(order=order).exists()
        if not has_revisions:
            update_score(order.team, 30, 'تایید نهایی بدون درخواست ویرایش', f'تایید نهایی سفارش {order.campaign.name} بدون هیچ درخواست اصلاحیه‌ای از سمت کارفرما #{order.id}')

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
