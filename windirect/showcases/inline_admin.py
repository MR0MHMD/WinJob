from django.contrib import admin
from .models import ShowcaseCard


class CardsInline(admin.StackedInline):
    """کارت‌ها را به ترتیب نمایش در صفحهٔ ویترین ویرایش می‌کند."""

    model = ShowcaseCard
    extra = 0
    min_num = 1
    max_num = 10
    fields = (
        "title",
        "subtitle",
        "image_url",
        ("button_title", "button_url"),
        "position",
    )
