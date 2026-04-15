from django import template
from markdown import markdown
from markdown.extensions import Extension
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='markdown')
def to_markdown(text):
    extensions = ['extra']
    return mark_safe(markdown(text, extensions=extensions))
