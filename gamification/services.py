# gamification/services.py

from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import PointLog, TeamScore, ChannelScore, AdvertiserScore, Badge
from accounts.models import Transaction, Wallet


@transaction.atomic
def update_score(target_instance, points, action_key, description):
    """
    ثبت امتیاز جدید (مثبت یا منفی) برای موجودیت‌های مختلف (تیم، کانال، تبلیغ‌دهنده)
    """
    if points == 0:
        return

    score_obj = _get_or_create_score_profile(target_instance)
    score_obj.points += points
    if score_obj.points < 0:
        score_obj.points = 0
    score_obj.save()

    PointLog.objects.create(
        content_type=ContentType.objects.get_for_model(score_obj),
        object_id=score_obj.id,
        points_changed=points,
        action_key=action_key,
        description=description
    )

    _evaluate_badge_and_reward(score_obj)


def _get_or_create_score_profile(target_instance):
    """بازگرداندن یا ایجاد شیء امتیاز مرتبط با موجودیت ورودی"""
    model_name = target_instance.__class__.__name__
    if model_name == 'ContentTeam':
        score, _ = TeamScore.objects.get_or_create(team=target_instance)
    elif model_name == 'InfluencerChannel':
        score, _ = ChannelScore.objects.get_or_create(channel=target_instance)
    elif model_name == 'AdvertiserProfile':
        score, _ = AdvertiserScore.objects.get_or_create(profile=target_instance)
    else:
        raise ValueError("نوع موجودیت برای سیستم امتیازدهی معتبر نیست.")
    return score


def _evaluate_badge_and_reward(score_obj):
    """بررسی سطح فعلی و ارتقا/تنزل نشان و پرداخت جایزه"""
    current_points = score_obj.points

    badges = Badge.objects.filter(is_active=True).order_by('-min_points')
    if not badges.exists():
        return

    new_badge = badges.last()

    for badge in badges:
        if current_points >= badge.min_points:
            new_badge = badge
            break

    if score_obj.badge and score_obj.badge.id == new_badge.id:
        return

    old_badge = score_obj.badge
    score_obj.badge = new_badge

    if not old_badge or new_badge.order > old_badge.order:
        if not score_obj.highest_badge or new_badge.order > score_obj.highest_badge.order:
            score_obj.highest_badge = new_badge

    score_obj.save()


def _deposit_reward(score_obj, amount, badge_name):
    """واریز جایزه به کیف پول کاربر(ها)"""
    description = f"جایزه ارتقا به نشان {badge_name}"

    if isinstance(score_obj, TeamScore):
        members = score_obj.team.members.filter(is_active=True)
        if members.exists():
            split_amount = amount // members.count()
            for member in members:
                _add_to_wallet(member.user, split_amount, description)
    elif isinstance(score_obj, ChannelScore):
        user = score_obj.channel.influencer.user
        _add_to_wallet(user, amount, description)
    elif isinstance(score_obj, AdvertiserScore):
        user = score_obj.profile.user
        _add_to_wallet(user, amount, description)


def _add_to_wallet(user, amount, description):
    """افزایش موجودی کیف پول کاربر و ثبت تراکنش"""
    Transaction.objects.create(
        user=user,
        amount=amount,
        type=Transaction.Type.DEPOSIT,
        status=Transaction.Status.SUCCESS,
        description=description
    )
    wallet = user.wallet
    wallet.balance += amount
    wallet.save()