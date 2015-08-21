from django.conf.urls import include, url
from django.contrib import admin

urlpatterns = [
	url(r'_ajax/find-reps$', 'letters.views.find_reps'),
	url(r'_ajax/write-letter$', 'letters.views.write_letter'),
]
