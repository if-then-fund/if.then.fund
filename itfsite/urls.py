from django.conf.urls import patterns, include, url
from django.contrib import admin

urlpatterns = patterns('',
	url(r'^$', 'itfsite.views.homepage', name='homepage'),
	url(r'^(about|legal)$', 'itfsite.views.simplepage', name='simplepage'),

	url(r'^', include('contrib.urls')),

	url(r'_ajax/validate_email$', 'itfsite.accounts.validate_email_view'),
	url(r'_ajax/login$', 'itfsite.accounts.login_view'),

	url(r'^admin/', include(admin.site.urls)),

	url(r'^_twostream', include('twostream.urls')),

    url(r'^ev/', include('email_confirm_la.urls')),
)
