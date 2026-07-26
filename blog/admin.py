from django.contrib import admin
from .models import Post, PostComments, BlogTags, BlogCategory
from core.utils.admin_utils import format_datetime


class PostCommentsInline(admin.TabularInline):
    model = PostComments
    extra = 0
    fields = ('name', 'content', 'parent_comment')
    readonly_fields = ('name', 'content', 'parent_comment')
    verbose_name = 'نظر'
    verbose_name_plural = 'نظرات'

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'status', 'formatted_created_at', 'formatted_updated_at', 'comment_count')

    list_filter = ('status', 'created_at')

    search_fields = ('title', 'content')

    prepopulated_fields = {'slug': ('title',)}

    readonly_fields = ["formatted_created_at", "formatted_updated_at"]

    inlines = [PostCommentsInline]

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    def formatted_updated_at(self, obj):
        return format_datetime(obj.updated_at)

    def comment_count(self, obj):
        return obj.comment_count()

    comment_count.short_description = 'تعداد نظرات'
    formatted_created_at.short_description = 'تاریخ ایجاد'
    formatted_updated_at.short_description = 'تاریخ ویرایش'

    class Meta:
        ordering = ['-created_at']


@admin.register(PostComments)
class PostCommentsAdmin(admin.ModelAdmin):
    list_display = ('post', 'name', 'formatted_created_at', 'parent_comment')
    list_filter = ('created_at', 'post')
    search_fields = ('content',)
    readonly_fields = ["formatted_created_at"]

    def formatted_created_at(self, obj):
        return format_datetime(obj.created_at)

    formatted_created_at.short_description = 'تاریخ ایجاد'


@admin.register(BlogTags)
class BlogTagsAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
