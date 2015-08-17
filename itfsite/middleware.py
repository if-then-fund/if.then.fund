from django.conf import settings

def itfsite_template_context_processor(request):
	return {
		"SITE_MODE": settings.SITE_MODE,
		"ROOT_URL": request.build_absolute_uri("/").strip("/"), # remove trailing slash
		"MIXPANEL_ID": settings.MIXPANEL_ID,
		"HIDE_REMOTE_EMBEDS": settings.HIDE_REMOTE_EMBEDS,
	}

