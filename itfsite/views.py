from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from contrib.models import Pledge, PledgeExecution

def homepage(request):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.

	from contrib.models import Trigger
	triggers = Trigger.objects.order_by('-created')[0:10]

	return render(request, "itfsite/homepage.html", {
		"triggers": triggers
	})

def simplepage(request, pagename):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.
	return render(request, "itfsite/%s.html" % pagename)

@login_required
def user_home(request):
	pledges = Pledge.objects.filter(user=request.user).order_by('-created').prefetch_related()
	pledge_map = dict((p.id, p) for p in pledges)
	for pe in PledgeExecution.objects.filter(pledge__in=set(pledges)):
		pledge.execution = pledge_map[pe.pledge_id]

	return render(request, "itfsite/home.html", {
		'pledges': pledges
		})
