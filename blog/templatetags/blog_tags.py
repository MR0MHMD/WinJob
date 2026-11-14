from django import template
from django.utils.safestring import mark_safe
from markdown import markdown

register = template.Library()

# Sanitize after Markdown conversion, including raw HTML embedded in the input.
ALLOWED_TAGS = {
    'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'del', 'blockquote', 'ul', 'ol', 'li',
    'pre', 'code', 'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
}


@register.filter(name='markdown')
def to_markdown(text):
    rendered = markdown(str(text or ''), extensions=['extra', 'nl2br'])

    return mark_safe(rendered)
