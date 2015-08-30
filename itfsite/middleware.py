from django.conf import settings

import re

def itfsite_template_context_processor(request):
	ctx = dict(settings.DEFAULT_TEMPLATE_CONTEXT)

	# for spam obfuscation
	ctx["CONTACT_EMAIL_REVERSED"] = "".join(reversed(re.search(r"<(.*)>", settings.CONTACT_EMAIL).group(1)))

	return ctx

