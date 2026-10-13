from django.contrib import admin
from .models import FormQuestion


class QuestionsInline(admin.StackedInline):
    """سؤال‌ها را کنار تنظیمات فرم در دسترس قرار می‌دهد."""

    model = FormQuestion
    extra = 0
    min_num = 1
    max_num = 20
    fields = ("prompt", "kind", "options", "position")
