from django import template
from django.utils import safestring
from django.template.defaultfilters import stringfilter
import markdown2
import json as jsonlib

register = template.Library()

@register.filter(is_safe=True)
@stringfilter
def render_text(value, format):
    if str(format) in 'TextFormat.Markdown':
        return safestring.mark_safe(markdown2.markdown(value, safe_mode=True))
    return safestring.mark_safe(value)

@register.filter(is_safe=True)
@stringfilter
def markdown(value):
    return safestring.mark_safe(markdown2.markdown(value, safe_mode=True))

@register.filter(is_safe=True)
def json(value):
    return safestring.mark_safe(jsonlib.dumps(value))
