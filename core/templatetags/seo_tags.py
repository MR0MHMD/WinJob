from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    query string فعلی رو نگه می‌داره و فقط پارامترهای داده‌شده رو تغییر می‌ده.
    بدون & اضافه، با urlencode درست.
    مثال: {% query_transform page=2 %}
    """
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()