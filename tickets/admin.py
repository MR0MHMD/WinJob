from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from .models import (
    TicketCategory, TicketTitle,
    Ticket, TicketMessage, TicketAttachment
)
from core.models import FAQ


# ==================== فیلترهای سفارشی ====================

class StatusFilter(SimpleListFilter):
    title = _('وضعیت تیکت')
    parameter_name = 'status_group'

    def lookups(self, request, model_admin):
        return (
            ('active', _('فعال (باز، منتظر، در حال بررسی)')),
            ('waiting', _('منتظر پاسخ')),
            ('closed', _('بسته شده')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.exclude(status=Ticket.Status.CLOSED)
        if self.value() == 'waiting':
            return queryset.filter(
                Q(status=Ticket.Status.WAITING_USER) |
                Q(status=Ticket.Status.WAITING_ADMIN)
            )
        if self.value() == 'closed':
            return queryset.filter(status=Ticket.Status.CLOSED)
        return queryset


class AssignedFilter(SimpleListFilter):
    title = _('وضعیت اختصاص')
    parameter_name = 'assignment'

    def lookups(self, request, model_admin):
        return (
            ('assigned', _('اختصاص داده شده')),
            ('unassigned', _('اختصاص داده نشده')),
            ('my', _('اختصاص به من')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'assigned':
            return queryset.filter(assigned_to__isnull=False)
        if self.value() == 'unassigned':
            return queryset.filter(assigned_to__isnull=True)
        if self.value() == 'my' and request.user.is_staff:
            return queryset.filter(assigned_to=request.user)
        return queryset


# ==================== اینلاین‌ها ====================

class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1
    fields = ['question', 'answer', 'order', 'is_active']
    ordering = ['order']


class TicketTitleInline(admin.TabularInline):
    model = TicketTitle
    extra = 1
    fields = ['name', 'slug', 'order', 'is_active', 'faqs_count']
    readonly_fields = ['faqs_count']

    def faqs_count(self, obj):
        return obj.faqs.count()

    faqs_count.short_description = _('تعداد سوالات')


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1
    fields = ['message', 'is_admin_reply', 'is_read', 'created_at']
    readonly_fields = ['created_at']
    can_delete = True
    show_change_link = True
    classes = ['collapse']


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 1
    fields = ['file_name', 'file_size_display', 'uploaded_at']
    readonly_fields = ['file_name', 'file_size_display', 'uploaded_at']

    def file_size_display(self, obj):
        return obj.file_size_display

    file_size_display.short_description = _('حجم')


# ==================== ادمین مدل‌ها ====================

@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order', 'is_active', 'created_at']
    list_display_links = ['name']
    list_filter = ['is_active', 'created_at']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TicketTitleInline]
    actions = ['make_active', 'make_inactive']

    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _('{} دسته‌بندی فعال شدند.').format(updated))

    make_active.short_description = _('فعال کردن دسته‌بندی‌های انتخاب شده')

    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _('{} دسته‌بندی غیرفعال شدند.').format(updated))

    make_inactive.short_description = _('غیرفعال کردن دسته‌بندی‌های انتخاب شده')


@admin.register(TicketTitle)
class TicketTitleAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'slug', 'order', 'is_active']
    list_display_links = ['name']
    list_filter = ['category', 'is_active', 'created_at']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [FAQInline]
    actions = ['make_active', 'make_inactive']

    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _('{} عنوان فعال شدند.').format(updated))

    make_active.short_description = _('فعال کردن عناوین انتخاب شده')

    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _('{} عنوان غیرفعال شدند.').format(updated))

    make_inactive.short_description = _('غیرفعال کردن عناوین انتخاب شده')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'get_title', 'user', 'category', 'status', 'priority', 'updated_at'
    ]
    list_display_links = ['id', 'get_title']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['id', 'custom_title', 'user__phone_number', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25
    inlines = [TicketMessageInline]
    actions = ['close_selected', 'reopen_selected', 'assign_to_me']

    def get_title(self, obj):
        title = obj.get_display_title()
        if len(title) > 50:
            title = title[:47] + '...'
        return title

    get_title.short_description = _('عنوان')

    def close_selected(self, request, queryset):
        updated = queryset.update(status=Ticket.Status.CLOSED)
        self.message_user(request, _('{} تیکت بسته شد.').format(updated))

    close_selected.short_description = _('بستن تیکت‌های انتخاب شده')

    def reopen_selected(self, request, queryset):
        updated = queryset.update(status=Ticket.Status.OPEN)
        self.message_user(request, _('{} تیکت دوباره باز شد.').format(updated))

    reopen_selected.short_description = _('باز کردن مجدد تیکت‌های انتخاب شده')

    def assign_to_me(self, request, queryset):
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, _('{} تیکت به شما اختصاص یافت.').format(updated))

    assign_to_me.short_description = _('اختصاص به من')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.status = Ticket.Status.OPEN
        super().save_model(request, obj, form, change)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'ticket', 'short_message', 'is_admin_reply', 'is_read', 'created_at']
    list_display_links = ['id']
    list_filter = ['is_admin_reply', 'is_read', 'created_at']
    search_fields = ['message', 'ticket__id']
    readonly_fields = ['created_at']
    inlines = [TicketAttachmentInline]
    actions = ['mark_as_read', 'mark_as_unread']

    def short_message(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message

    short_message.short_description = _('متن پیام')

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, _('{} پیام به عنوان خوانده شده علامت‌گذاری شد.').format(updated))

    mark_as_read.short_description = _('علامت‌گذاری به عنوان خوانده شده')

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, _('{} پیام به عنوان خوانده نشده علامت‌گذاری شد.').format(updated))

    mark_as_unread.short_description = _('علامت‌گذاری به عنوان خوانده نشده')


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'message', 'file_size_display', 'uploaded_at']
    list_display_links = ['file_name']
    list_filter = ['uploaded_at']
    search_fields = ['file_name', 'message__ticket__id']
    readonly_fields = ['file_name', 'file_size_display', 'uploaded_at']

    def file_size_display(self, obj):
        return obj.file_size_display

    file_size_display.short_description = _('حجم')

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.file.delete(save=False)
        super().delete_queryset(request, queryset)

    def delete_model(self, request, obj):
        obj.file.delete(save=False)
        super().delete_model(request, obj)
