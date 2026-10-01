"""مدیریت ابزارها و سوابق مکالمه با الگوی ادمین پروژه."""
from django.contrib import admin
from django_jalali.admin.filters import JDateFieldListFilter
from core.utils.admin_utils import format_datetime
from .models import Showcase, ShowcaseCard, ConversationForm, FormQuestion, DirectRule, FormSubmission, DirectMessageEvent


class ToolAdmin(admin.ModelAdmin):
    """نمای مشترک ابزارها با جست‌وجو، فیلتر و تاریخ شمسی."""
    list_display = ('name', 'connection', 'is_active', 'created_display')
    list_filter = ('is_active', ('created_at', JDateFieldListFilter))
    search_fields = ('name', 'connection__username', 'connection__owner__phone_number')
    autocomplete_fields = ('connection',)
    list_select_related = ('connection',)
    readonly_fields = ('created_display', 'updated_display')
    list_per_page = 25

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def created_display(self, obj):
        """تاریخ ایجاد را با قالب مشترک ادمین نمایش می‌دهد."""
        return format_datetime(obj.created_at) if obj.pk else '—'

    @admin.display(description='آخرین ویرایش', ordering='updated_at')
    def updated_display(self, obj):
        """تاریخ ویرایش را با قالب مشترک ادمین نمایش می‌دهد."""
        return format_datetime(obj.updated_at) if obj.pk else '—'

    def get_readonly_fields(self, request, obj=None):
        """از انتقال ابزار دارای سابقه به حساب دیگری جلوگیری می‌کند."""
        return self.readonly_fields + (('connection',) if obj else ())


class CardsInline(admin.StackedInline):
    """کارت‌ها را به ترتیب نمایش در صفحهٔ ویترین ویرایش می‌کند."""
    model = ShowcaseCard
    extra = 0
    min_num = 1
    max_num = 10
    fields = ('title', 'subtitle', 'image_url', ('button_title', 'button_url'), 'position')


class QuestionsInline(admin.StackedInline):
    """سؤال‌ها را کنار تنظیمات فرم در دسترس قرار می‌دهد."""
    model = FormQuestion
    extra = 0
    min_num = 1
    max_num = 20
    fields = ('prompt', 'kind', 'options', 'position')


@admin.register(Showcase)
class ShowcaseAdmin(ToolAdmin):
    """مدیریت ویترین‌ها و کارت‌های وابسته."""
    inlines = (CardsInline,)
    fieldsets = (('ویترین', {'fields': ('connection', 'name', 'is_active')}),
                 ('تاریخچه', {'fields': ('created_display', 'updated_display'), 'classes': ('collapse',)}))


@admin.register(ConversationForm)
class ConversationFormAdmin(ToolAdmin):
    """مدیریت تنظیمات پرسش‌نامه و سؤال‌ها."""
    inlines = (QuestionsInline,)
    fieldsets = (('فرم', {'fields': ('connection', 'name', 'is_active')}),
                 ('مکالمه', {'fields': ('completion_text', 'cancel_keyword')}),
                 ('تاریخچه', {'fields': ('created_display', 'updated_display'), 'classes': ('collapse',)}))


@admin.register(DirectRule)
class DirectRuleAdmin(ToolAdmin):
    """مدیریت اولویت و مقصد پاسخ قوانین دایرکت."""
    list_display = ('name', 'connection', 'keyword', 'response_type', 'priority', 'is_active', 'created_display')
    list_filter = ToolAdmin.list_filter + ('response_type', 'match_type')
    search_fields = ToolAdmin.search_fields + ('keyword',)
    autocomplete_fields = ('connection', 'showcase', 'form')
    fieldsets = (('قانون', {'fields': ('connection', 'name', 'is_active', 'priority')}),
                 ('محرک', {'fields': ('keyword', 'match_type')}),
                 ('پاسخ', {'fields': ('response_type', 'reply_text', 'showcase', 'form')}),
                 ('تاریخچه', {'fields': ('created_display', 'updated_display'), 'classes': ('collapse',)}))


class ImmutableRecordAdmin(admin.ModelAdmin):
    """سوابق را فقط برای مشاهده، جست‌وجو و بررسی نمایش می‌دهد."""
    list_per_page = 25

    def has_add_permission(self, request):
        """ثبت دستی سوابق مجاز نیست."""
        return False

    def has_change_permission(self, request, obj=None):
        """تغییر دستی سابقه مجاز نیست."""
        return False

    def has_delete_permission(self, request, obj=None):
        """حذف سابقه از ادمین مجاز نیست."""
        return False

    @admin.display(description='تاریخ ثبت', ordering='created_at')
    def created_display(self, obj):
        """زمان ثبت را با قالب مشترک نمایش می‌دهد."""
        return format_datetime(obj.created_at)


@admin.register(FormSubmission)
class FormSubmissionAdmin(ImmutableRecordAdmin):
    """مرور پاسخ‌نامه‌ها با تفکیک وضعیت و تاریخ."""
    list_display = ('form', 'connection', 'sender_id', 'status', 'created_display')
    list_filter = ('status', ('created_at', JDateFieldListFilter))
    search_fields = ('form__name', 'connection__username', 'sender_id')
    list_select_related = ('form', 'connection')
    readonly_fields = ('form', 'connection', 'sender_id', 'status', 'schema', 'answers', 'created_display', 'updated_at', 'completed_at')


@admin.register(DirectMessageEvent)
class DirectMessageEventAdmin(ImmutableRecordAdmin):
    """مرور پیام‌های نمونه و خروجی ثبت‌شدهٔ آن‌ها."""
    list_display = ('external_message_id', 'connection', 'sender_id', 'rule', 'created_display')
    list_filter = (('created_at', JDateFieldListFilter),)
    search_fields = ('external_message_id', 'sender_id', 'connection__username', 'text')
    list_select_related = ('rule', 'connection')
    readonly_fields = ('external_message_id', 'connection', 'sender_id', 'text', 'rule', 'response', 'created_display')
