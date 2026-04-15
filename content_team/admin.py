from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from core.admin_utils import format_datetime
from .models import *


# =========================
# Inline ها
# =========================

class ContentServiceRateInline(admin.TabularInline):
    model = ContentServiceRate
    extra = 0
    fields = (
        "service_type",
        "price_per_unit",
        "estimated_delivery_days",
        "is_available",
        "created_at",
    )
    readonly_fields = ("created_at",)


class TeamReviewInline(admin.TabularInline):
    model = TeamReview
    extra = 0
    readonly_fields = (
        "advertiser",
        "rating",
        "comment",
        "created_at",
    )
    can_delete = False


class ContentTeamMemberInline(admin.TabularInline):
    model = ContentTeamMember
    extra = 0
    fields = [
        'user',
        'role',
        'is_active',
        'revenue_share_percent'
    ]


class ContentOrderDescriptionInline(admin.StackedInline):
    """
    بریف سفارش - به صورت Stacked نمایش داده می‌شه
    چون فیلدهای زیادی داره و TabularInline خوانا نیست
    """
    model = ContentOrderDescription
    extra = 0
    can_delete = False
    max_num = 1

    fieldsets = (
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
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


class ContentOrderFileInline(admin.TabularInline):
    """
    فایل‌های پیوست سفارش
    """
    model = ContentOrderFile
    extra = 0
    can_delete = True

    fields = (
        "file",
        "file_type",
        "original_name",
        "description",
        "file_size_display",
        "uploaded_at",
    )

    readonly_fields = (
        "original_name",
        "file_size_display",
        "uploaded_at",
    )


class ContentPortfolioInline(admin.TabularInline):
    model = ContentPortfolio
    extra = 0
    fields = (
        "title",
        "media_preview",
        "service_type",
        "display_order",
        "is_active",
    )
    readonly_fields = ("media_preview",)

    def media_preview(self, obj):
        if obj.media:
            return format_html('<img src="{}" style="width: 40px; height: 40px; object-fit: cover;" />', obj.media.url)
        return "-"

    media_preview.short_description = _("پیش‌نمایش")


# =========================
# Content Team
# =========================

@admin.register(ContentTeam)
class ContentTeamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "is_active",
        "avg_rating_display",
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
        ContentServiceRateInline,
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
            "fields": (
                "is_active",
            )
        }),

        ("آمار تیم", {
            "fields": (
                "avg_rating_display",
                "completed_orders_display",
                'members_count_display'
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

    def avg_rating_display(self, obj):
        return obj.avg_rating or "-"

    def completed_orders_display(self, obj):
        return obj.completed_orders_count

    def members_count_display(self, obj):
        return obj.members_count

    completed_orders_display.short_description = _("سفارشات تکمیل شده")
    avg_rating_display.short_description = _("میانگین امتیاز")
    members_count_display.short_description = _("تعداد اعضای تیم")


# =========================
# Team Member
# =========================

@admin.register(ContentTeamMember)
class ContentTeamMemberAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'team',
        'role',
        'is_active',
        'created_at'
    ]

    list_filter = [
        'role',
        'team',
        'is_active'
    ]

    search_fields = [
        'user',
        'team__name'
    ]


# =========================
# Service Type
# =========================

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


# =========================
# Service Rate
# =========================

@admin.register(ContentServiceRate)
class ContentServiceRateAdmin(admin.ModelAdmin):
    list_display = (
        "team",
        "service_type",
        "price_per_unit",
        "estimated_delivery_days",
        "is_available",
        "created_at",
    )

    list_filter = (
        "is_available",
        "team",
        "service_type",
    )

    search_fields = (
        "team__name",
        "service_type__name",
    )

    autocomplete_fields = (
        "team",
        "service_type",
    )


# =========================
# Content Order
# =========================

@admin.register(ContentOrder)
class ContentOrderAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "team",
        "service_rate",
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
        "service_rate",
    )

    readonly_fields = (
        "created_at",
        "has_brief_display",
        "files_count_display",
    )

    # اضافه کردن Inline های بریف و فایل
    inlines = [
        ContentOrderDescriptionInline,
        ContentOrderFileInline,
    ]

    fieldsets = (
        ("اطلاعات سفارش", {
            "fields": (
                "campaign",
                "team",
                "service_rate",
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


# =========================
# Content Order Description
# =========================

@admin.register(ContentOrderDescription)
class ContentOrderDescriptionAdmin(admin.ModelAdmin):
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


# =========================
# Content Order File
# =========================

@admin.register(ContentOrderFile)
class ContentOrderFileAdmin(admin.ModelAdmin):
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

        # برای سایر فایل‌ها لینک دانلود
        return format_html(
            '<a href="{}" target="_blank" '
            'style="color: #007bff;">⬇️ دانلود فایل</a>',
            obj.file.url
        )

    file_preview.short_description = _("پیش‌نمایش")


# =========================
# Team Review
# =========================

@admin.register(TeamReview)
class TeamReviewAdmin(admin.ModelAdmin):
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


@admin.register(TeamJoinRequest)
class TeamJoinRequestAdmin(admin.ModelAdmin):
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

    def approve_request(self, request, request_id):
        """تایید یک درخواست خاص"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages

        join_request = get_object_or_404(TeamJoinRequest, id=request_id)
        join_request.status = TeamJoinRequest.Status.APPROVED
        join_request.save()

        messages.success(request,
                         f'درخواست {join_request.user.nickname} برای عضویت در تیم {join_request.team.name} با موفقیت تایید شد.')
        return redirect('admin:content_team_teamjoinrequest_changelist')

    def reject_request(self, request, request_id):
        """رد یک درخواست خاص"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages

        join_request = get_object_or_404(TeamJoinRequest, id=request_id)
        join_request.status = TeamJoinRequest.Status.REJECTED
        join_request.save()

        messages.success(request,
                         f'درخواست {join_request.user.nickname} برای عضویت در تیم {join_request.team.name} رد شد.')
        return redirect('admin:content_team_teamjoinrequest_changelist')



@admin.register(ContentDelivery)
class ContentDeliveryAdmin(admin.ModelAdmin):
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


@admin.register(ContentOrderRevision)
class ContentOrderRevisionAdmin(admin.ModelAdmin):
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


@admin.register(ContentPortfolio)
class ContentPortfolioAdmin(admin.ModelAdmin):
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
            # تلاش برای نمایش ویدیو از آپارات/یوتیوب
            video_html = f'''
            <div style="margin-top: 10px;">
                <strong>لینک ویدیو:</strong> 
                <a href="{obj.video_url}" target="_blank" style="color: #007bff;">{obj.video_url}</a>
            </div>
            '''
            return mark_safe(video_html)
        return "-"

    media_preview_large.short_description = _("پیش‌نمایش")
