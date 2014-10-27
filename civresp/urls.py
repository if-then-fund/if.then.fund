from django.conf.urls import patterns, include, url
from django.contrib import admin

urlpatterns = patterns('',
	url(r'^$', 'civresp.views.homepage', name='homepage'),
	url(r'^(about|legal)$', 'civresp.views.simplepage', name='simplepage'),

	# url(r'^blog/', include('blog.urls')),

	url(r'^admin/', include(admin.site.urls)),
)
