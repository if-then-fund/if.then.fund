from django import template
from django.utils import safestring
from django.template.defaultfilters import stringfilter, strip_tags
import markdown2
import json as jsonlib

register = template.Library()

@register.filter(is_safe=True)
@stringfilter
def render_text(value, format):
	if str(format) in 'TextFormat.Markdown':
		return safestring.mark_safe(markdown2.markdown(value, safe_mode=True))
	return safestring.mark_safe(value)

@register.filter
@stringfilter
def render_text_plain(value, format):
	if str(format) in 'TextFormat.Markdown':
		return value
	return strip_tags(value)

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
	if value == "": return "N/A"
	value = float(value)

	if value < 100:
		# Show dollars and cents.
		return "$%0.2f" % value

	else:
		# Only show dollars, but use commas to group digits.
		return "${:,.0f}".format(value)

@register.filter
def objtype(obj):
	return type(obj).__name__

@register.tag
def include2(parser, token):
	# In order to multiplex on branding for {% include %} tags, we need
	# a new tag. I tried to do this through a new template engine but
	# that failed miserably in multiple ways.
	template_name_var = template.Variable(token.split_contents()[1])
	return Include2Node(template_name_var)

class Include2Node(template.Node):
	def __init__(self, template_name):
		self.template_name = template_name

	def render(self, context):
		from itfsite.views import render2
		return render2(context['request'], self.template_name.resolve(context), context=context).content
