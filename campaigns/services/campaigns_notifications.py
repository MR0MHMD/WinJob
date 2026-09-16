from campaigns.tasks import penalize_unaccepted_content_orders, auto_approve_campaign_after_rejection
from campaigns.models import CampaignReport, CampaignContent, Campaign, CampaignTrackingLink
from content_team.models import ContentOrderRevision, ContentDelivery, ContentOrder, ContentServicePlan
from content_team.services import create_portfolio_from_order
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
import logging
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

logger = logging.getLogger(__name__)

# ========== توابع کمکی برای پشتیبانی از سفارش‌های مستقل ==========

def get_order_related_user(order):
    """دریافت کاربر مرتبط با سفارش (تبلیغ‌دهنده یا کاربر مستقل)"""
    if order.campaign:
        return order.campaign.advertiser.user
    elif order.standalone_user:
        return order.standalone_user
    return None

def get_order_display_name(order):
    """دریافت نام نمایشی سفارش (نام کمپین یا نام کاربر)"""
    if order.campaign:
        return order.campaign.name
    elif order.standalone_user:
        return f"سفارش مستقل {order.standalone_user.nickname or order.standalone_user.phone_number}"
    return f"سفارش #{order.id}"

def get_order_invoice(order):
    """دریافت فاکتور مرتبط با سفارش"""
    if order.campaign and hasattr(order.campaign, 'invoice'):
        return order.campaign.invoice
    return None


# ========== توابع کمکی برای واریز کمیسیون ==========

def _should_payout_commission(invoice, order=None):
    """
    آیا الان زمان واریز کمیسیون هست؟

    قواعد:
    - سفارش مستقل: بله، بلافاصله
    - کمپین فقط نشر: بله، وقتی کمپین COMPLETED
    - کمپین ترکیبی (نشر + محتوا): بله، وقتی هم کمپین COMPLETED
      و هم آخرین سفارش محتوای فعال COMPLETED

    ⚠️ نکته مهم:
    اگه تیم تولید محتوا رد کرده و تیم جدید انتخاب شده،
    فقط آخرین سفارش (که CANCELLED نیست) رو چک می‌کنیم.
    """
    if not invoice:
        return False

    if invoice.is_commission_paid:
        return False

    # ===== تابع کمکی: چک کردن وضعیت سفارش‌های محتوا =====
    def is_content_ready(campaign):
        """آیا آخرین سفارش محتوای فعال COMPLETED هست؟"""
        # آخرین سفارشی که رد نشده رو بگیر
        last_active_order = campaign.content_orders.exclude(
            status=ContentOrder.Status.CANCELLED
        ).order_by('-id').first()

        # اگه هیچ سفارش فعالی نیست، پس مشکلی نیست
        if not last_active_order:
            return True

        # آخرین سفارش فعال باید COMPLETED باشه
        return last_active_order.status == ContentOrder.Status.COMPLETED

    # ===== سفارش مستقل =====
    if order and order.is_standalone:
        return True

    # ===== سفارش کمپینی =====
    if order and order.campaign:
        campaign = order.campaign

        # چک ۱: کمپین باید COMPLETED باشه
        if campaign.status != Campaign.Status.COMPLETED:
            return False

        # چک ۲: آخرین سفارش محتوای فعال باید COMPLETED باشه
        if not is_content_ready(campaign):
            return False

        return True

    # ===== حالت مستقیم (فقط invoice) =====
    if invoice.campaign_id:
        campaign = invoice.campaign

        if campaign.status != Campaign.Status.COMPLETED:
            return False

        if not is_content_ready(campaign):
            return False

        return True

    return False


def _try_payout_commission(invoice, order=None):
    """
    تلاش برای واریز کمیسیون - با مدیریت خطا

    این تابع هیچ‌وقت exception نمی‌ندازه بیرون.
    خطاها رو لاگ می‌کنه.

    Returns:
        PayoutResult یا None
    """
    if not invoice:
        return None

    # چک شرایط واریز
    if not _should_payout_commission(invoice, order=order):
        return None

    try:
        from payment.services.payout import payout_commission, PayoutError

        result = payout_commission(
            invoice=invoice,
            campaign=invoice.campaign if hasattr(invoice, 'campaign') else None,
        )

        if result.success:
            logger.info(
                f'✅ کمیسیون واریز شد: {invoice.invoice_number} - '
                f'{result.total_paid:,} تومان - {len(result.transactions)} تراکنش'
            )
        else:
            logger.warning(
                f'⚠️ واریز رد شد: {invoice.invoice_number} - {result.message}'
            )

        return result

    except PayoutError as e:
        logger.error(
            f'❌ خطای واریز برای فاکتور {invoice.invoice_number}: {e}'
        )
        return None

    except Exception as e:
        logger.exception(
            f'❌ خطای غیرمنتظره در واریز برای فاکتور {invoice.invoice_number}: {e}'
        )
        return None


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
        display_name = get_order_display_name(order)
        update_score(
            order.team, 20,
            'قبول کردن سفارش تبلیغ',
            f'قبول سفارش {display_name}'
        )

        notify_advertiser_content_order_accepted(order)


def reject_content_order_service(order):
    """سرویس رد سفارش توسط تیم محتوا (۵۰- امتیاز منفی برای تیم)"""
    with transaction.atomic():
        # ========== ۱. تغییر وضعیت سفارش ==========
        order.status = ContentOrder.Status.CANCELLED
        order.save(update_fields=['status'])

        # ========== ۲. امتیاز منفی برای تیم ==========
        display_name = get_order_display_name(order)
        update_score(
            order.team, -50,
            'رد کردن سفارش تبلیغ',
            f'رد سفارش {display_name}'
        )

        # ========== ۳. محاسبه مبلغ برگشتی ==========
        user = get_order_related_user(order)
        invoice = get_order_invoice(order)

        # برای سفارش مستقل، فاکتور از خود سفارش میاد
        if not invoice and order.is_standalone and hasattr(order, 'invoice'):
            invoice = order.invoice

        refund_amount = 0
        description = ''

        if invoice:
            if order.is_standalone:
                # ⚡ سفارش مستقل → کل مبلغ پرداختی
                refund_amount = invoice.payable_amount
                description = (
                    f'برگشت کامل مبلغ پرداختی سفارش #{order.id} '
                    f'({refund_amount:,} تومان) به دلیل رد سفارش توسط تیم {order.team.name}'
                )
            else:
                # ⚡ سفارش کمپینی → فقط هزینه تیم محتوا
                refund_amount = invoice.content_cost
                description = (
                    f'برگشت هزینه تیم محتوا سفارش #{order.id} '
                    f'({refund_amount:,} تومان) به دلیل رد سفارش توسط {order.team.name}'
                )

        # ========== ۴. واریز به کیف پول ==========
        if user and refund_amount > 0:
            wallet = user.wallet
            wallet.balance += refund_amount
            wallet.save(update_fields=['balance'])

            Transaction.objects.create(
                user=user,
                amount=refund_amount,
                type=Transaction.Type.CAMPAIGN_REFUND,
                status=Transaction.Status.SUCCESS,
                campaign=order.campaign,  # برای مستقل None
                invoice=invoice,
                description=description,
                reference_id=f'TEAM_REJECT_REFUND_{order.id}_{timezone.now().timestamp()}'
            )

        # ========== ۵. ارسال نوتیف ==========
        notify_advertiser_content_order_rejected(order)

        # ========== ۶. برای کمپین: حالت جایگزینی ==========
        if order.campaign:
            campaign = order.campaign
            campaign.status = Campaign.Status.REVISION_NEEDED
            campaign.content_team_rejected = True
            campaign.replacement_mode = True
            campaign.save(update_fields=['status', 'content_team_rejected', 'replacement_mode'])
        # برای مستقل: هیچ کار اضافه‌ای لازم نیست


def deliver_content_order_service(order, primary_delivery):
    """سرویس تحویل فایل سفارش (فقط برای نوتیف و امتیاز)"""
    if not primary_delivery:
        return None

    with transaction.atomic():
        display_name = get_order_display_name(order)

        # ========== امتیازدهی بر اساس ددلاین ==========
        if order.deadline:
            if timezone.now() <= order.deadline:
                update_score(
                    order.team, 30,
                    'تحویل به موقع',
                    f'تحویل به موقع فایل سفارش {display_name} قبل از ددلاین'
                )
            else:
                update_score(
                    order.team, -20,
                    'تحویل دیرکرد',
                    f'تحویل تاخیری فایل سفارش {display_name} بعد از ددلاین'
                )
        else:
            update_score(
                order.team, 20,
                'تحویل فایل سفارش',
                f'تحویل فایل سفارش {display_name}'
            )

        # ========== ارسال نوتیف ==========
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

        display_name = get_order_display_name(order)
        update_score(
            order.team, 10,
            'قبول درخواست ویرایش',
            f'پذیرش و انجام اصلاحیه {display_name}'
        )

        notify_advertiser_revision_accepted(revision)


def reject_revision_service(order, revision):
    """سرویس رد درخواست ویرایش توسط تیم محتوا (۳۰- امتیاز منفی)"""
    with transaction.atomic():
        revision.status = 'rejected'
        revision.save(update_fields=['status'])

        order.status = ContentOrder.Status.DONE
        order.save(update_fields=['status'])

        last_delivery = order.deliveries.first()
        if last_delivery:
            last_delivery.status = ContentDelivery.DeliveryStatus.DELIVERED
            last_delivery.save(update_fields=['status'])

        display_name = get_order_display_name(order)
        update_score(
            order.team, -30,
            'رد درخواست ویرایش',
            f'رد درخواست اصلاحیه {display_name}'
        )

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

    # ============================================================
    # تلاش برای واریز کمیسیون (بیرون از تراکنش)
    # ============================================================
    if campaign.status == Campaign.Status.COMPLETED:
        if hasattr(campaign, 'invoice'):
            _try_payout_commission(campaign.invoice)


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

            # ========== برگشت پول به کیف پول تبلیغ دهنده (فقط برای کمپین‌های غیر رایگان) ==========
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
                        new_influencer_vat = invoice.influencer_vat
                        new_content_vat = invoice.content_vat
                        new_commission_vat = invoice.commission_vat
                        new_total_vat = invoice.total_vat

                        if new_total_vat > 0:
                            ratio = old_vat / new_total_vat
                        else:
                            ratio = 1

                        invoice.influencer_vat = int(new_influencer_vat * ratio)
                        invoice.content_vat = int(new_content_vat * ratio)
                        invoice.commission_vat = int(new_commission_vat * ratio)
                        invoice.total_vat = old_vat

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

                # ========== نوتیف به تبلیغ دهنده ==========
                notify_advertiser_influencer_rejected(order)

            # ========== تغییر وضعیت کمپین به REVISION_NEEDED (فقط برای کمپین‌های غیر رایگان) ==========
            campaign = order.campaign

            if not campaign.is_free and campaign.status == Campaign.Status.APPROVED:
                campaign.status = Campaign.Status.REVISION_NEEDED
                campaign.replacement_mode = True
                campaign.save(update_fields=['status', 'replacement_mode'])

                notify_advertiser_campaign_needs_revision(campaign, order.channel)

                if settings.CELERY_ENABLED:
                    auto_approve_campaign_after_rejection.apply_async(
                        args=[campaign.id],
                        countdown=60 * 60 * 24
                    )

            # ========== امتیازدهی ==========
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

            # ========== برگشت پول به کیف پول تبلیغ دهنده ==========
            if not campaign.is_free and not campaign_influencer.is_paid and price > 0:
                # ۱. برگشت به کیف پول تبلیغ دهنده
                advertiser_wallet = advertiser_user.wallet
                advertiser_wallet.balance += price
                advertiser_wallet.save(update_fields=['balance'])

                # ۲. ثبت تراکنش برگشت برای تبلیغ دهنده
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

                # ========== نوتیف به تبلیغ دهنده ==========
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


def finalize_content_order(order, selected_file=None):
    """
    نهایی‌سازی سفارش تولید محتوا — هم برای کمپین، هم مستقل

    این تابع «مغز واحد» نهایی‌سازی هست. همه‌جا باید این صدا زده بشه.

    Args:
        order: ContentOrder
            سفارش تولید محتوا (کمپینی یا مستقل)

        selected_file: ContentDeliveryFile یا None
            - برای کمپین multi_choice: الزامی — فایلی که کاربر انتخاب کرده
            - برای کمپین single: اختیاری — اگه None باشه، اولین فایل آخرین تحویل
            - برای مستقل: همیشه None — اولین فایل آخرین تحویل خودکار انتخاب میشه

    Returns:
        dict: {
            'success': bool,
            'message': str,
            'paid_amount': int,
            'members_count': int,
            'final_file': ContentDeliveryFile یا None
        }
    """

    from content_team.models import ContentTeamMember
    from payment.models import Wallet

    # ============================================================
    # ۰. قفل کردن سفارش از ابتدا (جلوگیری از race condition)
    # ============================================================
    # ⚡ مهم: order رو دوباره از DB با قفل می‌خونیم
    # این کار باعث میشه اگه دو تا درخواست همزمان برسن،
    # دومی صبر کنه تا اولی تموم بشه، بعد چک کنه
    with transaction.atomic():
        locked_order = ContentOrder.objects.select_for_update().get(pk=order.pk)

        # از این به بعد از locked_order استفاده می‌کنیم (نه order)
        # چون locked_order نسخه‌ی قفل‌شده و به‌روزه
        order = locked_order

        # ============================================================
        # ۱. اعتبارسنجی اولیه (داخل قفل)
        # ============================================================
        if order.status != ContentOrder.Status.DONE:
            return {
                'success': False,
                'message': f'این سفارش در وضعیت "{order.get_status_display()}" است و قابل تأیید نیست.',
                'paid_amount': 0,
                'members_count': 0,
                'final_file': None,
            }

        if order.has_selected_file():
            return {
                'success': False,
                'message': 'این سفارش قبلاً تأیید نهایی شده است.',
                'paid_amount': 0,
                'members_count': 0,
                'final_file': None,
            }

        # ============================================================
        # ۲. تشخیص فایل نهایی بر اساس نوع سفارش
        # ============================================================
        last_delivery = order.deliveries.order_by('-version').first()

        if not last_delivery:
            return {
                'success': False,
                'message': 'هیچ تحویلی برای این سفارش ثبت نشده است.',
                'paid_amount': 0,
                'members_count': 0,
                'final_file': None,
            }

        is_campaign_order = order.campaign is not None
        is_multi_choice = (
                order.plan and
                order.plan.delivery_type == ContentServicePlan.DeliveryType.MULTI_CHOICE
        )

        final_file = None

        # ---------- حالت ۱: سفارش کمپینی + multi_choice ----------
        if is_campaign_order and is_multi_choice:
            if not selected_file:
                return {
                    'success': False,
                    'message': 'برای این سفارش باید یکی از گزینه‌ها انتخاب شود.',
                    'paid_amount': 0,
                    'members_count': 0,
                    'final_file': None,
                }

            if selected_file.delivery.order_id != order.id:
                return {
                    'success': False,
                    'message': 'فایل انتخاب شده متعلق به این سفارش نیست.',
                    'paid_amount': 0,
                    'members_count': 0,
                    'final_file': None,
                }

            if not selected_file.is_option:
                return {
                    'success': False,
                    'message': 'فایل انتخاب شده از نوع گزینه (option) نیست.',
                    'paid_amount': 0,
                    'members_count': 0,
                    'final_file': None,
                }

            final_file = selected_file

        # ---------- حالت ۲: سفارش کمپینی + single ----------
        elif is_campaign_order and not is_multi_choice:
            final_file = last_delivery.files.first()

            if not final_file or not final_file.file:
                return {
                    'success': False,
                    'message': 'فایلی برای تأیید نهایی وجود ندارد.',
                    'paid_amount': 0,
                    'members_count': 0,
                    'final_file': None,
                }

        # ---------- حالت ۳: سفارش مستقل ----------
        else:
            final_file = last_delivery.files.first()

            if not final_file or not final_file.file:
                return {
                    'success': False,
                    'message': 'فایلی برای تأیید نهایی وجود ندارد.',
                    'paid_amount': 0,
                    'members_count': 0,
                    'final_file': None,
                }

        # ============================================================
        # ۳. محاسبه مبلغ قابل پرداخت به تیم
        # ============================================================
        invoice = get_order_invoice(order)

        if not invoice and order.is_standalone and hasattr(order, 'invoice'):
            invoice = order.invoice

        content_cost = invoice.content_cost if invoice and invoice.content_cost else order.price

        if content_cost <= 0:
            return {
                'success': False,
                'message': 'مبلغ تولید محتوا معتبر نیست.',
                'paid_amount': 0,
                'members_count': 0,
                'final_file': None,
            }

        # ============================================================
        # ۴. اعتبارسنجی اعضای تیم
        # ============================================================
        team_members = ContentTeamMember.objects.filter(
            team=order.team,
            is_active=True
        ).select_related('user')

        if not team_members.exists():
            return {
                'success': False,
                'message': 'هیچ عضو فعالی در تیم وجود ندارد.',
                'paid_amount': 0,
                'members_count': 0,
                'final_file': None,
            }

        total_percent = sum(member.revenue_share_percent for member in team_members)

        if total_percent != 100:
            return {
                'success': False,
                'message': f'مجموع درصد سهام اعضای تیم باید ۱۰۰ باشد (در حال حاضر: {total_percent}%).',
                'paid_amount': 0,
                'members_count': 0,
                'final_file': None,
            }

        # ============================================================
        # ۵. اجرای عملیات (همه داخل همون تراکنش)
        # ============================================================

        # ---------- ۵.۱. علامت‌گذاری فایل نهایی ----------
        final_file.is_selected = True
        final_file.save(update_fields=['is_selected'])

        # ---------- ۵.۱.۱. ساخت خودکار نمونه کار ----------
        try:
            create_portfolio_from_order(order, final_file)
        except Exception as e:
            logger.warning(f'ساخت نمونه کار برای سفارش #{order.id} ناموفق: {e}')

        # ---------- ۵.۲. تقسیم پول بین اعضای تیم ----------
        members_paid = 0
        total_paid = 0

        for member in team_members:
            share_amount = int((content_cost * member.revenue_share_percent) / 100)
            if share_amount <= 0:
                continue

            wallet, _ = Wallet.objects.get_or_create(user=member.user)
            wallet.balance += share_amount
            wallet.save(update_fields=['balance'])

            Transaction.objects.create(
                user=member.user,
                amount=share_amount,
                type=Transaction.Type.TEAM_PAYMENT,
                status=Transaction.Status.SUCCESS,
                campaign=order.campaign,
                invoice=invoice,
                team_member=member,
                description=(
                    f'پرداخت سهم از سفارش #{order.id} - '
                    f'تیم {order.team.name} - '
                    f'{member.revenue_share_percent}% - '
                    f'مبلغ: {share_amount:,} تومان'
                )
            )

            try:
                notify_content_team_order_accepted(member.user, order, share_amount)
            except Exception:
                pass

            members_paid += 1
            total_paid += share_amount

        # ---------- ۵.۳. بونوس بدون ویرایش ----------
        has_revisions = ContentOrderRevision.objects.filter(order=order).exists()
        if not has_revisions:
            display_name = get_order_display_name(order)
            update_score(
                order.team, 30,
                'تایید نهایی بدون درخواست ویرایش',
                f'تایید نهایی سفارش {display_name} بدون هیچ درخواست اصلاحیه‌ای'
            )

        # ---------- ۵.۴. آپدیت دلیوری ----------
        last_delivery.status = ContentDelivery.DeliveryStatus.FINAL_ACCEPTED
        last_delivery.accepted_at = timezone.now()
        last_delivery.save(update_fields=['status', 'accepted_at'])

        # ---------- ۵.۵. آپدیت وضعیت سفارش ----------
        order.status = ContentOrder.Status.COMPLETED
        order.save(update_fields=['status'])

        # ---------- ۵.۶. مخصوص کمپین ----------
        if is_campaign_order:
            campaign = order.campaign

            campaign_content, created = CampaignContent.objects.get_or_create(
                campaign=campaign,
                defaults={
                    'media': final_file.file,
                    'notes': f'محتوای تولید شده توسط تیم {order.team.name}',
                }
            )

            if not created:
                campaign_content.media = final_file.file
                campaign_content.notes = (
                    f'محتوای تولید شده توسط تیم {order.team.name} '
                    f'در تاریخ {timezone.now()}'
                )
                campaign_content.save(update_fields=['media', 'notes'])

            if campaign.content_type.slug == 'content-production-team':
                influencer_counts = defaultdict(int)
                bookings = campaign.influencer_bookings.select_related(
                    'channel__influencer__user'
                )
                for booking in bookings:
                    user = booking.channel.influencer.user
                    influencer_counts[user] += 1

                for user, count in influencer_counts.items():
                    try:
                        notify_influencer_new_campaign_orders(user, campaign, count)
                    except Exception:
                        pass

    # ============================================================
    # ۶. تلاش برای واریز کمیسیون (بیرون از تراکنش اصلی)
    # ============================================================
    if invoice:
        _try_payout_commission(invoice, order=order)

    # ============================================================
    # ۷. بازگشت نتیجه
    # ============================================================
    return {
        'success': True,
        'message': (
            f'سفارش #{order.id} با موفقیت تأیید شد. '
            f'مبلغ {total_paid:,} تومان بین {members_paid} عضو تیم تقسیم شد.'
        ),
        'paid_amount': total_paid,
        'members_count': members_paid,
        'final_file': final_file,
    }