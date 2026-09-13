# support/mixins.py

"""
سیستم کنترل دسترسی پنل Support

ساختار:
- BaseSupportMixin: پایه همه - چک می‌کنه کاربر Support Access داره
- TopManagerRequiredMixin: فقط CEO و Developer
- ContentManagerRequiredMixin: CEO + Dev + Content Manager
- PublishManagerRequiredMixin: CEO + Dev + Publish Manager
- RegionalFilterMixin: فیلتر خودکار برای مدیران استانی

نحوه استفاده:
    class MyView(PublishManagerRequiredMixin, RegionalFilterMixin, ListView):
        model = Campaign
        province_field_path = 'advertiser__user__province'
"""

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from accounts.models import CustomUser


# ==================== Mixin های دسترسی پایه ====================

class BaseSupportMixin(UserPassesTestMixin):
    """
    پایه همه Mixin های پنل Support

    چک می‌کنه کاربر:
    1. لاگین باشه
    2. یکی از نقش‌های سازمانی رو داشته باشه (has_support_access)

    در صورت نداشتن دسترسی: 403 Forbidden
    """

    def test_func(self):
        user = self.request.user
        return (
                user.is_authenticated and
                user.has_support_access
        )

    def handle_no_permission(self):
        """به جای redirect، ارور 403 می‌دیم"""
        if not self.request.user.is_authenticated:
            # کاربر مهمان → برو به لاگین
            return super().handle_no_permission()

        raise PermissionDenied(
            "شما به این بخش دسترسی ندارید."
        )


class TopManagerRequiredMixin(BaseSupportMixin):
    """
    فقط مدیرعامل و توسعه‌دهنده

    دسترسی: همه چیز
    """

    def test_func(self):
        if not super().test_func():
            return False
        return self.request.user.is_top_manager


class ContentManagerRequiredMixin(BaseSupportMixin):
    """
    مدیرعامل + توسعه‌دهنده + مدیر تولید محتوا + مدیر استانی

    نکته: مدیر استانی هم دسترسی داره ولی RegionalFilterMixin داده‌هاش رو فیلتر می‌کنه
    """

    def test_func(self):
        if not super().test_func():
            return False
        return self.request.user.role in [
            CustomUser.Role.CEO,
            CustomUser.Role.DEVELOPER,
            CustomUser.Role.CONTENT_MANAGER,
            CustomUser.Role.REGIONAL_MANAGER,  # ✅ اضافه شد
        ]


class PublishManagerRequiredMixin(BaseSupportMixin):
    """
    مدیرعامل + توسعه‌دهنده + مدیر نشر + مدیر استانی

    نکته: مدیر استانی هم دسترسی داره ولی RegionalFilterMixin داده‌هاش رو فیلتر می‌کنه
    """

    def test_func(self):
        if not super().test_func():
            return False
        return self.request.user.role in [
            CustomUser.Role.CEO,
            CustomUser.Role.DEVELOPER,
            CustomUser.Role.PUBLISH_MANAGER,
            CustomUser.Role.REGIONAL_MANAGER,  # ✅ اضافه شد
        ]

# ==================== Mixin فیلتر استانی ====================

class RegionalFilterMixin:
    """
    فیلتر خودکار برای مدیران استانی

    نحوه کار:
    - اگه کاربر Regional Manager نباشه: هیچ فیلتری اعمال نمی‌شه
    - اگه Regional Manager باشه: فقط رکوردهای استان خودش رو می‌بینه

    نحوه استفاده:
        class MyView(PublishManagerRequiredMixin, RegionalFilterMixin, ListView):
            province_field_path = 'province'
            # یا برای مدل‌هایی که از طریق FK به استان وصلن:
            province_field_path = 'advertiser__user__province'
    """

    # مسیر رسیدن به استان در QuerySet
    # مثلاً: 'province' یا 'channel__province' یا 'advertiser__user__province'
    province_field_path = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # فقط برای Regional Manager و اگه مسیر استان مشخص شده
        if user.is_regional_manager and self.province_field_path:
            if not user.province_id:
                # Regional Manager بدون استان → هیچی نباید ببینه
                return qs.none()

            qs = qs.filter(**{
                self.province_field_path: user.province
            })

        return qs


class RegionalFilterComplexMixin:
    """
    فیلتر استانی برای مدل‌های پیچیده (مثل ContentOrder)

    این Mixin به جای یه مسیر ساده، یه Q object می‌گیره.

    نحوه استفاده:
        class MyView(...):
            province_q_object = staticmethod(lambda province:
                Q(campaign__advertiser__user__province=province) |
                Q(standalone_user__province=province)
            )
    """

    province_q_object = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_regional_manager and self.province_q_object:
            if not user.province_id:
                return qs.none()

            q = self.province_q_object(user.province)
            qs = qs.filter(q)

        return qs


# ==================== Mixin کمکی ====================

class SupportDashboardMixin(BaseSupportMixin):
    """
    برای داشبورد اصلی - همه نقش‌ها می‌تونن ببینن
    (معادل BaseSupportMixin، فقط برای وضوح بیشتر)
    """
    pass


SupportRequiredMixin = BaseSupportMixin
SuperUserRequiredMixin = TopManagerRequiredMixin