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
	'pledge',
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
