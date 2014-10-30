from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
	url(r'a/(\d+)(?:/([a-z0-9_-]+))?$', 'contrib.views.trigger', name='trigger'),
)
