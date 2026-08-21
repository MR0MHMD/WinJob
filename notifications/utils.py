from .models import Notification, NotificationPreference
from influencers.models import ChannelBooking
from django.conf import settings
import threading
import requests


def send_bale_message_async(chat_id, text):
    # (همون کدهای قبلی خودت برای بله اینجا قرار میگیره)
    def _send():
        token = settings.BALE_BOT_TOKEN
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "HTML"}
        headers = {"User-Agent": "BaleBot/1.0", "Content-Type": "application/json"}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10.0)
            if response.status_code == 200:
                print("DEBUG: Message sent successfully via TAPI!")
            else:
                print(f"DEBUG: FAILED! Status Code: {response.status_code}")
        except Exception as e:
            print(f"DEBUG: ERROR: {e}")

    threading.Thread(target=_send, daemon=True).start()


def create_notification(user, notification_type, title, message, link='', related_object_id=None,
                        related_content_type=''):
    """تابع اصلی ساخت نوتیفیکیشن در دیتابیس و ارسال هوشمند به ربات بله"""

    prefs, created = NotificationPreference.objects.get_or_create(user=user)

    # ========== فیلتر کردن هوشمند بر اساس تنظیمات کاربر ==========
    # تبلیغ دهنده
    if notification_type in ['campaign_pending', 'campaign_approved', 'campaign_rejected', 'campaign_updates',
                             'campaign_completed']:
        if not prefs.adv_campaign_status: return None
    elif notification_type == 'influencer_accepted':
        if not prefs.adv_influencer_actions: return None
    elif notification_type in ['content_accepted', 'content_rejected', 'content_delivered', 'revision_accepted',
                               'revision_rejected']:
        if not prefs.adv_content_orders: return None

    # ناشر (اینفلوئنسر)
    elif notification_type == 'new_order':
        if not prefs.inf_new_orders: return None
    elif notification_type in ['report_approved', 'penalty']:  # از penalty برای رد گزارش استفاده شده
        if not prefs.inf_report_status: return None

    # تیم تولید محتوا
    elif notification_type == 'new_content_order':
        if not prefs.team_new_orders: return None
    elif notification_type == 'revision_requested':
        if not prefs.team_revisions: return None
    elif notification_type == 'order_accepted':
        if not prefs.team_financial: return None

    # عمومی
    elif notification_type in ['wallet_deposit', 'withdrawal_success', 'content_wallet_deposit',
                               'content_withdrawal_success']:
        if not prefs.financial_alerts: return None
    elif notification_type == 'ticket_answered':
        if not prefs.ticket_replies: return None

    # ========== ساخت نوتیف در دیتابیس ==========
    notification = Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        link=link,
        related_object_id=related_object_id,
        related_content_type=related_content_type
    )

    # ========== ارسال به بله ==========
    if user.bale_chat_id and prefs.receive_in_bale:
        bale_text = f"<b>{title}</b>\n\n{message}"
        if link:
            bale_text += f"\n\n🔗 <b>مشاهده در پنل کاربری:</b>\n{settings.SITE_URL}{link}"
        send_bale_message_async(user.bale_chat_id, bale_text)

    return notification


# ==================== 🎯 تبلیغ دهنده ====================

def notify_advertiser_campaign_pending(campaign):
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='campaign_pending',
        title='✅ کمپین شما با موفقیت ثبت شد',
        message=f'کمپین «{campaign.name}» با موفقیت ساخته شد و هم اکنون در انتظار تایید میباشد.\n'
                f'کارشناس های ما نهایتا تا ۲۴ ساعت آینده کمپین شما را بررسی خواهند کرد.\n'
                f'از شما ممنونیم که به وینجاب اعتماد کردید. 🤝',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_campaign_approved(campaign):
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='campaign_approved',
        title='🎉 تبریک، کمپین شما تأیید شد',
        message=f'خبر خوب! کمپین «{campaign.name}» با موفقیت تأیید شد.\n'
                f'به زودی در دسترس ناشران قرار می‌گیرد تا فرایند اکران آغاز شود.',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_campaign_rejected(campaign, reason=''):
    user = campaign.advertiser.user
    message = f'متأسفانه کمپین «{campaign.name}» تأیید نشد.\n'
    if reason:
        message += f'📌 دلیل رد شدن: {reason}\n'
    message += 'لطفاً اصلاحات لازم را انجام دهید تا دوباره بررسی کنیم.'
    return create_notification(
        user=user,
        notification_type='campaign_rejected',
        title='🛑 نیاز به اصلاح کمپین',
        message=message,
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_ticket_answered(ticket):
    user = ticket.user
    return create_notification(
        user=user,
        notification_type='ticket_answered',
        title='💬 پاسخ جدید از پشتیبانی',
        message=f'تیکت شما با موضوع «{ticket.subject}» پاسخ داده شد.\n'
                f'برای مشاهده پاسخ روی لینک زیر کلیک کنید.',
        link=f'/tickets/{ticket.id}/',
        related_object_id=ticket.id,
        related_content_type='Ticket'
    )


def notify_advertiser_campaign_running(campaign):
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='campaign_running',
        title='🚀 آغاز اکران کمپین',
        message=f'مژده! کمپین «{campaign.name}» رسماً وارد فاز اکران و نمایش شد.\n امیدواریم نتایج درخشانی کسب کنید.',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_campaign_completed(campaign):
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='campaign_completed',
        title='🏁 پایان موفقیت‌آمیز کمپین',
        message=f'خسته نباشید! کمپین «{campaign.name}» با موفقیت به پایان رسید.\n'
                f'امیدواریم از نتایج رضایت داشته باشید. منتظر کمپین‌های بعدی شما هستیم و از همکاری با شما لذت بردیم',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_influencer_accepted(campaign_influencer):
    campaign = campaign_influencer.campaign
    user = campaign.advertiser.user
    channel = campaign_influencer.channel
    return create_notification(
        user=user,
        notification_type='influencer_accepted',
        title='🤝 پیوستن یک ناشر جدید',
        message=f'ناشر «{channel.channel_name}» (شناسه کانال: {channel.channel_id}@) درخواست شما را برای کمپین «تست تکمیلی نوتیف» پذیرفت.» پذیرفت.',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_influencer_rejected(campaign_influencer):
    """
    نوتیف به تبلیغ دهنده وقتی ناشر سفارش رو رد میکنه
    """
    campaign = campaign_influencer.campaign
    user = campaign.advertiser.user
    channel = campaign_influencer.channel
    price = campaign_influencer.price

    if campaign.is_free:
        return None

    return create_notification(
        user=user,
        notification_type='influencer_rejected',  # این تایپ رو باید به Notification.Type اضافه کنی
        title='❌ رد سفارش توسط ناشر',
        message=f'ناشر «{channel.channel_name}» (شناسه کانال: {channel.channel_id}@) سفارش شما برای کمپین «{campaign.name}» را رد کرد.\n'
                f'💰 مبلغ {price:,} تومان به کیف پول شما برگشت داده شد.\n'
                f'برای انتخاب ناشر جایگزین، روی لینک زیر کلیک کنید.',
        link=f'/campaigns/select-replacement/{campaign.id}/',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )



def notify_advertiser_influencer_report_rejected(campaign_influencer, reason=''):
    """
    نوتیف به تبلیغ دهنده وقتی گزارش ناشر توسط ادمین رد میشه
    """
    campaign = campaign_influencer.campaign
    user = campaign.advertiser.user
    channel = campaign_influencer.channel
    price = campaign_influencer.price

    if campaign.is_free:
        return None

    message = f'گزارش ناشر «{channel.channel_name}» (شناسه کانال: {channel.channel_id}@) برای کمپین «{campaign.name}» توسط ادمین رد شد.\n'
    if reason:
        message += f'📌 دلیل رد: {reason}\n'
    message += f'💰 مبلغ {price:,} تومان به کیف پول شما برگشت داده شد.\n\n'

    return create_notification(
        user=user,
        notification_type='influencer_report_rejected',
        title='❌ رد گزارش ناشر توسط ادمین',
        message=message,
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_campaign_needs_revision(campaign, rejected_channel=None):
    """نوتیف به تبلیغ دهنده وقتی کمپین نیاز به اصلاح دارد"""
    user = campaign.advertiser.user

    channel_name = rejected_channel.channel_name if rejected_channel else "یک ناشر"
    message = f'ناشر «{channel_name}» سفارش شما برای کمپین «{campaign.name}» را رد کرد.\n'
    message += f'💰 مبلغ مربوطه به کیف پول شما برگشت داده شد.\n\n'
    message += '🔄 دو گزینه پیش روی شماست:\n'
    message += '1️⃣ انتخاب ناشر جایگزین\n'
    message += '2️⃣ ادامه کمپین بدون جایگزینی (ناشران رد شده نادیده گرفته می‌شوند)\n\n'
    message += '⚠️ در صورت عدم اقدام تا ۲۴ ساعت، گزینه ۲ به طور خودکار انتخاب خواهد شد.'

    return create_notification(
        user=user,
        notification_type='campaign_needs_revision',
        title='🔄 کمپین نیاز به اصلاح دارد',
        message=message,
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_campaign_auto_approved(campaign):
    """نوتیف به تبلیغ دهنده وقتی کمپین به صورت خودکار تایید شد"""
    user = campaign.advertiser.user

    rejected_count = campaign.influencer_bookings.filter(
        status=ChannelBooking.Status.REJECTED
    ).count()

    message = f'🔔 کمپین «{campaign.name}» به صورت خودکار و پس از گذشت ۲۴ ساعت از رد شدن {rejected_count} ناشر، ادامه یافت.\n'
    message += 'ناشران رد شده نادیده گرفته شده‌اند و روند کمپین ادامه پیدا میکند.'

    return create_notification(
        user=user,
        notification_type='campaign_auto_approved',
        title='✅ ادامه خودکار کمپین',
        message=message,
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_content_order_accepted(order):
    campaign = order.campaign
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='content_accepted',
        title='✅ تیم تولید محتوا سفارشت رو قبول کرد',
        message=f'تیم محتوای «{order.team.name}» سفارش شما برای کمپین «{campaign.name}» را تحویل گرفت و کار را شروع کرد. به زودی خروجی نهایی ارسال خواهد شد.',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=order.id,
        related_content_type='ContentOrder'
    )


def notify_advertiser_content_order_rejected(campaign, team=None):
    """نوتیف به تبلیغ دهنده وقتی تیم محتوا سفارش رو رد میکنه"""
    user = campaign.advertiser.user

    team_name = team.name if team else "تیم تولید محتوا"
    content_cost = campaign.invoice.content_cost if campaign.invoice and campaign.invoice.content_cost else 0

    message = f'تیم تولید محتوا «{team_name}» سفارش شما برای کمپین «{campaign.name}» را رد کرد.\n'
    message += f'💰 مبلغ {content_cost:,} تومان به کیف پول شما برگشت داده شد.\n\n'
    message += '🔄 دو گزینه پیش روی شماست:\n'
    message += '1️⃣ انتخاب تیم تولید محتوای جایگزین\n'
    message += '2️⃣ آپلود محتوای آماده (بدون نیاز به تیم تولید محتوا)'

    return create_notification(
        user=user,
        notification_type='content_rejected',
        title='🔄 تیم محتوا سفارش را رد کرد - نیاز به اصلاح',
        message=message,
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_content_delivered(delivery):
    order = delivery.order
    campaign = order.campaign
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='content_delivered',
        title='🎁 محتوای شما آماده است',
        message=f'تیم «{order.team.name}» فایل نهایی (نسخه {delivery.version}) کمپین «{campaign.name}» را بارگذاری کرد.\n'
                f'لطفاً فایل را بررسی کنید تا در صورت نیاز به ویرایش، به تیم اطلاع دهید.',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=delivery.id,
        related_content_type='ContentDelivery'
    )


def notify_advertiser_revision_accepted(revision):
    order = revision.order
    campaign = order.campaign
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='revision_accepted',
        title='✍️ در حال انجام ویرایش',
        message=f'تیم «{order.team.name}» درخواست ویرایش شما برای کمپین «{campaign.name}» را پذیرفت. فایل به‌روزرسانی‌شده به زودی ارسال می‌شود.',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=revision.id,
        related_content_type='ContentOrderRevision'
    )


def notify_advertiser_revision_rejected(revision):
    order = revision.order
    campaign = order.campaign
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='revision_rejected',
        title='🛑 رد درخواست ویرایش',
        message=f'تیم «{order.team.name}» درخواست ویرایش شما برای کمپین «{campaign.name}» را رد کرد. سفارش به حالت پایان‌یافته بازگشت.',
        link=f'/advertisers/campaign_detail/{campaign.id}',
        related_object_id=revision.id,
        related_content_type='ContentOrderRevision'
    )


# ==================== 🌟 اینفلوئنسر ====================

def notify_influencer_new_campaign_orders(user, campaign, channels_count):
    type_name = "پیج" if campaign.platform.slug == "instagram" else "کانال"
    if channels_count == 1:
        if campaign.is_free:
            message = f'یکی از {type_name}‌های شما برای کمپین عام المنفعه«{campaign.name}» انتخاب شده است. لطفاً در اسرع وقت بررسی کنید.'
        else:
            message = f'یکی از {type_name}‌های شما برای کمپین «{campaign.name}» انتخاب شده است. لطفاً در اسرع وقت بررسی کنید.'
    else:
        if campaign.is_free:
            message = f'تعداد {channels_count} {type_name} از شما برای کمپین عام المنفعه«{campaign.name}» انتخاب شده‌اند. وارد پنل شوید و سفارش‌ها را تأیید کنید.'
        else:
            message = f'تعداد {channels_count} {type_name} از شما برای کمپین «{campaign.name}» انتخاب شده‌اند. وارد پنل شوید و سفارش‌ها را تأیید کنید.'
    return create_notification(
        user=user,
        notification_type='new_order',
        title=f'📲 یک سفارش جدید دارید',
        message=message,
        link='/influencers/order_list',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_influencer_report_approved(campaign_influencer):
    user = campaign_influencer.channel.influencer.user
    campaign = campaign_influencer.campaign
    channel = campaign_influencer.channel
    price = campaign_influencer.price
    return create_notification(
        user=user,
        notification_type='report_approved',
        title='💰 تأیید گزارش و واریز مبلغ',
        message=f'گزارش کانال «{channel.channel_name}» برای کمپین «{campaign.name}» با موفقیت تأیید شد.\n'
                f'مبلغ {price:,} تومان به کیف پول شما واریز شد.',
        link=f'/influencers/order_detail/{campaign_influencer.id}',
        related_object_id=campaign_influencer.id,
        related_content_type='ChannelBooking'
    )


def notify_influencer_report_rejected(campaign_influencer, reason=''):
    user = campaign_influencer.channel.influencer.user
    campaign = campaign_influencer.campaign
    channel = campaign_influencer.channel
    message = f'گزارش کانال «{channel.channel_name}» برای کمپین «{campaign.name}» تأیید نشد.\n'
    if reason:
        message += f'📌 دلیل: {reason}\n'
    message += 'لطفاً گزارش را اصلاح کرده و دوباره ارسال کنید.'

    return create_notification(
        user=user,
        notification_type='influencer_report_rejected',
        title='گزارش شما متاسفانه تایید نشد ❌',
        message=message,
        link=f'/influencers/order_detail/{campaign_influencer.id}',
        related_object_id=campaign_influencer.id,
        related_content_type='ChannelBooking'
    )


# ==================== 🎨 تیم تولید محتوا ====================

def notify_content_team_new_order(user, order):
    campaign = order.campaign
    plan = order.plan
    service_type = plan.service_type
    return create_notification(
        user=user,
        notification_type='new_content_order',
        title='💼 پروژه جدید برای شما',
        message=f'یک سفارش جدید برای کمپین «{campaign.name}» ثبت شده است.\n'
                f'🛠 نوع خدمت: {service_type.name}\n'
                f'📄 پلن انتخابی: {plan.name}\n'
                f'لطفاً وارد پنل شده و آن را بررسی کنید.',
        link=f'/content_team/team/orders/{order.id}',
        related_object_id=order.id,
        related_content_type='ContentOrder'
    )


def notify_content_team_revision_requested(user, revision):
    order = revision.order
    campaign = order.campaign
    feedback_excerpt = revision.feedback[:80] + "..." if len(revision.feedback) > 80 else revision.feedback
    return create_notification(
        user=user,
        notification_type='revision_requested',
        title='🛠️ درخواست ویرایش از سوی کارفرما',
        message=f'کارفرمای شما فایل کمپین «{campaign.name}» را بررسی کرده و درخواست ویرایش دارد.\n'
                f'📌 توضیحات: {feedback_excerpt}',
        link=f'/content_team/team/orders/{order.id}',
        related_object_id=revision.id,
        related_content_type='ContentOrderRevision'
    )


def notify_content_team_order_accepted(user, order, share_amount):
    campaign = order.campaign
    return create_notification(
        user=user,
        notification_type='final_accept',
        title='💳 تسویه حساب، خسته نباشید',
        message=f'فایل تحویلی کمپین «{campaign.name}» توسط تبلیغ دهنده تأیید نهایی شد.\n'
                f'مبلغ {share_amount:,} تومان بابت سهم شما از این پروژه به کیف پول واریز شد.',
        link=f'/content_team/team/orders/{order.id}',
        related_object_id=order.id,
        related_content_type='ContentOrder'
    )
