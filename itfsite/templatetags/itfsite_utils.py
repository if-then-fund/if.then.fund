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

@register.filter(is_safe=True)
@stringfilter
def currency(value):
	# Make the value appear like currency. Rounds big numbers to
	# whole-dollar amounts, so avoid this where exact amounts are
	# important.
	#
	# We could use locale.currency(grouping=True), but we lose
	# control over whether to show cents.

	# value might be a Decimal instance.
	value = float(value)

	if value < 100:
		# Show dollars and cents.
		return "$%0.2f" % value

	else:
		# Only show dollars, but use commas to group digits.
		return "${:,.0f}".format(value)
