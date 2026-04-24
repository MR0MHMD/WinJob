from .forms import CustomUserChangeForm, CustomUserCreationForm
from django_jalali.admin.filters import JDateFieldListFilter
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.admin import UserAdmin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from .models import CustomUser, Wallet
from django.contrib import messages
from django.db.models import Sum
from django.urls import reverse
from .models import OTPRequest
from .inline_admin import *


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = [
        'phone_number',
        'nickname',
        'user_type_display',
        'profile_status',
        'formatted_created_at',
    ]

    list_filter = [
        'is_active',
        'is_staff',
        'is_superuser',
        ('created_at', JDateFieldListFilter),
        ('province', admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        'phone_number',
        'nickname',
        'advertiser_profile__business_name',
        'influencer_profile__full_name',
    ]

    ordering = ('-created_at',)

    readonly_fields = [
        'last_login',
        'formatted_date_joined',
        'formatted_created_at',
        'formatted_updated_at',
        'profile_link',
        'wallet_balance_display',
        'total_spent_display',
        'total_deposits_display',
        'display_sheba',
    ]

    # ==================== FIELDSETS ====================

    def get_fieldsets(self, request, obj=None):
        base_fieldsets = (
            (None, {
                'fields': ('phone_number', 'password')
            }),
            (_('اطلاعات شخصی'), {
                'fields': ('nickname', 'email', 'avatar', 'display_sheba', 'province',),
            }),
            (_('اطلاعات مالی'), {
                'fields': ('wallet_balance_display', 'total_spent_display', 'total_deposits_display'),
                'classes': ('collapse',)
            }),
            (_('مجوزها'), {
                'fields': ('is_active', 'is_staff', 'is_superuser', 'is_regional_manager',),
                'classes': ('collapse',)
            }),
            (_('گروه‌ها و دسترسی‌ها'), {
                'classes': ('collapse',),
                'fields': ('groups', 'user_permissions')
            }),
            (_('تاریخ‌ها'), {
                'classes': ('collapse',),
                'fields': ('last_login', 'formatted_date_joined', 'formatted_created_at', 'formatted_updated_at')
            }),
        )

        if obj:
            base_fieldsets = base_fieldsets + (
                (_('پروفایل مرتبط'), {
                    'classes': ('collapse',),
                    'fields': ('profile_link',)
                }),
            )

        return base_fieldsets

    # ==================== INLINE MANAGEMENT ====================

    def get_inline_instances(self, request, obj=None):
        inlines = []

        if obj:
            inlines.append(TransactionInline(self.model, self.admin_site))

            if hasattr(obj, 'advertiser_profile'):
                inlines.append(AdvertiserProfileInline(self.model, self.admin_site))

            elif hasattr(obj, 'influencer_profile'):
                inlines.append(InfluencerProfileInline(self.model, self.admin_site))

        return inlines

    # ==================== CUSTOM METHODS ====================

    def user_type_display(self, obj):
        if hasattr(obj, 'advertiser_profile'):
            return mark_safe('<span style="color: #4CAF50;">🏢 تبلیغ‌دهنده</span>')
        elif hasattr(obj, 'influencer_profile'):
            return mark_safe('<span style="color: #2196F3;">🌟 اینفلوئنسر</span>')
        elif hasattr(obj, 'team_member'):
            return mark_safe('<span style="color: #2196F3;">🌟 عضو تیم</span>')
        elif obj.is_superuser:
            return mark_safe('<span style="color: #f44336;">👑 مدیر سیستم</span>')
        elif obj.is_staff and obj.is_regional_manager:
            return mark_safe('<span style="color: #f44336;">👑 مدیر استانی</span>')
        elif obj.is_staff:
            return mark_safe('<span style="color: #f44336;">👑 کارمند</span>')

        return '-'

    user_type_display.short_description = 'نوع کاربر'

    def wallet_balance_display(self, obj):
        """نمایش موجودی کیف پول با استایل رنگی"""
        try:
            balance = obj.wallet.balance
            color = '#4CAF50' if balance > 0 else '#f44336'
            return format_html('<span style="color: {}; font-weight: bold;">{} تومان</span>', color, f"{balance:,}")
        except:
            return mark_safe('<span style="color: #f44336;">کیف پول ایجاد نشده</span>')

    wallet_balance_display.short_description = 'موجودی کیف پول'

    def total_spent_display(self, obj):
        """کل هزینه‌های کاربر"""
        total = Transaction.objects.filter(
            user=obj,
            type__in=[Transaction.Type.CAMPAIGN_PAYMENT, Transaction.Type.WITHDRAW],
            status=Transaction.Status.SUCCESS
        ).aggregate(total=Sum('amount'))['total'] or 0
        return format_html('<span style="color: #ff9800;">{} تومان</span>', f"{total:,}")

    total_spent_display.short_description = 'کل هزینه‌ها'

    def total_deposits_display(self, obj):
        """کل شارژهای کاربر"""
        total = Transaction.objects.filter(
            user=obj,
            type__in=[Transaction.Type.DEPOSIT, Transaction.Type.GATEWAY_PAYMENT],
            status=Transaction.Status.SUCCESS
        ).aggregate(total=Sum('amount'))['total'] or 0
        return format_html('<span style="color: #4CAF50;">{} تومان</span>', f"{total:,}")

    total_deposits_display.short_description = 'کل شارژها'

    def profile_status(self, obj):
        try:
            if hasattr(obj, 'advertiser_profile'):
                if obj.advertiser_profile.is_verified:
                    return mark_safe('<span style="color: #4CAF50;">✅ تأیید شده</span>')
                else:
                    return mark_safe('<span style="color: #ff9800;">⏳ در انتظار تأیید</span>')

            elif hasattr(obj, 'influencer_profile'):
                if obj.influencer_profile.is_active:
                    return mark_safe('<span style="color: #4CAF50;">✅ فعال</span>')
                else:
                    return mark_safe('<span style="color: #f44336;">❌ غیرفعال</span>')

            elif obj.is_superuser:
                return mark_safe('<span style="color: #9c27b0;">👑 مدیر</span>')

            return '-'

        except Exception:
            return "خطا"

    profile_status.short_description = 'وضعیت پروفایل'

    def profile_link(self, obj):
        if hasattr(obj, 'advertiser_profile'):
            try:
                profile = obj.advertiser_profile
                if profile and profile.id:
                    url = reverse('admin:advertisers_advertiserprofile_change', args=[profile.id])
                    return format_html(
                        '<a href="{}" style="background-color: #4CAF50; color: white; padding: 5px 10px; '
                        'border-radius: 4px; text-decoration: none;">📋 مشاهده پروفایل تبلیغ‌دهنده</a>',
                        url
                    )
            except (AttributeError, AdvertiserProfile.DoesNotExist):
                pass

        elif hasattr(obj, 'influencer_profile'):
            try:
                profile = obj.influencer_profile
                if profile and profile.id:
                    url = reverse('admin:influencers_influencerprofile_change', args=[profile.id])
                    return format_html(
                        '<a href="{}" style="background-color: #2196F3; color: white; padding: 5px 10px; '
                        'border-radius: 4px; text-decoration: none;">📋 مشاهده پروفایل اینفلوئنسر</a>',
                        url
                    )
            except (AttributeError, InfluencerProfile.DoesNotExist):
                pass

        return mark_safe('<span style="color: gray;">این کاربر پروفایل خاصی ندارد</span>')

    profile_link.short_description = 'لینک پروفایل'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'
    formatted_created_at.admin_order_field = 'created_at'

    def formatted_date_joined(self, obj):
        return format_datetime(obj.date_joined)

    formatted_date_joined.short_description = 'تاریخ عضویت'

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = 'آخرین ویرایش'

    # ==================== ACTIONS ====================

    actions = ['activate_users', 'deactivate_users', 'delete_profiles']

    def activate_users(self, request, queryset):
        updated_count = queryset.update(is_active=True)
        self.message_user(request, f'✅ {updated_count} کاربر با موفقیت فعال شدند.', messages.SUCCESS)

    activate_users.short_description = 'فعال کردن کاربران'

    def deactivate_users(self, request, queryset):
        updated_count = queryset.update(is_active=False)
        self.message_user(request, f'✅ {updated_count} کاربر با موفقیت غیرفعال شدند.', messages.SUCCESS)

    deactivate_users.short_description = 'غیرفعال کردن کاربران'

    def delete_profiles(self, request, queryset):
        deleted_count = 0
        for user in queryset:
            if hasattr(user, 'advertiser_profile'):
                user.advertiser_profile.delete()
                deleted_count += 1
            elif hasattr(user, 'influencer_profile'):
                user.influencer_profile.delete()
                deleted_count += 1
        self.message_user(request, f'✅ {deleted_count} پروفایل مرتبط حذف شدند.', messages.SUCCESS)

    delete_profiles.short_description = 'حذف پروفایل‌های مرتبط'


@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'code', 'get_type', 'status', 'created_at', 'expires_at', 'api_status_badge']
    list_filter = ['status', 'type', 'api_status_code', 'created_at']
    search_fields = ['phone_number', 'code', 'request_id']
    readonly_fields = ['api_response_pretty', 'created_at', 'expires_at', 'verified_at']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('phone_number', 'code', 'type', 'status')
        }),
        ('جزئیات', {
            'fields': ('attempts', 'request_id', 'created_at', 'expires_at', 'verified_at')
        }),
        ('لاگ API', {
            'fields': ('api_status_code', 'api_response_pretty'),
            'classes': ('collapse',)
        }),
    )

    def get_type(self, obj):
        return obj.get_type_display()

    get_type.short_description = 'نوع'

    def api_status_badge(self, obj):
        if obj.api_status_code == 200:
            color = 'green'
            text = '✓ موفق'
        elif obj.api_status_code:
            color = 'red'
            text = '✗ خطا'
        else:
            color = 'gray'
            text = '—'
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, text)

    api_status_badge.short_description = 'وضعیت API'

    def api_response_pretty(self, obj):
        import json
        if not obj.api_response:
            return '-'
        return format_html('<pre style="white-space: pre-wrap;">{}</pre>',
                           json.dumps(obj.api_response, indent=2, ensure_ascii=False))

    api_response_pretty.short_description = 'پاسخ API'


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'balance_display', 'formatted_created_at', 'formatted_updated_at')
    search_fields = ('user__phone_number', 'user__nickname')
    list_select_related = ('user',)
    readonly_fields = ('formatted_created_at', 'formatted_updated_at', 'balance_display')

    def balance_display(self, obj):
        color = '#4CAF50' if obj.balance > 0 else '#f44336'
        return format_html('<span style="color: {}; font-weight: bold;">{} تومان</span>', color, f"{obj.balance:,}")

    balance_display.short_description = 'موجودی'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    formatted_updated_at.short_description = 'آخرین بروزرسانی'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user_display',
        'amount_display',
        'type_badge',
        'status_badge',
        'campaign_link',
        'formatted_created_at',
    )

    list_filter = (
        'type',
        'status',
        ('created_at', JDateFieldListFilter),
    )

    search_fields = (
        'user__phone_number',
        'user__nickname',
        'campaign__name',
        'invoice__id',
        'reference_id',
        'description',
    )

    autocomplete_fields = ('user', 'campaign', 'invoice', 'payment')

    readonly_fields = (
        'formatted_created_at',
        'amount_display',
        'sign_display',
    )

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('user', 'amount_display', 'type', 'status')
        }),
        ('ارتباط با سایر مدل‌ها', {
            'fields': ('campaign', 'invoice', 'payment', 'reference_id'),
            'classes': ('collapse',)
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('تاریخ', {
            'fields': ('formatted_created_at',),
            'classes': ('collapse',)
        }),
    )

    def user_display(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:accounts_customuser_change', args=[obj.user.id]),
            obj.user.phone_number
        )

    user_display.short_description = 'کاربر'

    def amount_display(self, obj):
        color = '#4CAF50' if obj.is_income else '#f44336'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} تومان</span>',
            color,
            f"{obj.amount:,}"
        )

    amount_display.short_description = 'مبلغ'

    def sign_display(self, obj):
        return obj.sign_display

    sign_display.short_description = 'علامت'

    def type_badge(self, obj):
        colors = {
            Transaction.Type.DEPOSIT: '#4CAF50',
            Transaction.Type.WITHDRAW: '#f44336',
            Transaction.Type.CAMPAIGN_PAYMENT: '#ff9800',
            Transaction.Type.CAMPAIGN_REFUND: '#2196F3',
            Transaction.Type.GATEWAY_PAYMENT: '#9c27b0',
            Transaction.Type.GATEWAY_REFUND: '#00bcd4',
        }
        color = colors.get(obj.type, '#757575')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_type_display())

    type_badge.short_description = 'نوع تراکنش'

    def status_badge(self, obj):
        colors = {
            Transaction.Status.PENDING: '#ff9800',
            Transaction.Status.SUCCESS: '#4CAF50',
            Transaction.Status.FAILED: '#f44336',
            Transaction.Status.CANCELLED: '#757575',
        }
        color = colors.get(obj.status, '#757575')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())

    status_badge.short_description = 'وضعیت'

    def campaign_link(self, obj):
        if obj.campaign:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:campaigns_campaign_change', args=[obj.campaign.id]),
                obj.campaign.name[:30]
            )
        return '-'

    campaign_link.short_description = 'کمپین'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'

    actions = ['mark_as_success', 'mark_as_failed', 'mark_as_pending']

    def mark_as_success(self, request, queryset):
        updated = queryset.update(status=Transaction.Status.SUCCESS)
        self.message_user(request, f'✅ {updated} تراکنش با موفقیت تأیید شد.', messages.SUCCESS)

    mark_as_success.short_description = 'تغییر وضعیت به موفق'

    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status=Transaction.Status.FAILED)
        self.message_user(request, f'❌ {updated} تراکنش ناموفق علامت‌گذاری شد.', messages.SUCCESS)

    mark_as_failed.short_description = 'تغییر وضعیت به ناموفق'

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status=Transaction.Status.PENDING)
        self.message_user(request, f'⏳ {updated} تراکنش به حالت در انتظار برگشت.', messages.SUCCESS)

    mark_as_pending.short_description = 'برگشت به حالت در انتظار'
