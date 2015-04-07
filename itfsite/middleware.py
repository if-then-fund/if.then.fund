from django.conf import settings

def itfsite_template_context_processor(request):
	return {
		"SITE_MODE": settings.SITE_MODE,
		"ROOT_URL": request.build_absolute_uri("/"),
		"MIXPANEL_ID": settings.MIXPANEL_ID,
	}

class DumpErrorsToConsole:
	def process_exception(self, request, exception):
		import traceback
		print()
		print(request)
		print()
		traceback.print_exc()
		print()
		return None # let Django continue as normal