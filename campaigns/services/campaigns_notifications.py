from campaigns.tasks import penalize_unaccepted_content_orders, auto_approve_campaign_after_rejection
from campaigns.models import CampaignReport, CampaignContent, Campaign, CampaignTrackingLink
from content_team.models import ContentOrderRevision, ContentDelivery, ContentOrder
from payment.services.create_invoice import create_campaign_invoice
from payment.services.payment_service import pay_influencer
from payment.models import Wallet, Transaction
from gamification.services import update_score
from influencers.models import ChannelBooking
from notifications.models import Notification
from collections import defaultdict
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.db import models
import uuid
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
    notify_advertiser_influencer_rejected,
    notify_advertiser_campaign_needs_revision,
    notify_advertiser_influencer_report_rejected,
)


def submit_campaign_for_review(campaign):
    """انتقال کمپین از پیش‌نویس به در انتظار تایید پس از پرداخت و اعمال امتیاز های تبلیغ ‌دهنده"""
    if campaign.status == 'draft':
        with transaction.atomic():
            notify_advertiser_campaign_pending(campaign)
            advertiser = campaign.advertiser
            is_first_campaign = not advertiser.campaigns.exclude(status='draft').exists()
            if is_first_campaign:
                update_score(advertiser, 70, 'ساخت اولین کمپین', 'امتیاز ثبت اولین کمپین در پلتفرم')

            if hasattr(campaign, 'invoice') and campaign.invoice:
                payable_amount = campaign.invoice.payable_amount
                if payable_amount < 10_000_000:
                    update_score(advertiser, 30, 'ثبت کمپین زیر 10 میلیون تومان',
                                 f'ثبت کمپین با بودجه زیر ۱۰ میلیون تومان (کمپین {campaign.name})')
                elif 10_000_000 <= payable_amount <= 30_000_000:
                    update_score(advertiser, 50, 'ثبت کمپین زیر 30 میلیون تومان',
                                 f'ثبت کمپین با بودجه بین ۱۰ تا ۳۰ میلیون تومان (کمپین {campaign.name})')
                elif payable_amount > 30_000_000:
                    update_score(advertiser, 70, 'ثبت کمپین بالای 30 میلیون تومان',
                                 f'ثبت کمپین با بودجه بالای ۳۰ میلیون تومان (کمپین {campaign.name})')

            if campaign.content_orders.exists():
                update_score(advertiser, 15, 'استفاده از تیم تولید محتوا',
                             f'استفاده از خدمات تیم تولید محتوا در کمپین {campaign.name}')

            campaign.status = 'pending'
            campaign.save(update_fields=['status'])

    return campaign


def approve_campaign_by_admin(campaign):
    if campaign.status == 'pending' or campaign.is_free:
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

        if campaign.content_type.slug != 'content-production-team':
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
        campaign = order.campaign

        order.status = 'cancelled'
        order.save(update_fields=['status'])

        update_score(order.team, -50, 'رد کردن سفارش تبلیغ',
                     f'رد سفارش تولید محتوای کمپین {campaign.name}')

        if campaign.invoice and campaign.invoice.content_cost > 0:
            advertiser_user = campaign.advertiser.user
            wallet = advertiser_user.wallet

            wallet.balance += campaign.invoice.content_cost
            wallet.save(update_fields=['balance'])

            Transaction.objects.create(
                user=advertiser_user,
                amount=campaign.invoice.content_cost,
                type=Transaction.Type.CAMPAIGN_REFUND,
                status=Transaction.Status.SUCCESS,
                campaign=campaign,
                description=f'برگشت کامل هزینه تیم محتوا ({campaign.invoice.content_cost:,} تومان) به دلیل رد سفارش توسط {order.team.name}',
                reference_id=f'TEAM_REJECT_REFUND_{campaign.id}_{timezone.now().timestamp()}'
            )

        notify_advertiser_content_order_rejected(campaign, order.team)

        campaign.status = Campaign.Status.REVISION_NEEDED
        campaign.content_team_rejected = True
        campaign.replacement_mode = True
        campaign.save(update_fields=['status', 'content_team_rejected', 'replacement_mode'])


def deliver_content_order_service(order, primary_delivery):
    """
    سرویس تحویل فایل سفارش (فقط برای نوتیف و امتیاز)
    دلیوری قبلاً در ویو ایجاد شده
    """
    if not primary_delivery:
        return None

    with transaction.atomic():
        # ========== امتیازدهی بر اساس ددلاین ==========
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

        # ========== ارسال نوتیف (با دلیوری که قبلاً ساخته شده) ==========
        notify_advertiser_content_delivered(primary_delivery)

        return primary_delivery


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

        update_score(order.team, 10, 'قبول درخواست ویرایش',
                     f'پذیرش و انجام اصلاحیه کمپین{revision.order.campaign.name}')

        notify_advertiser_revision_accepted(revision)


def reject_revision_service(order, revision):
    """
    سرویس رد درخواست ویرایش توسط تیم محتوا
    ۳۰- امتیاز منفی برای تیم
    وضعیت سفارش به DONE تغییر میکند
    وضعیت آخرین تحویل به DELIVERED برمیگردد
    """
    with transaction.atomic():
        # ========== ۱. آپدیت وضعیت ریویژن ==========
        revision.status = 'rejected'
        revision.save(update_fields=['status'])

        # ========== ۲. تغییر وضعیت سفارش به DONE ==========
        order.status = ContentOrder.Status.DONE
        order.save(update_fields=['status'])

        # ========== ۳. پیدا کردن آخرین تحویل ==========
        last_delivery = order.deliveries.first()

        if last_delivery:
            # ========== ۴. برگردوندن وضعیت تحویل به DELIVERED ==========
            last_delivery.status = ContentDelivery.DeliveryStatus.DELIVERED
            last_delivery.save(update_fields=['status'])

        # ========== ۵. امتیاز منفی برای تیم ==========
        update_score(order.team, -30, 'رد درخواست ویرایش',
                     f'رد درخواست اصلاحیه کمپین {revision.order.campaign.name}')

        # ========== ۶. نوتیف به تبلیغ‌دهنده ==========
        notify_advertiser_revision_rejected(revision)

    return True


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

        order.status = ChannelBooking.Status.COMPLETED
        order.save(update_fields=['status'])

        # --- سیستم گیمیفیکیشن ---
        update_score(order.channel, 15, 'ارسال گزارش تبلیغ',
                     f' ارسال گزارش عملکرد و اتمام کمپین {order.campaign.name} در کانال {order.channel.channel_name} در {order.channel.platform.name}')

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

        pending_or_accepted_without_report = ChannelBooking.objects.filter(
            campaign=campaign
        ).filter(
            models.Q(status=ChannelBooking.Status.PENDING) |
            models.Q(status=ChannelBooking.Status.ACCEPTED, report__isnull=True)
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

            # ساخت لینک ردیابی اگر وجود نداشت
            if not hasattr(order, 'tracking_link'):
                if not order.tracking_code:
                    order.tracking_code = uuid.uuid4().hex[:8]
                    order.save(update_fields=['tracking_code'])
                CampaignTrackingLink.objects.create(campaign_influencer=order)

            # امتیازدهی بر اساس نوع کمپین
            if order.campaign.is_free:
                points = 70
                action_key = 'قبول کردن کمپین رایگان'
                description = f'قبول سفارش کمپین رایگان {order.campaign.name} در کانال {order.channel.channel_name}'
            else:
                points = 20
                action_key = 'قبول کردن تبلیغ'
                description = f'قبول سفارش کمپین {order.campaign.name} در کانال {order.channel.channel_name}'

            update_score(order.channel, points, action_key, description)

            from notifications.utils import notify_advertiser_influencer_accepted
            notify_advertiser_influencer_accepted(order)

        elif action == 'reject':
            order.status = 'rejected'
            order.rejected_at = timezone.now()
            order.save(update_fields=['status', 'rejected_at'])

            # ========== برگشت پول به کیف پول تبلیغ‌دهنده (فقط برای کمپین‌های غیر رایگان) ==========
            if not order.campaign.is_free:
                advertiser_user = order.campaign.advertiser.user
                wallet = advertiser_user.wallet

                # ✅ قدم ۱: ذخیره مالیات قبلی قبل از هر تغییری
                old_vat = 0
                old_commission = 0
                if hasattr(order.campaign, 'invoice') and order.campaign.invoice:
                    old_vat = int(order.campaign.invoice.total_vat)
                    old_commission = int(order.campaign.invoice.commission)

                # برگشت مبلغ به کیف پول
                wallet.balance += order.price
                wallet.save(update_fields=['balance'])

                # ثبت تراکنش برگشت
                Transaction.objects.create(
                    user=advertiser_user,
                    amount=order.price,
                    type=Transaction.Type.CAMPAIGN_REFUND,
                    status=Transaction.Status.SUCCESS,
                    campaign=order.campaign,
                    description=f'برگشت وجه بابت رد سفارش توسط ناشر {order.channel.channel_name} در کمپین {order.campaign.name}',
                    reference_id=f'REFUND_INFLUENCER_REJECT_{order.id}_{timezone.now().timestamp()}'
                )

                # ========== به‌روزرسانی فاکتور با حفظ مالیات قبلی ==========
                campaign = order.campaign

                if hasattr(campaign, 'invoice') and campaign.invoice:
                    # ✅ قدم ۲: ایجاد فاکتور جدید (که مالیات رو به‌روز می‌کنه)
                    invoice = create_campaign_invoice(campaign)

                    # ✅ قدم ۳: برگردوندن مالیات قبلی به فاکتور جدید
                    if old_vat > 0:
                        # محاسبه نسبت مالیات قبلی به کل
                        # این کار رو می‌کنیم تا مالیات جدید رو با نسبت قبلی تنظیم کنیم

                        # محاسبه مالیات جدیدی که create_campaign_invoice ساخته
                        new_influencer_vat = invoice.influencer_vat
                        new_content_vat = invoice.content_vat
                        new_commission_vat = invoice.commission_vat
                        new_total_vat = invoice.total_vat

                        # محاسبه نسبت مالیات جدید به قبلی
                        # اگه مالیات جدید صفر شد، از نسبت ۱ استفاده می‌کنیم
                        if new_total_vat > 0:
                            ratio = old_vat / new_total_vat
                        else:
                            ratio = 1

                        # تنظیم مالیات‌ها با نسبت قبلی
                        invoice.influencer_vat = int(new_influencer_vat * ratio)
                        invoice.content_vat = int(new_content_vat * ratio)
                        invoice.commission_vat = int(new_commission_vat * ratio)
                        invoice.total_vat = old_vat  # ✅ حفظ مالیات قبلی


                    # ✅ قدم ۴: حفظ کمیسیون قبلی (همون کاری که قبلاً میکردیم)
                    # ✅ قدم ۴: حفظ کمیسیون قبلی
                    if invoice.commission < old_commission:
                        invoice.commission = old_commission
                        invoice.total_amount = invoice.influencer_cost + invoice.content_cost + invoice.commission
                        invoice.payable_amount = max(invoice.total_amount + invoice.total_vat - invoice.discount_amount, 0)

                    # ✅ قدم ۵: ذخیره نهایی فاکتور
                    invoice.save(update_fields=[
                        'influencer_vat',
                        'content_vat',
                        'commission_vat',
                        'total_vat',
                        'commission',
                        'total_amount',
                        'payable_amount'
                    ])

                # ========== نوتیف به تبلیغ‌دهنده ==========
                notify_advertiser_influencer_rejected(order)

            # ========== تغییر وضعیت کمپین به REVISION_NEEDED ==========
            campaign = order.campaign

            if campaign.status == Campaign.Status.APPROVED:
                campaign.status = Campaign.Status.REVISION_NEEDED
                campaign.replacement_mode = True
                campaign.save(update_fields=['status', 'replacement_mode'])

                notify_advertiser_campaign_needs_revision(campaign, order.channel)

                if settings.CELERY_ENABLED:
                    auto_approve_campaign_after_rejection.apply_async(
                        args=[campaign.id],
                        countdown=60 * 60 * 24
                    )

            if not order.campaign.is_free:
                update_score(order.channel, -40, 'رد کردن تبلیغ',
                             f'رد سفارش کمپین {order.campaign.name} در کانال {order.channel.channel_name} در {order.channel.platform.name}')
            else:
                Notification.objects.create(
                    user=order.channel.influencer.user,
                    type='info',
                    title='رد سفارش رایگان',
                    message=f'شما سفارش کمپین خیریه {order.campaign.name} را رد کردید. امتیازی کسر نشد.',
                    related_object_id=order.id,
                    related_content_type='campaign_influencer'
                )


def approve_influencer_report_service(report):
    """سرویس تایید گزارش ناشر توسط ادمین و پرداخت مالی (+۵ امتیاز برای کانال)"""
    with transaction.atomic():
        if report.status != 'approved':
            report.status = 'approved'
            report.save(update_fields=['status'])

            ci = report.campaign_influencer
            if not ci.is_paid:
                pay_influencer(ci)

            update_score(ci.channel, 5, 'تایید شدن گزارش',
                         f'تایید نهایی گزارش عملکرد توسط ادمین برای کانال {ci.channel.channel_name} در {ci.channel.platform.name}')

            notify_influencer_report_approved(ci)


def reject_influencer_report_service(report, reason=''):
    """سرویس رد گزارش ناشر توسط ادمین"""
    with transaction.atomic():
        if report.status != 'rejected':
            report.status = 'rejected'
            report.save(update_fields=['status'])

            # ========== دریافت اطلاعات سفارش ==========
            campaign_influencer = report.campaign_influencer
            campaign = campaign_influencer.campaign
            advertiser_user = campaign.advertiser.user
            channel = campaign_influencer.channel
            price = campaign_influencer.price

            # ========== برگشت پول به کیف پول تبلیغ‌دهنده ==========
            if not campaign.is_free and not campaign_influencer.is_paid and price > 0:
                # ۱. برگشت به کیف پول تبلیغ‌دهنده
                advertiser_wallet = advertiser_user.wallet
                advertiser_wallet.balance += price
                advertiser_wallet.save(update_fields=['balance'])

                # ۲. ثبت تراکنش برگشت برای تبلیغ‌دهنده
                Transaction.objects.create(
                    user=advertiser_user,
                    amount=price,
                    type=Transaction.Type.CAMPAIGN_REFUND,
                    status=Transaction.Status.SUCCESS,
                    campaign=campaign,
                    invoice=campaign.invoice if hasattr(campaign, 'invoice') else None,
                    description=f'برگشت وجه بابت رد گزارش ناشر {channel.channel_name} (شناسه کانال: {channel.channel_id}@) در کمپین {campaign.name}',
                    reference_id=f'REFUND_INFLUENCER_REPORT_REJECT_{campaign_influencer.id}_{timezone.now().timestamp()}'
                )

                # ========== نوتیف به تبلیغ‌دهنده ==========
                notify_advertiser_influencer_report_rejected(campaign_influencer, reason)

            # ========== نوتیف به اینفلوئنسر ==========
            notify_influencer_report_rejected(campaign_influencer, reason)


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

        last_delivery = order.deliveries.first()
        if last_delivery:
            last_delivery.status = 'revision_requested'
            last_delivery.save(update_fields=['status'])

        if hasattr(order, 'delivery'):
            order.delivery.status = 'revision_requested'
            order.delivery.save(update_fields=['status'])

        active_team_members = order.team.members.filter(is_active=True).select_related('user')
        for member in active_team_members:
            notify_content_team_revision_requested(member.user, revision)

    return revision


def accept_content_order_delivery(order, content_cost, team_members, primary_delivery=None):
    """سرویس تأیید نهایی سفارش، تقسیم وجه و بررسی بونوس تایید بدون اصلاحیه (+۳۰ امتیاز برای تیم)"""
    with transaction.atomic():

        if not primary_delivery:
            primary_delivery = order.deliveries.first()

        if not primary_delivery:
            return False

        # ✅ پیدا کردن فایل انتخاب شده
        primary_file = primary_delivery.files.filter(is_selected=True).first()

        # ❌ اگه فایل انتخاب شده پیدا نشد، از اولین فایل استفاده کن
        if not primary_file:
            primary_file = primary_delivery.files.first()

        if not primary_file:
            return False

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
            update_score(order.team, 30, 'تایید نهایی بدون درخواست ویرایش',
                         f'تایید نهایی سفارش {order.campaign.name} بدون هیچ درخواست اصلاحیه‌ای از سمت کارفرما #{order.id}')

        # ✅ استفاده از primary_file (فایل انتخاب شده)
        campaign_content, created = CampaignContent.objects.get_or_create(
            campaign=order.campaign,
            defaults={
                'media': primary_file.file,
                'notes': f'محتوای تولید شده توسط تیم {order.team.name}',
            }
        )

        if not created:
            campaign_content.media = primary_file.file
            campaign_content.notes = f'محتوای تولید شده توسط تیم {order.team.name} در تاریخ {timezone.now()}'
            campaign_content.save(update_fields=['media', 'notes'])

        primary_delivery.status = 'final_accepted'
        primary_delivery.accepted_at = timezone.now()
        primary_delivery.save(update_fields=['status', 'accepted_at'])
        order.status = "completed"
        order.save(update_fields=['status', ])

        campaign = order.campaign
        if campaign.content_type.slug == 'content-production-team':
            influencer_counts = defaultdict(int)
            bookings = campaign.influencer_bookings.select_related('channel__influencer__user')

            for booking in bookings:
                user = booking.channel.influencer.user
                influencer_counts[user] += 1

            for user, count in influencer_counts.items():
                notify_influencer_new_campaign_orders(user, campaign, count)

    return True
