# Applications.

from .settings import *

INSTALLED_APPS += [
	'itfsite',
	'contrib',
	'letters',
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

TEMPLATES[0]['DIRS'] += [os.path.join(os.path.dirname(os.path.dirname(__file__)), 'branding/279forchange.us/templates')]
TEMPLATES[0]['OPTIONS']['context_processors'] += [
	"itfsite.middleware.itfsite_template_context_processor",
]

AUTHENTICATION_BACKENDS += ['itfsite.betteruser.DirectLoginBackend']

DEFAULT_FILE_STORAGE = 'dbstorage.storage.DatabaseStorage'

# Local site settings.

ADMINS = (("Joshua Tauberer", "josh@if.then.fund"),)
SERVER_EMAIL = 'if.then.fund error <errors@mail.if.then.fund>'

# 3rd party app settings.

EMAIL_CONFIRM_LA_CONFIRM_EXPIRE_SEC = 60 * 60 * 24 * 7  # 7 days (once it expires we can't retry)

# Other local settings.

SITE_MODE = environment.get("mode")
DE_API = environment['democracyengine']
CDYNE_API_KEY = environment['cdyne_key']
FACEBOOK_ACCESS_TOKEN = environment['facebook_access_token']
VOTERVOICE_API_KEY = environment.get('votervoice', {}).get('api_key')
VOTERVOICE_ASSOCIATION = environment.get('votervoice', {}).get('association')
CURRENT_ELECTION_CYCLE = 2016

DEFAULT_TEMPLATE_CONTEXT = {
	"SITE_MODE": SITE_MODE,
	"MIXPANEL_ID": environment.get('mixpanel_id'),
	"HIDE_REMOTE_EMBEDS": environment.get('hide_remote_embeds', False),
}

DEFAULT_BRAND = "279forchange.us"
