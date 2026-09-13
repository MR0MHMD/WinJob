# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django.db.models import Sum
from django_jalali.admin.filters import JDateFieldListFilter

from payment.admin import TransactionInline
from payment.models import Transaction
from core.utils.admin_utils import format_datetime
from .models import CustomUser, OTPRequest
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .inline_admin import AdvertiserProfileInline, InfluencerProfileInline


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    مدیریت کامل کاربران با فرم‌های سفارشی و امکانات پیشرفته
    """
    model = CustomUser

    # ==================== فرم‌های مورد استفاده ====================
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    # ==================== لیست نمایش ====================
    list_display = [
        'phone_number',
        'nickname',
        'role_badge',          # ← جایگزین user_type_display
        'profile_badges',      # ← نمایش پروفایل‌ها (تبلیغ‌دهنده/اینفلوئنسر/عضو تیم)
        'wallet_balance_short',
        'formatted_created_at',
    ]

    list_filter = [
        'is_active',
        'is_superuser',
        'role',                # ← جایگزین is_regional_manager
        ('created_at', JDateFieldListFilter),
        'province',
    ]

    search_fields = [
        'phone_number',
        'nickname',
        'email',
        'advertiser_profile__business_name',
    ]

    ordering = ('-created_at',)

    # ==================== فیلدهای فقط خواندنی ====================
    readonly_fields = [
        'last_login',
        'date_joined_display',
        'created_at_display',
        'updated_at_display',
        'profile_link',
        'wallet_balance_display',
        'total_spent_display',
        'total_deposits_display',
        'display_sheba_formatted',
    ]

    # ==================== فیلدست‌ها ====================

    # فیلدست برای ویرایش کاربران موجود
    fieldsets = (
        (None, {
            'fields': ('phone_number', 'password')
        }),
        (_('اطلاعات شخصی'), {
            'fields': ('nickname', 'email', 'avatar', 'province', 'display_sheba_formatted'),
        }),
        (_('اطلاعات مالی'), {
            'fields': ('wallet_balance_display', 'total_spent_display', 'total_deposits_display'),
            'classes': ('collapse',)
        }),
        (_('مجوزها و دسترسی‌ها'), {
            'fields': ('is_active', 'role', 'is_superuser'),
            'classes': ('collapse',)
        }),
        (_('گروه‌ها و دسترسی‌های خاص'), {
            'classes': ('collapse',),
            'fields': ('groups', 'user_permissions')
        }),
        (_('تاریخ‌ها'), {
            'classes': ('collapse',),
            'fields': ('last_login', 'date_joined_display', 'created_at_display', 'updated_at_display')
        }),
    )

    # فیلدست برای ساخت کاربر جدید
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2'),
        }),
        (_('اطلاعات شخصی'), {
            'fields': ('nickname', 'email', 'avatar', 'province',),
        }),
        (_('مجوزها'), {
            'fields': ('is_active', 'role', 'is_superuser'),
        }),
    )

    # ==================== اینلاین‌ها ====================

    def get_inline_instances(self, request, obj=None):
        """
        اضافه کردن اینلاین‌ها فقط در صورت وجود کاربر و پروفایل مرتبط
        """
        inlines = []

        if obj:
            # تراکنش‌های مالی
            inlines.append(TransactionInline(self.model, self.admin_site))

            # پروفایل تبلیغ دهنده
            if hasattr(obj, 'advertiser_profile'):
                inlines.append(AdvertiserProfileInline(self.model, self.admin_site))

            # پروفایل اینفلوئنسر
            if hasattr(obj, 'influencer_profile'):
                inlines.append(InfluencerProfileInline(self.model, self.admin_site))

        return inlines

    # ==================== متدهای نمایشی ====================

    def role_badge(self, obj):
        """نمایش نقش سازمانی با آیکون و رنگ مناسب"""
        role_map = {
            'ceo':              ('👑 مدیرعامل',                '#9C27B0', 'bold'),
            'developer':        ('💻 توسعه‌دهنده',              '#2196F3', 'bold'),
            'content_manager':  ('📝 مدیر تولید محتوا',         '#4CAF50', 'bold'),
            'publish_manager':  ('📢 مدیر نشر',                 '#FF9800', 'bold'),
            'regional_manager': ('🏛️ مدیر استانی',              '#FF5722', 'bold'),
            'none':             ('—',                          '#9E9E9E', 'normal'),
        }

        # اگه سوپر یوزر باشه، اون مهم‌تره
        if obj.is_superuser:
            return mark_safe(
                '<span style="color:#f44336; font-weight:bold;">⭐ سوپر یوزر</span>'
            )

        label, color, weight = role_map.get(obj.role, ('—', '#9E9E9E', 'normal'))

        return format_html(
            '<span style="color: {}; font-weight: {};">{}</span>',
            color, weight, label
        )

    role_badge.short_description = _('نقش سازمانی')
    role_badge.admin_order_field = 'role'

    def profile_badges(self, obj):
        """نمایش پروفایل‌های کاربر (تبلیغ‌دهنده / اینفلوئنسر / عضو تیم)"""
        badges = []

        if hasattr(obj, 'advertiser_profile'):
            badges.append(
                '<span style="background:#4CAF50; color:white; padding:2px 6px; '
                'border-radius:3px; font-size:10px; margin-right:2px;">🏢 تبلیغ‌دهنده</span>'
            )

        if hasattr(obj, 'influencer_profile'):
            badges.append(
                '<span style="background:#2196F3; color:white; padding:2px 6px; '
                'border-radius:3px; font-size:10px; margin-right:2px;">🌟 اینفلوئنسر</span>'
            )

        if hasattr(obj, 'team_member'):
            badges.append(
                '<span style="background:#9C27B0; color:white; padding:2px 6px; '
                'border-radius:3px; font-size:10px; margin-right:2px;">👥 عضو تیم</span>'
            )

        if not badges:
            return mark_safe('<span style="color:#9E9E9E;">—</span>')

        return mark_safe(''.join(badges))

    profile_badges.short_description = _('پروفایل‌ها')

    def wallet_balance_short(self, obj):
        """نمایش مختصر موجودی در لیست"""
        try:
            balance = obj.wallet.balance
            color = '#4CAF50' if balance > 0 else '#f44336'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} تومان</span>',
                color,
                f"{balance:,}"
            )
        except:
            return mark_safe('<span style="color: #9E9E9E;">-</span>')

    wallet_balance_short.short_description = 'موجودی'
    wallet_balance_short.admin_order_field = 'wallet__balance'

    def wallet_balance_display(self, obj):
        """نمایش کامل موجودی با جزییات"""
        try:
            balance = obj.wallet.balance
            color = '#4CAF50' if balance > 0 else '#f44336'
            return format_html(
                '<div style="font-size: 14px; padding: 5px; background: #f5f5f5; border-radius: 4px;">'
                '<span style="color: {}; font-weight: bold;">💰 {} تومان</span>'
                '</div>',
                color,
                f"{balance:,}"
            )
        except:
            return mark_safe('<span style="color: #f44336;">⚠️ کیف پول ایجاد نشده</span>')

    wallet_balance_display.short_description = 'موجودی کیف پول'

    def total_spent_display(self, obj):
        """کل هزینه‌های کاربر"""
        total = Transaction.objects.filter(
            user=obj,
            type__in=[Transaction.Type.CAMPAIGN_PAYMENT, Transaction.Type.WITHDRAW],
            status=Transaction.Status.SUCCESS
        ).aggregate(total=Sum('amount'))['total'] or 0

        return format_html(
            '<span style="color: #FF9800; font-weight: bold;">💰 {} تومان</span>',
            f"{total:,}"
        )

    total_spent_display.short_description = 'کل هزینه‌ها'

    def total_deposits_display(self, obj):
        """کل شارژهای کاربر"""
        total = Transaction.objects.filter(
            user=obj,
            type__in=[Transaction.Type.DEPOSIT, Transaction.Type.GATEWAY_PAYMENT],
            status=Transaction.Status.SUCCESS
        ).aggregate(total=Sum('amount'))['total'] or 0

        return format_html(
            '<span style="color: #4CAF50; font-weight: bold;">💰 {} تومان</span>',
            f"{total:,}"
        )

    total_deposits_display.short_description = 'کل شارژها'

    def profile_link(self, obj):
        """لینک مستقیم به پروفایل مرتبط"""
        if hasattr(obj, 'advertiser_profile'):
            try:
                profile = obj.advertiser_profile
                if profile and profile.id:
                    url = reverse('admin:advertisers_advertiserprofile_change', args=[profile.id])
                    return format_html(
                        '<a href="{}" style="background: #4CAF50; color: white; padding: 5px 12px; '
                        'border-radius: 4px; text-decoration: none; display: inline-block;">'
                        '📋 مشاهده پروفایل تبلیغ دهنده</a>',
                        url
                    )
            except:
                pass

        elif hasattr(obj, 'influencer_profile'):
            try:
                profile = obj.influencer_profile
                if profile and profile.id:
                    url = reverse('admin:influencers_influencerprofile_change', args=[profile.id])
                    return format_html(
                        '<a href="{}" style="background: #2196F3; color: white; padding: 5px 12px; '
                        'border-radius: 4px; text-decoration: none; display: inline-block;">'
                        '📋 مشاهده پروفایل اینفلوئنسر</a>',
                        url
                    )
            except:
                pass

        return mark_safe('<span style="color: #9E9E9E;">این کاربر پروفایل خاصی ندارد</span>')

    profile_link.short_description = 'مشاهده پروفایل'

    def display_sheba_formatted(self, obj):
        """نمایش فرمت شده شماره شبا"""
        if not obj.sheba_code:
            return mark_safe('<span style="color: #9E9E9E;">-</span>')

        raw = obj.sheba_code.replace("IR", "").strip()
        first_two = raw[:2]
        rest = raw[2:]
        formatted_rest = " ".join(rest[i:i + 4] for i in range(0, len(rest), 4))

        return format_html(
            '<code style="background: #f5f5f5; padding: 3px 8px; border-radius: 3px; direction: ltr; display: inline-block;">'
            'IR - {} {}</code>',
            first_two,
            formatted_rest
        )

    display_sheba_formatted.short_description = 'شماره شبا'

    # ==================== نمایش تاریخ‌ها ====================

    def date_joined_display(self, obj):
        return format_datetime(obj.date_joined)

    date_joined_display.short_description = 'تاریخ عضویت'
    date_joined_display.admin_order_field = 'date_joined'

    def created_at_display(self, obj):
        return format_datetime(obj.created_at)

    created_at_display.short_description = 'تاریخ ایجاد'
    created_at_display.admin_order_field = 'created_at'

    def updated_at_display(self, obj):
        return format_datetime(obj.updated_at)

    updated_at_display.short_description = 'آخرین ویرایش'
    updated_at_display.admin_order_field = 'updated_at'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'
    formatted_created_at.admin_order_field = 'created_at'

    # ==================== اکشن‌های دسته‌جمعی ====================

    actions = [
        'activate_users',
        'deactivate_users',
        'assign_role_ceo',
        'assign_role_developer',
        'assign_role_content_manager',
        'assign_role_publish_manager',
        'clear_role',
        'delete_profiles',
    ]

    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ {updated} کاربر با موفقیت فعال شدند.', messages.SUCCESS)

    activate_users.short_description = 'فعال کردن کاربران انتخاب‌شده'

    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'✅ {updated} کاربر با موفقیت غیرفعال شدند.', messages.SUCCESS)

    deactivate_users.short_description = 'غیرفعال کردن کاربران انتخاب‌شده'

    def assign_role_ceo(self, request, queryset):
        updated = queryset.update(role=CustomUser.Role.CEO)
        self.message_user(request, f'✅ {updated} کاربر به عنوان مدیرعامل تعیین شدند.', messages.SUCCESS)

    assign_role_ceo.short_description = 'تبدیل به مدیرعامل'

    def assign_role_developer(self, request, queryset):
        updated = queryset.update(role=CustomUser.Role.DEVELOPER)
        self.message_user(request, f'✅ {updated} کاربر به عنوان توسعه‌دهنده تعیین شدند.', messages.SUCCESS)

    assign_role_developer.short_description = 'تبدیل به توسعه‌دهنده'

    def assign_role_content_manager(self, request, queryset):
        updated = queryset.update(role=CustomUser.Role.CONTENT_MANAGER)
        self.message_user(request, f'✅ {updated} کاربر به عنوان مدیر تولید محتوا تعیین شدند.', messages.SUCCESS)

    assign_role_content_manager.short_description = 'تبدیل به مدیر تولید محتوا'

    def assign_role_publish_manager(self, request, queryset):
        updated = queryset.update(role=CustomUser.Role.PUBLISH_MANAGER)
        self.message_user(request, f'✅ {updated} کاربر به عنوان مدیر نشر تعیین شدند.', messages.SUCCESS)

    assign_role_publish_manager.short_description = 'تبدیل به مدیر نشر'

    def clear_role(self, request, queryset):
        updated = queryset.update(role=CustomUser.Role.NONE)
        self.message_user(request, f'✅ نقش سازمانی {updated} کاربر پاک شد.', messages.SUCCESS)

    clear_role.short_description = 'پاک کردن نقش سازمانی'

    def delete_profiles(self, request, queryset):
        deleted = 0
        for user in queryset:
            if hasattr(user, 'advertiser_profile'):
                user.advertiser_profile.delete()
                deleted += 1
            elif hasattr(user, 'influencer_profile'):
                user.influencer_profile.delete()
                deleted += 1
        self.message_user(request, f'✅ {deleted} پروفایل مرتبط حذف شدند.', messages.SUCCESS)

    delete_profiles.short_description = 'حذف پروفایل‌های مرتبط'

    # ==================== متدهای ذخیره‌سازی ====================

    def save_model(self, request, obj, form, change):
        """
        ذخیره‌سازی با مدیریت رمز عبور
        """
        if not change:  # ساخت کاربر جدید
            password = form.cleaned_data.get('password1')
            if password:
                obj.set_password(password)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """
        ذخیره‌سازی روابط بعد از ذخیره اصلی
        """
        super().save_related(request, form, formsets, change)

        # اطمینان از ایجاد کیف پول
        if form.instance:
            from payment.models import Wallet
            Wallet.objects.get_or_create(user=form.instance)


# ==================== مدیریت OTP ====================

@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    """
    مدیریت کدهای تایید یکبار مصرف
    """
    list_display = [
        'phone_number',
        'code',
        'type_badge',
        'status_badge',
        'attempts',
        'created_at',
        'expires_at',
        'api_status_badge'
    ]

    list_filter = [
        'status',
        'type',
        'api_status_code',
        'created_at',
    ]

    search_fields = [
        'phone_number',
        'code',
        'request_id',
    ]

    readonly_fields = [
        'api_response_pretty',
        'created_at',
        'expires_at',
        'verified_at',
    ]

    fieldsets = (
        (_('اطلاعات اصلی'), {
            'fields': ('phone_number', 'code', 'type', 'status')
        }),
        (_('جزییات و وضعیت'), {
            'fields': ('attempts', 'request_id', 'created_at', 'expires_at', 'verified_at')
        }),
        (_('لاگ ارتباط با API'), {
            'fields': ('api_status_code', 'api_response_pretty'),
            'classes': ('collapse',)
        }),
    )

    # ==================== متدهای نمایشی ====================

    def type_badge(self, obj):
        """نمایش نوع با رنگ مناسب"""
        colors = {
            'login': '#4CAF50',
            'register': '#2196F3',
            'verify': '#FF9800',
        }
        labels = {
            'login': 'ورود',
            'register': 'ثبت‌نام',
            'verify': 'تایید',
        }
        color = colors.get(obj.type, '#9E9E9E')
        label = labels.get(obj.type, obj.type)
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            label
        )

    type_badge.short_description = 'نوع'

    def status_badge(self, obj):
        """نمایش وضعیت با رنگ مناسب"""
        colors = {
            'pending': '#FF9800',
            'verified': '#4CAF50',
            'expired': '#f44336',
        }
        labels = {
            'pending': '⏳ در انتظار',
            'verified': '✅ تایید شده',
            'expired': '❌ منقضی',
        }
        color = colors.get(obj.status, '#9E9E9E')
        label = labels.get(obj.status, obj.status)
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label
        )

    status_badge.short_description = 'وضعیت'

    def api_status_badge(self, obj):
        """نمایش وضعیت API با رنگ مناسب"""
        if obj.api_status_code == 200:
            return mark_safe(
                '<span style="color: #4CAF50; font-weight: bold;">✓ موفق</span>'
            )
        elif obj.api_status_code:
            return format_html(
                '<span style="color: #f44336; font-weight: bold;">✗ خطا ({})</span>',
                obj.api_status_code
            )
        return mark_safe(
            '<span style="color: #9E9E9E;">-</span>'
        )

    api_status_badge.short_description = 'وضعیت API'

    def api_response_pretty(self, obj):
        """نمایش زیبای پاسخ API"""
        import json
        if not obj.api_response:
            return mark_safe('<span style="color: #9E9E9E;">-</span>')

        try:
            formatted = json.dumps(obj.api_response, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="background: #000; padding: 10px; border-radius: 4px; '
                'white-space: pre-wrap; direction: ltr; text-align: left;">{}</pre>',
                formatted
            )
        except:
            return format_html('<pre>{}</pre>', obj.api_response)

    api_response_pretty.short_description = 'پاسخ API'

    # ==================== اکشن‌ها ====================

    actions = ['resend_otp', 'verify_manually']

    def resend_otp(self, request, queryset):
        """درخواست ارسال مجدد OTP"""
        # این قابلیت باید در سرویس مربوطه پیاده‌سازی شود
        self.message_user(request, '⚠️ این قابلیت باید از طریق سرویس OTP انجام شود.', messages.WARNING)

    resend_otp.short_description = 'ارسال مجدد OTP (نیاز به پیاده‌سازی)'

    def verify_manually(self, request, queryset):
        """تایید دستی OTP"""
        updated = queryset.update(status='verified', verified_at=timezone.now())
        self.message_user(request, f'✅ {updated} کد تایید به صورت دستی تایید شدند.', messages.SUCCESS)

    verify_manually.short_description = 'تایید دستی کدهای انتخاب‌شده'