from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from core.admin_utils import RegionalFilterAdminMixin
from accounts.models import CustomUser
from core.admin_utils import format_datetime
from .utils import get_team_province
from .inline_admin import *


@admin.register(ContentTeam)
class ContentTeamAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "is_active",
        "avg_rating_display",
        "members_count_display",
        "completed_orders_display",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

    inlines = [
        ContentTeamMemberInline,
        ContentServicePlanInline,
        TeamReviewInline,
        ContentPortfolioInline
    ]

    readonly_fields = (
        "created_at",
        "updated_at",
        "avg_rating_display",
        "completed_orders_display",
        'members_count_display',
    )

    fieldsets = (
        ("اطلاعات تیم", {
            "fields": (
                "name",
                "slug",
                "description",
                "logo",
            )
        }),
        ("وضعیت", {
            "fields": ("is_active",),
            'classes': ('collapse',)
        }),
        ("آمار تیم", {
            "fields": (
                "avg_rating_display",
                "completed_orders_display",
                'members_count_display'
            ),
            'classes': ('collapse',)
        }),
        ("تاریخ‌ها", {
            "fields": ("created_at", "updated_at",),
            "classes": ("collapse",)
        }),
    )

    @staticmethod
    def get_team_manager_province(obj):
        """دریافت استان مدیر تیم"""
        try:
            manager = obj.members.filter(role='manager', is_active=True).first()
            if manager and manager.user and manager.user.province:
                return manager.user.province
        except:
            pass
        return None

    def avg_rating_display(self, obj):
        return obj.avg_rating or "-"

    avg_rating_display.short_description = "میانگین امتیاز"

    def completed_orders_display(self, obj):
        return obj.completed_orders_count

    completed_orders_display.short_description = "سفارشات تکمیل شده"

    def members_count_display(self, obj):
        return obj.members_count

    members_count_display.short_description = "تعداد اعضای تیم"

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for team in qs:
                province = self.get_team_manager_province(team)
                if province and province.id == request.user.province.id:
                    team_ids.append(team.id)
            return qs.filter(id__in=team_ids)

        return qs

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            province = self.get_team_manager_province(obj)
            if province and province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            province = self.get_team_manager_province(obj)
            if province and province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)


@admin.register(ContentTeamMember)
class ContentTeamMemberAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = [
        "id",
        'user_display',
        'team_link',
        'role',
        'is_active',
        'created_at'
    ]

    list_filter = [
        'role',
        'is_active',
        'user__province',
    ]

    search_fields = [
        'user__phone_number',
        'user__nickname',
        'team__name'
    ]

    autocomplete_fields = ['user', 'team']

    readonly_fields = [
        'created_at',
    ]

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": (
                "user",
                "team",
                "role",
            )
        }),
        ("مالی", {
            "fields": ("revenue_share_percent",)
        }),
        ("سایر", {
            "fields": ("bio", "is_active")
        }),
        ("تاریخچه", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )

    def user_display(self, obj):
        """نمایش کاربر با لینک"""
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse("admin:accounts_customuser_change", args=[obj.user.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.user.nickname or obj.user.phone_number)

    user_display.short_description = "کاربر"
    user_display.admin_order_field = "user__phone_number"

    def team_link(self, obj):
        """لینک به تیم"""
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse("admin:content_team_contentteam_change", args=[obj.team.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.team.name)

    team_link.short_description = "تیم"
    team_link.admin_order_field = "team__name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_regional_manager and request.user.province:
            qs = qs.filter(user__province=request.user.province)

        return qs.select_related('user', 'user__province', 'team')

    def has_change_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.user.province != request.user.province:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user.is_regional_manager and request.user.province:
            if obj.user.province != request.user.province:
                return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user' and request.user.is_regional_manager:
            kwargs['queryset'] = CustomUser.objects.filter(
                province=request.user.province,
                team_member__isnull=True
            )
        if db_field.name == 'team' and request.user.is_regional_manager:
            team_ids = []
            all_teams = ContentTeam.objects.all()
            for team in all_teams:
                try:
                    manager = team.members.filter(role='manager', is_active=True).first()
                    if manager and manager.user and manager.user.province == request.user.province:
                        team_ids.append(team.id)
                except:
                    pass
            kwargs['queryset'] = ContentTeam.objects.filter(id__in=team_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ContentServiceType)
class ContentServiceTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "icon",
        "display_order",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
    )

    ordering = (
        "display_order",
        "name",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }


@admin.register(ContentServicePlan)
class ContentServicePlanAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    """
    مدیریت پلن‌های خدمات تیم‌ها
    هر تیم برای هر نوع خدمت تا ۳ پلن می‌تونه داشته باشه
    """
    list_display = (
        "id",
        "name",
        "team_link",
        "service_type",
        "price_display",
        "estimated_delivery_days",
        "orders_count_display",
        "is_active_badge",
        "formated_created_ad",
    )

    list_filter = (
        "is_active",
        "team",
        "service_type",
        "estimated_delivery_days",
    )

    search_fields = (
        "team__name",
        "service_type__name",
        "name",
        "description",
    )

    autocomplete_fields = (
        "team",
        "service_type",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "price_display",
        "features_display",
        "orders_count_display",
    )

    fieldsets = (
        (_("اطلاعات اصلی"), {
            "fields": (
                "team",
                "service_type",
                "name",
                "description",
            )
        }),
        (_("قیمت‌گذاری و زمان"), {
            "fields": (
                "price_per_unit",
                "price_display",
                "estimated_delivery_days",
            )
        }),
        (_("ویژگی‌های پلن"), {
            "fields": (
                "features",
                "features_display",
            ),
            "classes": ("wide",),
        }),
        (_("وضعیت و آمار"), {
            "fields": (
                "is_active",
                "orders_count_display",
            )
        }),
        (_("تاریخ‌ها"), {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    # ---------- متدهای نمایش ----------
    def team_link(self, obj):
        url = reverse("admin:content_team_contentteam_change", args=[obj.team.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.team.name)

    team_link.short_description = _("تیم")
    team_link.admin_order_field = "team__name"

    def price_display(self, obj):
        """نمایش قیمت خوانا"""
        return obj.price_display

    price_display.short_description = _("قیمت")
    price_display.admin_order_field = "price_per_unit"

    def features_display(self, obj):
        """نمایش کامل ویژگی‌ها در جزئیات"""
        features_list = obj.get_features_list()
        if not features_list:
            return mark_safe('<span style="color: #6c757d;">بدون ویژگی</span>')

        badges = []
        for feature in features_list:
            badges.append(
                f'<span style="display: inline-block; background: #e9ecef; color: #495057; '
                f'padding: 3px 10px; margin: 2px; border-radius: 15px; font-size: 13px;">'
                f'{feature}</span>'
            )
        return mark_safe(''.join(badges))

    features_display.short_description = _("ویژگی‌های پلن")

    def orders_count_display(self, obj):
        if not obj.pk:  # هنوز ذخیره نشده
            return "-"
        count = obj.orders.count()
        if count:
            return format_html('<span style="color: #007bff;">{} سفارش</span>', count)
        return mark_safe('<span style="color: #6c757d;">بدون سفارش</span>')

    orders_count_display.short_description = _("سفارش‌ها")

    def is_active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color: #28a745;">✓ فعال</span>')
        return mark_safe('<span style="color: #dc3545;">✗ غیرفعال</span>')

    is_active_badge.short_description = _("وضعیت")

    def formated_created_ad(self, obj):
        return format_datetime(obj.created_at)

    formated_created_ad.short_description = _("تاریخ ایجاد")

    # ---------- محدودیت منطقه‌ای ----------
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            # فیلتر کردن پلن‌هایی که تیم‌شون در استان مدیر منطقست
            team_ids = []
            for plan in qs:
                province = get_team_province(plan.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(plan.team_id)
            return qs.filter(team_id__in=team_ids)
        return qs.select_related('team', 'service_type')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "team" and request.user.is_regional_manager:
            # فقط تیم‌های هم‌استان مدیر منطقه‌ای
            team_ids = []
            for team in ContentTeam.objects.all():
                province = get_team_province(team)
                if province and province.id == request.user.province.id:
                    team_ids.append(team.id)
            kwargs["queryset"] = ContentTeam.objects.filter(id__in=team_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ContentOrder)
class ContentOrderAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "campaign",
        "team",
        "plan",
        "price",
        "status",
        "has_brief_display",
        "files_count_display",
        "created_at",
    )

    list_filter = (
        "status",
        "team",
    )

    search_fields = (
        "campaign__name",
        "team__name",
    )

    autocomplete_fields = (
        "campaign",
        "team",
        "plan",
    )

    readonly_fields = (
        "created_at",
        "has_brief_display",
        "files_count_display",
    )

    inlines = [
        ContentOrderDescriptionInline,
        ContentOrderFileInline,
    ]

    fieldsets = (
        ("اطلاعات سفارش", {
            "fields": (
                "campaign",
                "team",
                "plan",
                "price",
            )
        }),

        ("وضعیت", {
            "fields": (
                "status",
            )
        }),

        ("اطلاعات تکمیلی", {
            "fields": (
                "has_brief_display",
                "files_count_display",
            ),
            "classes": ("collapse",)
        }),

        ("تاریخ", {
            "fields": (
                "created_at",
            ),
            "classes": ("collapse",)
        }),
    )

    def has_brief_display(self, obj):
        """آیا بریف ثبت شده؟"""
        has_brief = hasattr(obj, 'brief') and obj.brief is not None
        if has_brief:
            return mark_safe(
                '<span style="color: #28a745;">✓ بله</span>'
            )
        return mark_safe(
            '<span style="color: #dc3545;">✗ خیر</span>'
        )

    def files_count_display(self, obj):
        """تعداد فایل‌های پیوست"""
        count = obj.files.count()
        if count:
            return format_html(
                '<span style="color: #007bff; font-weight: bold;"> {} فایل</span>',
                count
            )
        return mark_safe('<span style="color: #6c757d;">بدون فایل</span>')

    has_brief_display.short_description = _("بریف ثبت شده؟")
    files_count_display.short_description = _("فایل‌های پیوست")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for order in qs:
                province = get_team_province(order.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(order.team_id)
            return qs.filter(team_id__in=team_ids)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'team' and request.user.is_regional_manager:
            team_ids = []
            for team in ContentTeam.objects.all():
                province = get_team_province(team)
                if province and province.id == request.user.province.id:
                    team_ids.append(team.id)
            kwargs['queryset'] = ContentTeam.objects.filter(id__in=team_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ContentOrderDescription)
class ContentOrderDescriptionAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "order",
        "goal",
        "tone",
        "brand_name",
        "created_at",
    )

    list_filter = (
        "goal",
        "tone",
    )

    search_fields = (
        "order__campaign__name",
        "order__team__name",
        "brand_name",
        "description",
    )

    autocomplete_fields = (
        "order",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("سفارش مرتبط", {
            "fields": (
                "order",
            )
        }),

        ("هدف و لحن", {
            "fields": (
                "goal",
                "goal_description",
                "tone",
            )
        }),

        ("اطلاعات برند", {
            "fields": (
                "brand_name",
                "hashtags",
            )
        }),

        ("محتوا", {
            "fields": (
                "target_audience",
                "description",
                "do_not_include",
            )
        }),

        ("مراجع", {
            "fields": (
                "reference_links",
            ),
            "classes": ("collapse",)
        }),

        ("تاریخ‌ها", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for desc in qs:
                province = get_team_province(desc.order.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(desc.order.team_id)
            return qs.filter(order__team_id__in=team_ids)
        return qs


@admin.register(ContentOrderFile)
class ContentOrderFileAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "original_name",
        "order",
        "file_type",
        "file_size_display",
        "description",
        "uploaded_at",
    )

    list_filter = (
        "file_type",
    )

    search_fields = (
        "original_name",
        "description",
        "order__campaign__name",
        "order__team__name",
    )

    autocomplete_fields = (
        "order",
    )

    readonly_fields = (
        "original_name",
        "file_size_display",
        "uploaded_at",
        "file_preview",
    )

    fieldsets = (
        ("سفارش مرتبط", {
            "fields": (
                "order",
            )
        }),

        ("فایل", {
            "fields": (
                "file",
                "file_preview",
                "file_type",
                "original_name",
                "file_size_display",
            )
        }),

        ("توضیحات", {
            "fields": (
                "description",
            )
        }),

        ("تاریخ", {
            "fields": (
                "uploaded_at",
            ),
            "classes": ("collapse",)
        }),
    )

    def file_preview(self, obj):
        """
        پیش‌نمایش فایل در ادمین
        فقط برای تصاویر نمایش داده می‌شه
        """
        if not obj.file:
            return "-"

        if obj.file_type == ContentOrderFile.FileType.IMAGE:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px; '
                'border-radius: 8px; border: 1px solid #ddd;" />',
                obj.file.url
            )

        if obj.file_type == ContentOrderFile.FileType.VIDEO:
            return format_html(
                '<video controls style="max-width: 300px; border-radius: 8px;">'
                '<source src="{}">'
                'مرورگر شما از ویدیو پشتیبانی نمی‌کند.'
                '</video>',
                obj.file.url
            )

        return format_html(
            '<a href="{}" target="_blank" '
            'style="color: #007bff;">⬇️ دانلود فایل</a>',
            obj.file.url
        )

    file_preview.short_description = _("پیش‌نمایش")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for file_obj in qs:
                province = get_team_province(file_obj.order.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(file_obj.order.team_id)
            return qs.filter(order__team_id__in=team_ids)
        return qs


@admin.register(TeamReview)
class TeamReviewAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        "team",
        "advertiser",
        "rating",
        "order",
        "created_at",
    )

    list_filter = (
        "team",
        "rating",
    )

    search_fields = (
        "team__name",
        "advertiser__user__username",
    )

    readonly_fields = (
        "created_at",
    )

    autocomplete_fields = (
        "team",
        "order",
        "advertiser",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for review in qs:
                province = get_team_province(review.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(review.team_id)
            return qs.filter(team_id__in=team_ids)
        return qs


@admin.register(TeamJoinRequest)
class TeamJoinRequestAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    """
    ادمین مدیریت درخواست‌های عضویت در تیم
    """
    list_display = ('id', 'user_link', 'team_link', 'status_badge', 'created_at', 'action_buttons')
    list_filter = ('status', 'created_at', 'team')
    search_fields = ('user__phone_number', 'user__nickname', 'team__name')
    readonly_fields = ('created_at',)
    list_per_page = 20
    list_select_related = ('user', 'team')

    fieldsets = (
        (_('اطلاعات درخواست'), {
            'fields': ('user', 'team', 'status')
        }),
        (_('اطلاعات زمانی'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def user_link(self, obj):
        """لینک به صفحه کاربر در ادمین"""
        url = reverse('admin:accounts_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.user.nickname)

    user_link.short_description = _('کاربر')

    def team_link(self, obj):
        """لینک به صفحه تیم در ادمین"""
        url = reverse('admin:content_team_contentteam_change', args=[obj.team.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.team.name)

    team_link.short_description = _('تیم')

    def status_badge(self, obj):
        """نمایش وضعیت با بج رنگی"""
        if obj.status == TeamJoinRequest.Status.PENDING:
            return mark_safe(
                '<span style="background: #ffc107; color: #000; padding: 3px 10px; border-radius: 15px; font-size: 12px;">⏳ در انتظار</span>')
        elif obj.status == TeamJoinRequest.Status.APPROVED:
            return mark_safe(
                '<span style="background: #28a745; color: #fff; padding: 3px 10px; border-radius: 15px; font-size: 12px;">✓ تایید شده</span>')
        else:
            return mark_safe(
                '<span style="background: #dc3545; color: #fff; padding: 3px 10px; border-radius: 15px; font-size: 12px;">✗ رد شده</span>')

    status_badge.short_description = _('وضعیت')

    def action_buttons(self, obj):
        """دکمه‌های عملیات برای تایید/رد درخواست"""
        if obj.status == TeamJoinRequest.Status.PENDING:
            return format_html(
                '<a class="button" href="{}" style="background: #28a745; color: white; padding: 4px 12px; border-radius: 4px; text-decoration: none; margin-right: 5px;">✅ تایید</a> '
                '<a class="button" href="{}" style="background: #dc3545; color: white; padding: 4px 12px; border-radius: 4px; text-decoration: none;">❌ رد</a>',
                f'approve/{obj.id}/',
                f'reject/{obj.id}/'
            )
        return '-'

    action_buttons.short_description = _('عملیات')

    actions = ['approve_selected', 'reject_selected']

    def approve_selected(self, request, queryset):
        """تایید چند درخواست به صورت批量"""
        updated = queryset.update(status=TeamJoinRequest.Status.APPROVED)
        self.message_user(request, f'{updated} درخواست با موفقیت تایید شد.')

    approve_selected.short_description = _('تایید درخواست‌های انتخاب شده')

    def reject_selected(self, request, queryset):
        """رد چند درخواست به صورت批量"""
        updated = queryset.update(status=TeamJoinRequest.Status.REJECTED)
        self.message_user(request, f'{updated} درخواست با موفقیت رد شد.')

    reject_selected.short_description = _('رد درخواست‌های انتخاب شده')

    def get_urls(self):
        """اضافه کردن URLهای سفارشی برای تایید/رد"""
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path('approve/<int:request_id>/', self.admin_site.admin_view(self.approve_request),
                 name='content_team_teamjoinrequest_approve'),
            path('reject/<int:request_id>/', self.admin_site.admin_view(self.reject_request),
                 name='content_team_teamjoinrequest_reject'),
        ]
        return custom_urls + urls

    @staticmethod
    def approve_request(request, request_id):
        """تایید یک درخواست خاص"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages

        join_request = get_object_or_404(TeamJoinRequest, id=request_id)
        join_request.status = TeamJoinRequest.Status.APPROVED
        join_request.save()

        messages.success(request,
                         f'درخواست {join_request.user.nickname} برای عضویت در تیم {join_request.team.name} با موفقیت تایید شد.')
        return redirect('admin:content_team_teamjoinrequest_changelist')

    @staticmethod
    def reject_request(request, request_id):
        """رد یک درخواست خاص"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages

        join_request = get_object_or_404(TeamJoinRequest, id=request_id)
        join_request.status = TeamJoinRequest.Status.REJECTED
        join_request.save()

        messages.success(request,
                         f'درخواست {join_request.user.nickname} برای عضویت در تیم {join_request.team.name} رد شد.')
        return redirect('admin:content_team_teamjoinrequest_changelist')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for req in qs:
                province = get_team_province(req.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(req.team_id)
            return qs.filter(team_id__in=team_ids)
        return qs


@admin.register(ContentDelivery)
class ContentDeliveryAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    """
    ادمین تحویل سفارشات - نسخه ساده شده با فایل مستقیم
    """
    list_display = (
        "id",
        "order_link",
        "version",
        "status_badge",
        "file_name_display",
        "delivered_by",
        "delivered_at_display",
        "is_accepted",
    )

    list_filter = (
        "status",
        "version",
        "delivered_at",
    )

    search_fields = (
        "order__campaign__name",
        "order__team__name",
        "file_name",
        "delivered_by__user__nickname",
    )

    autocomplete_fields = (
        "order",
        "delivered_by",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "file_name",
        "file_size_display",
        "order_info",
        "file_preview",
    )

    fieldsets = (
        ("اطلاعات سفارش", {
            "fields": (
                "order_info",
                "order",
                "version",
            )
        }),

        ("فایل تحویلی", {
            "fields": (
                "file",
                "file_preview",
                "file_name",
                "file_size_display",
            )
        }),

        ("وضعیت تحویل", {
            "fields": (
                "status",
                "notes",
            )
        }),

        ("اطلاعات تحویل‌دهنده", {
            "fields": (
                "delivered_by",
                "delivered_at",
            )
        }),

        ("تأیید نهایی", {
            "fields": (
                "accepted_at",
            ),
            "classes": ("collapse",)
        }),

        ("تاریخ‌ها", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    def order_link(self, obj):
        url = reverse('admin:content_team_contentorder_change', args=[obj.order.id])
        return format_html('<a href="{}" target="_blank">سفارش #{}</a>', url, obj.order.id)

    order_link.short_description = _("سفارش")

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'delivered': '#17a2b8',
            'partial': '#fd7e14',
            'revision_requested': '#dc3545',
            'final_accepted': '#28a745',
        }
        color = colors.get(obj.status, '#6c757d')
        return mark_safe(
            f'<span style="background: {color}; color: white; padding: 3px 10px; border-radius: 15px; font-size: 12px;">'
            f'{obj.get_status_display()}'
            f'</span>'
        )

    status_badge.short_description = _("وضعیت")

    def file_name_display(self, obj):
        if obj.file_name:
            if len(obj.file_name) > 30:
                return obj.file_name[:27] + "..."
            return obj.file_name
        return "-"

    file_name_display.short_description = _("نام فایل")

    def delivered_at_display(self, obj):
        return format_datetime(obj.delivered_at) if obj.delivered_at else "-"

    delivered_at_display.short_description = _("تاریخ تحویل")

    def is_accepted(self, obj):
        if obj.status == 'final_accepted':
            return mark_safe('<span style="color: #28a745;">✓ تأیید شده</span>')
        return mark_safe('<span style="color: #dc3545;">✗ تأیید نشده</span>')

    is_accepted.short_description = _("تأیید نهایی")

    def order_info(self, obj):
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<strong>کمپین:</strong> {}<br>'
            '<strong>تیم:</strong> {}<br>'
            '<strong>قیمت:</strong> {:,} تومان<br>'
            '<strong>وضعیت سفارش:</strong> {}'
            '</div>',
            obj.order.campaign.name,
            obj.order.team.name,
            obj.order.price,
            obj.order.get_status_display()
        )

    order_info.short_description = _("اطلاعات سفارش")

    def file_preview(self, obj):
        """پیش‌نمایش فایل در ادمین"""
        if not obj.file:
            return "-"

        ext = obj.file.name.lower().split('.')[-1] if '.' in obj.file.name else ''

        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px; border-radius: 8px; border: 1px solid #ddd;" />',
                obj.file.url
            )
        elif ext in ['mp4', 'mov', 'avi', 'mkv']:
            return format_html(
                '<video controls style="max-width: 300px; max-height: 200px; border-radius: 8px;">'
                '<source src="{}">'
                'مرورگر شما از ویدیو پشتیبانی نمی‌کند.'
                '</video>',
                obj.file.url
            )
        else:
            return format_html(
                '<a href="{}" target="_blank" style="color: #007bff;">📎 دانلود فایل</a>',
                obj.file.url
            )

    file_preview.short_description = _("پیش‌نمایش")

    def file_size_display(self, obj):
        return obj.file_size_display

    file_size_display.short_description = _("حجم فایل")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for rev in qs:
                province = get_team_province(rev.order.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(rev.order.team_id)
            return qs.filter(order__team_id__in=team_ids)
        return qs


@admin.register(ContentOrderRevision)
class ContentOrderRevisionAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    """
    ادمین درخواست‌های ویرایش سفارش - نسخه ساده شده با فایل مستقیم
    """
    list_display = (
        "id",
        "order_link",
        "requested_by",
        "status_badge",
        "feedback_preview",
        "file_name_display",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "order__campaign__name",
        "order__team__name",
        "requested_by__nickname",
        "feedback",
        "file_name",
    )

    autocomplete_fields = (
        "order",
        "requested_by",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "order_info",
        "file_name",
        "file_size_display",
        "file_preview",
    )

    fieldsets = (
        ("اطلاعات سفارش", {
            "fields": (
                "order_info",
                "order",
            )
        }),

        ("درخواست‌کننده", {
            "fields": (
                "requested_by",
            )
        }),

        ("جزئیات ویرایش", {
            "fields": (
                "feedback",
                "status",
            )
        }),

        ("فایل مرجع", {
            "fields": (
                "file",
                "file_preview",
                "file_name",
                "file_size_display",
            ),
            "classes": ("collapse",)
        }),

        ("تاریخ‌ها", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    def order_link(self, obj):
        url = reverse('admin:content_team_contentorder_change', args=[obj.order.id])
        return format_html('<a href="{}" target="_blank">سفارش #{}</a>', url, obj.order.id)

    order_link.short_description = _("سفارش")

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'accepted': '#28a745',
            'rejected': '#dc3545',
            'done': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return mark_safe(
            f'<span style="background: {color}; color: white; padding: 3px 10px; border-radius: 15px; font-size: 12px;">'
            f'{obj.get_status_display()}'
            f'</span>'
        )

    status_badge.short_description = _("وضعیت")

    def feedback_preview(self, obj):
        if len(obj.feedback) > 50:
            return obj.feedback[:50] + "..."
        return obj.feedback

    feedback_preview.short_description = _("توضیحات ویرایش")

    def file_name_display(self, obj):
        if obj.file_name:
            if len(obj.file_name) > 30:
                return obj.file_name[:27] + "..."
            return obj.file_name
        return "-"

    file_name_display.short_description = _("نام فایل")

    def order_info(self, obj):
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<strong>کمپین:</strong> {}<br>'
            '<strong>تیم:</strong> {}<br>'
            '<strong>قیمت:</strong> {:,} تومان'
            '</div>',
            obj.order.campaign.name,
            obj.order.team.name,
            obj.order.price
        )

    order_info.short_description = _("اطلاعات سفارش")

    def file_preview(self, obj):
        """پیش‌نمایش فایل مرجع در ادمین"""
        if not obj.file:
            return "-"

        ext = obj.file.name.lower().split('.')[-1] if '.' in obj.file.name else ''

        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px; border-radius: 8px; border: 1px solid #ddd;" />',
                obj.file.url
            )
        elif ext in ['mp4', 'mov', 'avi', 'mkv']:
            return format_html(
                '<video controls style="max-width: 300px; max-height: 200px; border-radius: 8px;">'
                '<source src="{}">'
                '</video>',
                obj.file.url
            )
        else:
            return format_html(
                '<a href="{}" target="_blank" style="color: #007bff;">📎 دانلود فایل</a>',
                obj.file.url
            )

    file_preview.short_description = _("پیش‌نمایش")

    def file_size_display(self, obj):
        return obj.file_size_display

    file_size_display.short_description = _("حجم فایل")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for delivery in qs:
                province = get_team_province(delivery.order.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(delivery.order.team_id)
            return qs.filter(order__team_id__in=team_ids)
        return qs


@admin.register(ContentPortfolio)
class ContentPortfolioAdmin(RegionalFilterAdminMixin, admin.ModelAdmin):
    """
    ادمین نمونه کارهای تیم‌ها
    """
    list_display = (
        "title_display",
        "team_link",
        "service_type",
        "display_order",
        "is_active_badge",
        "media_preview",
        "created_at",
    )

    list_filter = (
        "is_active",
        "team",
        "service_type",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "team__name",
    )

    autocomplete_fields = (
        "team",
        "service_type",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "media_preview_large",
    )

    fieldsets = (
        ("اطلاعات نمونه کار", {
            "fields": (
                "team",
                "title",
                "description",
            )
        }),

        ("محتوا", {
            "fields": (
                "media",
                "media_preview_large",
                "video_url",
                "external_link",
            )
        }),

        ("دسته‌بندی", {
            "fields": (
                "service_type",
            )
        }),

        ("تنظیمات نمایش", {
            "fields": (
                "display_order",
                "is_active",
            )
        }),

        ("تاریخ‌ها", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )

    def title_display(self, obj):
        if len(obj.title) > 40:
            return obj.title[:40] + "..."
        return obj.title

    title_display.short_description = _("عنوان")

    def team_link(self, obj):
        url = reverse('admin:content_team_contentteam_change', args=[obj.team.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.team.name)

    team_link.short_description = _("تیم")

    def is_active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color: #28a745;">✓ فعال</span>')
        return mark_safe('<span style="color: #dc3545;">✗ غیرفعال</span>')

    is_active_badge.short_description = _("وضعیت")

    def media_preview(self, obj):
        """پیش‌نمایش کوچک در لیست"""
        if obj.media:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 8px;" />',
                obj.media.url
            )
        elif obj.video_url:
            return mark_safe('<span style="color: #17a2b8;">🎬 ویدیو</span>')
        return "-"

    media_preview.short_description = _("پیش‌نمایش")

    def media_preview_large(self, obj):
        """پیش‌نمایش بزرگ در صفحه جزئیات"""
        if obj.media:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 300px; border-radius: 12px; border: 1px solid #ddd;" />',
                obj.media.url
            )
        elif obj.video_url:
            video_html = f'''
            <div style="margin-top: 10px;">
                <strong>لینک ویدیو:</strong> 
                <a href="{obj.video_url}" target="_blank" style="color: #007bff;">{obj.video_url}</a>
            </div>
            '''
            return mark_safe(video_html)
        return "-"

    media_preview_large.short_description = _("پیش‌نمایش")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_regional_manager and request.user.province:
            team_ids = []
            for portfolio in qs:
                province = get_team_province(portfolio.team)
                if province and province.id == request.user.province.id:
                    team_ids.append(portfolio.team_id)
            return qs.filter(team_id__in=team_ids)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'team' and request.user.is_regional_manager:
            team_ids = []
            for team in ContentTeam.objects.all():
                province = get_team_province(team)
                if province and province.id == request.user.province.id:
                    team_ids.append(team.id)
            kwargs['queryset'] = ContentTeam.objects.filter(id__in=team_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
