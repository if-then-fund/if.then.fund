def local(fn):
	import os, os.path
	return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'local', fn)

import json
environment = json.load(open("local/environment.json"))

SECRET_KEY = environment["secret-key"]
DEBUG = environment["debug"]
TEMPLATE_DEBUG = True

ALLOWED_HOSTS = [environment["host"]]

# Applications & middleware

INSTALLED_APPS = (
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',

	'itfsite',
	'contrib',

	'twostream',

	# 3rd party apps. They go last so that we can override their
	# templates.
	'email_confirm_la',
	'bootstrapform',
	'htmlemailer',
)

MIDDLEWARE_CLASSES = (
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
	'twostream.middleware.CacheLogic',
)

TEMPLATE_CONTEXT_PROCESSORS = (
	"django.contrib.auth.context_processors.auth",
	"django.core.context_processors.debug",
	"django.core.context_processors.i18n",
	"django.core.context_processors.media",
	"django.core.context_processors.static",
	"django.core.context_processors.tz",
	"django.contrib.messages.context_processors.messages",
	"django.core.context_processors.request",
	"itfsite.middleware.itfsite_template_context_processor",
	)

AUTHENTICATION_BACKENDS = ['itfsite.accounts.DirectLoginBackend', 'itfsite.accounts.EmailPasswordLoginBackend']

# Database and Cache

DATABASES = {
	'default': {
		'ENGINE': 'django.db.backends.sqlite3',
		'NAME': local('db.sqlite3'),
	}
}
if environment.get('db'):
	DATABASES['default'].update(environment['db'])
	CONN_MAX_AGE = 60

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': '127.0.0.1:11211',
    }
}
if environment.get('memcached'):
	CACHES['default']['BACKEND'] = 'django.core.cache.backends.memcached.MemcachedCache'
	SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Settings

ROOT_URLCONF = 'itfsite.urls'
WSGI_APPLICATION = 'itfsite.wsgi.application'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
AUTH_USER_MODEL = 'itfsite.User'

if environment.get("email"):
	EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
	EMAIL_HOST = environment["email"]["host"]
	EMAIL_PORT = environment["email"]["port"]
	EMAIL_HOST_USER = environment["email"]["user"]
	EMAIL_HOST_PASSWORD = environment["email"]["pw"]
	EMAIL_USE_TLS = True

if environment["https"]:
	SESSION_COOKIE_HTTPONLY = True
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_HTTPONLY = True
	CSRF_COOKIE_SECURE = True

if not DEBUG:
	TEMPLATE_LOADERS = (
	    ('django.template.loaders.cached.Loader', (
	        'django.template.loaders.filesystem.Loader',
	        'django.template.loaders.app_directories.Loader',
	    )),
	)

# Paths

STATIC_URL = '/static/'
STATIC_ROOT = environment.get("static", None)
LOGIN_REDIRECT_URL = '/home'

# App settings

EMAIL_CONFIRM_LA_HTTP_PROTOCOL = 'https' if environment["https"] else 'http'
EMAIL_CONFIRM_LA_DOMAIN = environment['host']
EMAIL_CONFIRM_LA_SAVE_EMAIL_TO_INSTANCE = False
DEFAULT_FROM_EMAIL = 'if.then.fund <hello@mail.if.then.fund>'
SITE_ROOT_URL = EMAIL_CONFIRM_LA_HTTP_PROTOCOL + "://" + environment['host']

# Local Settings

SITE_MODE = environment.get("mode")
ADMINS = ["josh@if.then.fund"]
NO_SMTP_CHECK = environment["no_smtp_check"]
DE_API = environment['democracyengine']
CDYNE_API_KEY = environment['cdyne_key']
CURRENT_ELECTION_CYCLE = 2014
