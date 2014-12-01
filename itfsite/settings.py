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
)

TEMPLATE_CONTEXT_PROCESSORS = (
	"django.contrib.auth.context_processors.auth",
	"django.core.context_processors.debug",
	"django.core.context_processors.i18n",
	"django.core.context_processors.media",
	"django.core.context_processors.static",
	"django.core.context_processors.tz",
	"django.contrib.messages.context_processors.messages",
	'django.core.context_processors.request',
	)

AUTHENTICATION_BACKENDS = ['itfsite.accounts.DirectLoginBackend', 'itfsite.accounts.EmailPasswordLoginBackend']

# Database

DATABASES = {
	'default': {
		'ENGINE': 'django.db.backends.sqlite3',
		'NAME': local('db.sqlite3'),
	}
}

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

if environment["https"]:
	SESSION_COOKIE_HTTPONLY = True
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_HTTPONLY = True
	CSRF_COOKIE_SECURE = True

# Paths

STATIC_URL = '/static/'
LOGIN_REDIRECT_URL = '/home'

# App settings

EMAIL_CONFIRM_LA_HTTP_PROTOCOL = 'https' if environment["https"] else 'http'
EMAIL_CONFIRM_LA_DOMAIN = 'itfsite.unnamed.example'
EMAIL_CONFIRM_LA_SAVE_EMAIL_TO_INSTANCE = False
DEFAULT_FROM_EMAIL = 'if.then.fund <hello@itfsite.unnamed.example>'
SITE_ROOT_URL = "https://unnamedsite"

# Local Settings

NO_SMTP_CHECK = environment["no_smtp_check"]
DE_API = environment['democracyengine']
CURRENT_ELECTION_CYCLE = 2014
