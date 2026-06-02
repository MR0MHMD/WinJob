from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, get_object_or_404
from gamification.models import Badge, AdvertiserScore, ChannelScore, TeamScore, PointLog
from influencers.models import InfluencerChannel


# تابع کمکی برای گرفتن لاگ‌ها
def get_recent_logs(score_obj, limit=5):
    if not score_obj:
        return []
    content_type = ContentType.objects.get_for_model(score_obj)
    return list(PointLog.objects.filter(
        content_type=content_type,
        object_id=score_obj.id
    ).order_by('-created_at')[:limit])

# تابع کمکی برای ساخت دیتای کانال
def get_channel_data(channel):
    score_obj, _ = ChannelScore.objects.get_or_create(channel=channel)
    status = channel.gamification_status
    return {
        'role': 'influencer',
        'title': channel.channel_name,
        'icon': 'bi-instagram',
        'status': status,
        'score_obj': score_obj,
        'recent_logs': get_recent_logs(score_obj),
        'channel_id': channel.id,
    }


@login_required
def points_guide(request, channel_id=None):
    user = request.user

    rules = {
        'advertiser': {
            'positive': [
                {'action': 'ساخت اولین کمپین', 'points': 70},
                {'action': 'ساخت و پرداخت کمپین زیر ۱۰ میلیون', 'points': 30},
                {'action': 'ساخت و پرداخت کمپین بین ۱۰ تا ۳۰ میلیون', 'points': 50},
                {'action': 'ساخت و پرداخت کمپین بالای ۳۰ میلیون', 'points': 70},
                {'action': 'ثبت نظر درباره کانال‌های ناشران', 'points': 5},
                {'action': 'ثبت نظر برای تیم تولید محتوا', 'points': 5},
                {'action': 'استفاده از تیم تولید محتوا در کمپین', 'points': 15},
            ],
            'negative': []
        },
        'influencer': {
            'positive': [
                {'action': 'قبول کردن سفارش', 'points': 20},
                {'action': 'تحویل گزارش (تکمیل سفارش)', 'points': 15},
                {'action': 'تایید شدن گزارش توسط ادمین', 'points': 5},
                {'action': 'دریافت امتیاز ۵ از تبلیغ‌دهنده', 'points': 15},
                {'action': 'دریافت امتیاز ۴ از تبلیغ‌دهنده', 'points': 5},
            ],
            'negative': [
                {'action': 'رد کردن سفارش', 'points': -40},
                {'action': 'دریافت امتیاز ۲ از تبلیغ‌دهنده', 'points': -20},
                {'action': 'دریافت امتیاز ۱ از تبلیغ‌دهنده', 'points': -30},
            ]
        },
        'team_member': {
            'positive': [
                {'action': 'قبول سفارش', 'points': 20},
                {'action': 'تحویل سفارش قبل از ددلاین', 'points': 20},
                {'action': 'قبول کردن ویرایش (هر بار)', 'points': 10},
                {'action': 'تایید نهایی کاربر بدون درخواست ویرایش', 'points': 30},
                {'action': 'دریافت امتیاز ۵ از تبلیغ‌دهنده', 'points': 15},
                {'action': 'دریافت امتیاز ۴ از تبلیغ‌دهنده', 'points': 5},
            ],
            'negative': [
                {'action': 'رد کردن سفارش', 'points': -50},
                {'action': 'رد کردن درخواست ویرایش', 'points': -30},
                {'action': 'تحویل سفارش بعد از ددلاین', 'points': -20},
                {'action': 'دریافت امتیاز ۲ از تبلیغ‌دهنده', 'points': -10},
                {'action': 'دریافت امتیاز ۱ از تبلیغ‌دهنده', 'points': -20},
            ]
        }
    }

    if channel_id:
        channel = get_object_or_404(InfluencerChannel, id=channel_id, influencer__user=user, is_active=True)
        roles_data = [get_channel_data(channel)]
        badges = Badge.objects.filter(is_active=True).order_by('min_points')
        context = {
            'roles_data': roles_data,
            'badges': badges,
            'rules': rules,
            'influencer_exists': True,
            'single_channel_mode': True,
        }
        return render(request, 'gamification/pages/points_guide.html', context)

        # حالت عادی (نمایش همه نقش‌ها)
    roles_data = []

    # تبلیغ‌دهنده
    if hasattr(user, 'advertiser_profile'):
        profile = user.advertiser_profile
        score_obj, _ = AdvertiserScore.objects.get_or_create(profile=profile)
        status = profile.gamification_status
        roles_data.append({
            'role': 'advertiser',
            'title': 'تبلیغ‌دهنده',
            'icon': 'bi-person-badge',
            'status': status,
            'score_obj': score_obj,
            'recent_logs': get_recent_logs(score_obj),
        })

    # اینفلوئنسر (همه کانال‌ها)
    if hasattr(user, 'influencer_profile'):
        channels = InfluencerChannel.objects.filter(influencer=user.influencer_profile, is_active=True)
        for channel in channels:
            roles_data.append(get_channel_data(channel))

    # تیم تولید محتوا
    if hasattr(user, 'team_member') and user.team_member.team:
        team = user.team_member.team
        score_obj, _ = TeamScore.objects.get_or_create(team=team)
        status = team.gamification_status
        roles_data.append({
            'role': 'team_member',
            'title': f'تیم {team.name}',
            'icon': 'bi-people',
            'status': status,
            'score_obj': score_obj,
            'recent_logs': get_recent_logs(score_obj),
        })

    badges = Badge.objects.filter(is_active=True).order_by('min_points')
    influencer_exists = any(r['role'] == 'influencer' for r in roles_data)

    context = {
        'roles_data': roles_data,
        'badges': badges,
        'rules': rules,
        'influencer_exists': influencer_exists,
        'single_channel_mode': False,
    }
    return render(request, 'gamification/pages/points_guide.html', context)
