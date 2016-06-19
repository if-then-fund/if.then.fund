# Applications.

from .settings import *

def get_brand_domains(brandid):
	import json
	with open(os.path.join("branding", brandid, "settings.json")) as f:
		d = json.load(f)
		return [d["site-domain"]] + d.get("alt-domains", [])
ALLOWED_HOSTS = sum([get_brand_domains(brandid) for brandid in os.listdir("branding")], [])

INSTALLED_APPS += [
	'itfsite',
	'contrib',
	'itf_vendor_static_resources',

	'twostream',

	# 3rd party apps. They go last so that we can override their
	# templates.
	'email_confirm_la',
	'bootstrapform',
	'htmlemailer',
	'dbstorage',
]

MIDDLEWARE_CLASSES += ['twostream.middleware.CacheLogic',]

TEMPLATES[0]['DIRS'] += [os.path.join(os.path.dirname(os.path.dirname(__file__)))]
TEMPLATES[0]['OPTIONS']['context_processors'] += [
	"itfsite.middleware.itfsite_template_context_processor",
]

AUTHENTICATION_BACKENDS += ['itfsite.betteruser.DirectLoginBackend']

DEFAULT_FILE_STORAGE = 'dbstorage.storage.DatabaseStorage'

STATICFILES_DIRS = [
    ('branding/' + brandid, os.path.join('branding', brandid, "static")) # (virtual root within /static, path to static resources)
    for brandid in os.listdir("branding")
]

# Local site settings.

ADMINS = (("Joshua Tauberer", "josh@if.then.fund"),)
SERVER_EMAIL = 'if.then.fund error <errors@mail.if.then.fund>'
TIME_ZONE = 'America/New_York' # default for templates/views, esp. since we say "The vote occurred on ___."

# 3rd party app settings.

EMAIL_CONFIRM_LA_CONFIRM_EXPIRE_SEC = 60 * 60 * 24 * 7  # 7 days (once it expires we can't retry)

# Other local settings.

SITE_MODE = environment.get("mode")
DE_API = environment.get('democracyengine') if "NO_DE" not in os.environ else {}
CDYNE_API_KEY = environment['cdyne_key']
FACEBOOK_ACCESS_TOKEN = environment['facebook_access_token']
VOTERVOICE_API_KEY = environment.get('votervoice', {}).get('api_key')
VOTERVOICE_ASSOCIATION = environment.get('votervoice', {}).get('association')
CURRENT_ELECTION_CYCLE = 2016
VALIDATE_EMAIL_DELIVERABILITY = True # turned off during tests

DEFAULT_TEMPLATE_CONTEXT = {
	"SITE_MODE": SITE_MODE,
	"MIXPANEL_ID": environment.get('mixpanel_id'),
	"HIDE_REMOTE_EMBEDS": environment.get('hide_remote_embeds', False),
}

DEFAULT_BRAND = "if.then.fund"

