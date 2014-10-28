from django.shortcuts import render

def homepage(request):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.

	from pledge.models import Trigger
	triggers = Trigger.objects.order_by('-created')[0:10]

	return render(request, "itfsite/homepage.html", {
		"triggers": triggers
	})

def simplepage(request, pagename):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.
	return render(request, "itfsite/%s.html" % pagename)
