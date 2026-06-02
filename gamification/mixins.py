from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from .models import Badge
from django.utils.translation import gettext_lazy as _


class GamificationMixin(models.Model):
    class Meta:
        abstract = True

    @property
    def gamification_status(self):
        """
        برگرداندن اطلاعات سطح با استفاده از مدل Badge (پویا)
        """
        try:
            score_obj = self.score
            points = score_obj.points
            current_badge = score_obj.badge
        except ObjectDoesNotExist:
            points = 0
            current_badge = None

        # اگر سطح فعلی معتبر نیست، از اولین سطح فعال (کمترین min_points) استفاده کن
        if not current_badge or not current_badge.is_active:
            current_badge = Badge.objects.filter(is_active=True).order_by('min_points').first()

        # دریافت لیست تمام سطوح فعال (برای پیدا کردن سطح بعدی)
        all_badges = list(Badge.objects.filter(is_active=True).order_by('min_points'))

        # پیدا کردن سطح بعدی
        next_badge = None
        for badge in all_badges:
            if badge.min_points > points:
                next_badge = badge
                break

        # محاسبه درصد پیشرفت
        if next_badge:
            prev_threshold = current_badge.min_points if current_badge else 0
            next_threshold = next_badge.min_points
            if next_threshold > prev_threshold:
                progress_percent = ((points - prev_threshold) / (next_threshold - prev_threshold)) * 100
            else:
                progress_percent = 0
            next_badge_name = next_badge.name
            next_badge_icon = next_badge.icon_url
            points_needed = next_threshold - points
            is_max_level = False
        else:
            progress_percent = 100
            next_badge_name = _('بالاترین سطح')
            next_badge_icon = None
            points_needed = 0
            is_max_level = True

        return {
            'current_points': points,
            'current_badge_slug': current_badge.slug if current_badge else 'unknown',
            'current_badge_name': current_badge.name if current_badge else _('نامشخص'),
            'current_badge_icon': current_badge.icon_url if current_badge else None,
            'current_badge_obj': current_badge,
            'next_badge_name': next_badge_name,
            'next_badge_icon': next_badge_icon,
            'points_needed_for_next': points_needed,
            'progress_percent': round(progress_percent, 1),
            'is_max_level': is_max_level,
        }
