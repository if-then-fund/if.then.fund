from django.db.models import Sum
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from contrib.models import Pledge, PledgeExecution, PledgeStatus

def homepage(request):
	# The site homepage.

	# Get all of the open triggers that a user might participate in.
	from contrib.models import Trigger, TriggerStatus
	open_triggers = Trigger.objects.filter(status=TriggerStatus.Open).order_by('-total_pledged')
	recent_executed_triggers = Trigger.objects.filter(status=TriggerStatus.Executed).select_related("execution").order_by('-execution__created')

	return render(request, "itfsite/homepage.html", {
		"open_triggers": open_triggers,
		"recent_executed_triggers": recent_executed_triggers,
	})

def simplepage(request, pagename):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.
	pagename = pagename.replace('/', '-')
	return render(request, "itfsite/%s.html" % pagename)

@login_required
def user_home(request):
	# Get the user's pledges.
	pledges = Pledge.objects.filter(user=request.user).order_by('-created').prefetch_related()
	
	# Get the user's total amount of open pledges, i.e. their total possible
	# future credit card charges / campaign contributions.
	total_pledged = pledges.filter(status=PledgeStatus.Open)
	if len(total_pledged) == 0:
		total_pledged = 0.0
	else:
		total_pledged = total_pledged.aggregate(total_pledged=Sum('amount'))['total_pledged']

	# Get the user's total amount of executed campaign contributions.
	total_contribs = pledges.filter(status=PledgeStatus.Executed)
	if len(total_contribs) == 0:
		total_contribs = 0.0
	else:
		total_contribs = total_contribs.aggregate(total_contribs=Sum('execution__charged'))['total_contribs']

	return render(request, "itfsite/home.html", {
		'pledges': pledges,
		'total_pledged': total_pledged,
		'total_contribs': total_contribs,
		})
