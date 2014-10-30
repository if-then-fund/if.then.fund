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

# Paths

STATIC_URL = '/static/'

# Local Settings

NO_SMTP_CHECK = environment["no_smtp_check"]
