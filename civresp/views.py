from django.shortcuts import render

def homepage(request):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.
	return render(request, "civresp/homepage.html")

def simplepage(request, pagename):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.
	return render(request, "civresp/%s.html" % pagename)
