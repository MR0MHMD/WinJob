from .models import Notification


def create_notification(user, notification_type, title, message, link='', related_object_id=None,
                        related_content_type=''):
    """تابع اصلی ساخت نوتیفیکیشن"""
    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        link=link,
        related_object_id=related_object_id,
        related_content_type=related_content_type
    )


# ==================== تبلیغ‌دهنده ====================

def notify_advertiser_campaign_pending(campaign):
    """وقتی کاربر کمپین رو ساخته و در انتظار تایید هست"""
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='campaign_pending',
        title='📝 کمپین در انتظار تایید',
        message=f'کمپین "{campaign.name}" با موفقیت ثبت شد. در حال بررسی توسط ادمین...',
        link='/dashboard/my-campaigns/',  # صفحه تبلیغات من
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_campaign_approved(campaign):
    """وقتی کمپین کاربر تایید میشه"""
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='campaign_approved',
        title='✅ کمپین شما تایید شد!',
        message=f'کمپین "{campaign.name}" تایید شد و به زودی اجرا خواهد شد.',
        link=f'/campaigns/{campaign.id}/',  # جزئیات کمپین
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_campaign_rejected(campaign, reason=''):
    """وقتی کمپین رد میشه"""
    user = campaign.advertiser.user
    message = f'کمپین "{campaign.name}" تایید نشد.'
    if reason:
        message += f' دلیل: {reason}'

    return create_notification(
        user=user,
        notification_type='campaign_rejected',
        title='❌ کمپین شما تایید نشد',
        message=message,
        link=f'/campaigns/{campaign.id}/',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_influencer_accepted(campaign_influencer):
    """وقتی اینفلوئنسر تبلیغ رو قبول میکنه"""
    campaign = campaign_influencer.campaign
    user = campaign.advertiser.user
    channel = campaign_influencer.channel

    return create_notification(
        user=user,
        notification_type='influencer_accepted',
        title='🎯 اینفلوئنسر سفارش را قبول کرد',
        message=f'{channel.influencer.full_name} ({channel.channel_id}) درخواست شما برای کمپین "{campaign.name}" را پذیرفت.',
        link=f'/campaigns/{campaign.id}/',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_report_approved(campaign_influencer):
    """وقتی اینفلوئنسر گزارش فرستاد و ادمین تایید کرد"""
    campaign = campaign_influencer.campaign
    user = campaign.advertiser.user
    channel = campaign_influencer.channel

    return create_notification(
        user=user,
        notification_type='influencer_report_approved',
        title='📊 گزارش اینفلوئنسر تایید شد',
        message=f'گزارش عملکرد {channel.influencer.full_name} برای کمپین "{campaign.name}" توسط ادمین تایید شد.',
        link=f'/campaigns/{campaign.id}/',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


def notify_advertiser_ticket_answered(ticket):
    """وقتی تیکت پاسخ داده شد"""
    user = ticket.user
    return create_notification(
        user=user,
        notification_type='ticket_answered',
        title='💬 پاسخ تیکت شما',
        message=f'تیکت شما با موضوع "{ticket.subject}" پاسخ داده شد.',
        link=f'/tickets/{ticket.id}/',
        related_object_id=ticket.id,
        related_content_type='Ticket'
    )


def notify_advertiser_campaign_completed(campaign):
    """وقتی کمپین با موفقیت تموم شد"""
    user = campaign.advertiser.user
    return create_notification(
        user=user,
        notification_type='campaign_completed',
        title='🏁 کمپین به پایان رسید',
        message=f'کمپین "{campaign.name}" با موفقیت به پایان رسید. از مشارکت شما متشکریم.',
        link=f'/campaigns/{campaign.id}/',
        related_object_id=campaign.id,
        related_content_type='Campaign'
    )


# ==================== اینفلوئنسر ====================

def notify_influencer_new_order(campaign_influencer):
    """سفارش جدید برای اینفلوئنسر"""
    user = campaign_influencer.channel.influencer.user
    campaign = campaign_influencer.campaign

    return create_notification(
        user=user,
        notification_type='new_order',
        title='📢 سفارش جدید دارید!',
        message=f'یک سفارش جدید برای کمپین "{campaign.name}" از طرف {campaign.advertiser.business_name} دریافت کردید.',
        link=f'/influencer/orders/{campaign_influencer.id}/',
        related_object_id=campaign_influencer.id,
        related_content_type='CampaignInfluencer'
    )


def notify_influencer_penalty(campaign_influencer, amount, reason):
    """وقتی اینفلوئنسر جریمه میشه"""
    user = campaign_influencer.channel.influencer.user
    campaign = campaign_influencer.campaign

    return create_notification(
        user=user,
        notification_type='penalty',
        title='⚠️ جریمه',
        message=f'برای کمپین "{campaign.name}" به مبلغ {amount:,} تومان جریمه شدید. دلیل: {reason}',
        link=f'/influencer/orders/{campaign_influencer.id}/',
        related_object_id=campaign_influencer.id,
        related_content_type='CampaignInfluencer'
    )


def notify_influencer_report_approved(campaign_influencer):
    """وقتی گزارش اینفلوئنسر توسط ادمین تایید میشه"""
    user = campaign_influencer.channel.influencer.user
    campaign = campaign_influencer.campaign

    return create_notification(
        user=user,
        notification_type='report_approved',
        title='✅ گزارش شما تایید شد',
        message=f'گزارش شما برای کمپین "{campaign.name}" تایید شد. مبلغ به کیف پول شما واریز خواهد شد.',
        link=f'/influencer/orders/{campaign_influencer.id}/',
        related_object_id=campaign_influencer.id,
        related_content_type='CampaignInfluencer'
    )


def notify_influencer_wallet_deposit(transaction):
    """وقتی پول به کیف پول اینفلوئنسر واریز میشه"""
    user = transaction.user
    return create_notification(
        user=user,
        notification_type='wallet_deposit',
        title='💰 واریز به کیف پول',
        message=f'مبلغ {transaction.amount:,} تومان به کیف پول شما واریز شد.',
        link='/dashboard/wallet/',
        related_object_id=transaction.id,
        related_content_type='Transaction'
    )


def notify_influencer_withdrawal_success(withdrawal_request):
    """وقتی با موفقیت پول رو از کیف پول برداشت میکنه"""
    user = withdrawal_request.user
    return create_notification(
        user=user,
        notification_type='withdrawal_success',
        title='✅ برداشت موفق',
        message=f'درخواست برداشت شما به مبلغ {withdrawal_request.amount:,} تومان با موفقیت انجام شد.',
        link='/dashboard/wallet/withdrawals/',
        related_object_id=withdrawal_request.id,
        related_content_type='WithdrawalRequest'
    )


# ==================== تیم تولید محتوا ====================

def notify_content_team_new_order(content_order):
    """وقتی سفارش محتوا جدید داره"""
    # به همه اعضای فعال تیم نوتیف میدیم
    notifications = []
    for member in content_order.team.members.filter(is_active=True):
        notif = create_notification(
            user=member.user,
            notification_type='new_content_order',
            title='📦 سفارش محتوا جدید',
            message=f'یک سفارش جدید برای کمپین "{content_order.campaign.name}" دریافت کردید.',
            link=f'/team/orders/{content_order.id}/',
            related_object_id=content_order.id,
            related_content_type='ContentOrder'
        )
        notifications.append(notif)
    return notifications


def notify_content_team_revision_requested(content_order):
    """وقتی کاربر درخواست ویرایش داده روی سفارش"""
    # به همه اعضای فعال تیم
    notifications = []
    for member in content_order.team.members.filter(is_active=True):
        notif = create_notification(
            user=member.user,
            notification_type='revision_requested',
            title='✏️ درخواست ویرایش سفارش',
            message=f'برای سفارش کمپین "{content_order.campaign.name}" درخواست ویرایش داده شده است.',
            link=f'/team/orders/{content_order.id}/',
            related_object_id=content_order.id,
            related_content_type='ContentOrder'
        )
        notifications.append(notif)
    return notifications


def notify_content_team_final_accepted(content_order):
    """وقتی کاربر تایید نهایی داده روی سفارش"""
    notifications = []
    for member in content_order.team.members.filter(is_active=True):
        notif = create_notification(
            user=member.user,
            notification_type='final_accepted',
            title='✅ تایید نهایی سفارش',
            message=f'سفارش کمپین "{content_order.campaign.name}" توسط کاربر تایید نهایی شد.',
            link=f'/team/orders/{content_order.id}/',
            related_object_id=content_order.id,
            related_content_type='ContentOrder'
        )
        notifications.append(notif)
    return notifications


def notify_content_team_wallet_deposit(transaction, team):
    """وقتی پول به حساب تیم واریز میشه"""
    notifications = []
    for member in team.members.filter(is_active=True):
        notif = create_notification(
            user=member.user,
            notification_type='content_wallet_deposit',
            title='💰 واریز به حساب تیم',
            message=f'مبلغ {transaction.amount:,} تومان به حساب تیم {team.name} واریز شد.',
            link='/team/wallet/',
            related_object_id=transaction.id,
            related_content_type='Transaction'
        )
        notifications.append(notif)
    return notifications


def notify_content_team_withdrawal_success(withdrawal_request, team):
    """وقتی با موفقیت پول رو از کیف پول تیم برداشت میکنه"""
    notifications = []
    for member in team.members.filter(is_active=True):
        notif = create_notification(
            user=member.user,
            notification_type='content_withdrawal_success',
            title='✅ برداشت موفق تیم',
            message=f'درخواست برداشت تیم {team.name} به مبلغ {withdrawal_request.amount:,} تومان با موفقیت انجام شد.',
            link='/team/wallet/withdrawals/',
            related_object_id=withdrawal_request.id,
            related_content_type='WithdrawalRequest'
        )
        notifications.append(notif)
    return notifications
