from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views

urlpatterns = patterns('',
	url(r'^$', 'itfsite.views.homepage', name='homepage'),
	url(r'^(about|about/how-it-works|about/theory-of-change|about/legal|about/press|privacy|terms|open)$', 'itfsite.views.simplepage', name='simplepage'),
	url(r'^accounts/welcome$', 'itfsite.accounts.welcome', name='welcome'),
	url(r'^home$', 'itfsite.views.user_home', name='home'),
	url(r'^home/contributions$', 'itfsite.views.user_contribution_details', name='user_contrib_details'),

	url(r'^', include('contrib.urls')),
	url(r'^(user|org)/(\d+)/([^/]+)$', 'itfsite.views.org_landing_page'),
	url(r'a/(?P<id>\d+)(?:/[a-z0-9_-]+)?(?:/(?P<action>contribute))?(?P<api_format_ext>\.json)?$', 'itfsite.views.campaign'),

	url(r'^accounts/login$', auth_views.login),
	url(r'^accounts/logout$', auth_views.logout, { 'next_page': '/' } ),
	url(r'^accounts/password-change$', auth_views.password_change, { 'post_change_redirect': '/home', 'template_name': 'registration/password_change.html' }, name='password_change' ),
	url(r'^accounts/_dismiss-notifications$', 'itfsite.views.dismiss_notifications'),
	url(r'^accounts/_email_settings$', 'itfsite.views.set_email_settings'),

	url(r'^user-media', include('dbstorage.urls')),

	url(r'^admin/', include(admin.site.urls)),

	url(r'^_twostream', include('twostream.urls')),

    url(r'^ev/', include('email_confirm_la.urls')),
)

# Because we use context variables from our template context
# processor in master.html, and the default error renderer
# does not process template context processors, and that
# leads to template errors, we can't render oops pages without
# our own handler that does process template context processors.
handler500 = 'itfsite.urls.ItfsiteHandler500'
def ItfsiteHandler500(request, exception=None):
	from django.http import HttpResponse
	try:
		from django.shortcuts import render
		return render(request, '500.html', {})
	except Exception as e:
		return HttpResponse("Ooops! There was an error!\n\n%s\n\n%s"
				% (str(e), repr(e)), content_type="text/plain")

