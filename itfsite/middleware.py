from django.conf import settings
from django.core.exceptions import DisallowedHost

import re

def load_brandings():
	import glob, os.path, json
	settings.BRANDS = { }
	settings.BRAND_CHOICES = []
	settings.BRANDS_FROM_INDEX = { }
	settings.BRAND_DOMAIN_MAP = { }
	for brand in glob.glob("branding/*"):
		brandid = os.path.basename(brand)
		data = json.load(open(os.path.join(brand, 'settings.json')))
		settings.BRANDS[brandid] = data
		settings.BRAND_CHOICES.append((data['index'], brandid))
		settings.BRANDS_FROM_INDEX[data['index']] = brandid
		settings.BRAND_DOMAIN_MAP[brandid] = brandid
		for domain in data.get("alt-domains", []): settings.BRAND_DOMAIN_MAP[domain] = brandid
	settings.BRAND_CHOICES.sort()

def get_branding(request_or_brandid):
	if isinstance(request_or_brandid, str):
		brandid = request_or_brandid
	elif isinstance(request_or_brandid, int):
		brandid = settings.BRANDS_FROM_INDEX[request_or_brandid]
	else:
		# Choose brand ID from the request hostname.
		host = request_or_brandid.get_host().split(":")[0]
		if host in settings.BRAND_DOMAIN_MAP:
			brandid = settings.BRAND_DOMAIN_MAP[host]
		elif host in ("127.0.0.1", "localhost", "demo.if.then.fund"):
			brandid = settings.DEFAULT_BRAND
		else:
			raise DisallowedHost(brandid)

	# Return a template context dictionary based on the branding settings.
	brand = settings.BRANDS[brandid]
	email_domain = re.sub(r"^www\.", "", brand['site-domain'])
	return {
		"BRAND_ID": brandid,
		"BRAND_INDEX": brand['index'],
		"SITE_NAME": brand['site-name'],
		"SITE_DOMAIN": brand['site-domain'],
		"ROOT_URL": "https://" + brand['site-domain'],
		"MAIL_FROM_EMAIL": '%s <no.reply@mail.%s>' % (brand['site-name'], email_domain),
		"CONTACT_EMAIL": '%s <hello@%s>' % (brand['site-name'], email_domain),
		"TWITTER_HANDLE": brand.get('twitter-handle'),
		"COPYRIGHT": brand['copyright'],
	}

def itfsite_template_context_processor(request):
	ctx = dict(settings.DEFAULT_TEMPLATE_CONTEXT)
	ctx.update(get_branding(request))

	# for spam obfuscation
	import re
	ctx["CONTACT_EMAIL_REVERSED"] = "".join(reversed(re.search(r"<(.*)>", ctx['CONTACT_EMAIL']).group(1)))

	return ctx

load_brandings()
