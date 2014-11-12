from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views

urlpatterns = patterns('',
	url(r'^$', 'itfsite.views.homepage', name='homepage'),
	url(r'^(about|legal)$', 'itfsite.views.simplepage', name='simplepage'),
	url(r'^accounts/welcome$', 'itfsite.accounts.welcome', name='welcome'),

	url(r'^', include('contrib.urls')),

	url(r'_ajax/validate_email$', 'itfsite.accounts.validate_email_view'),

	url(r'^accounts/login$', auth_views.login),
	url(r'^accounts/logout$', auth_views.logout, { 'next_page': '/' } ),


	url(r'^admin/', include(admin.site.urls)),

	url(r'^_twostream', include('twostream.urls')),

    url(r'^ev/', include('email_confirm_la.urls')),
)
