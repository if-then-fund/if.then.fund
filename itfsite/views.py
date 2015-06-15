from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone

from itfsite.models import Organization, Notification, NotificationsFrequency
from contrib.models import Pledge, PledgeExecution, PledgeStatus

from twostream.decorators import anonymous_view, user_view_for

def homepage(request):
	# The site homepage.

	# Get all of the open triggers that a user might participate in.
	from contrib.models import Trigger, TriggerStatus
	open_triggers = Trigger.objects.filter(status=TriggerStatus.Open).order_by('-total_pledged')
	recent_executed_triggers = Trigger.objects.filter(status=TriggerStatus.Executed).select_related("execution").order_by('-execution__created')

	# Exclude triggers in the process of being executed from the 'recent' list, because
	# that list shows aggregate stats that are not yet valid
	recent_executed_triggers = [t for t in recent_executed_triggers
		if t.pledge_count <= t.execution.pledge_count]

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
	open_pledges = pledges.filter(status=PledgeStatus.Open)
	if len(open_pledges) == 0:
		total_pledged = 0.0
	else:
		total_pledged = open_pledges.aggregate(total_pledged=Sum('amount'))['total_pledged']

	# Get the user's total amount of executed campaign contributions.
	total_contribs = pledges.filter(status=PledgeStatus.Executed)
	if len(total_contribs) == 0:
		total_contribs = 0.0
	else:
		total_contribs = total_contribs.aggregate(total_contribs=Sum('execution__charged'))['total_contribs']

	# Get the user's distinct ContributorInfo objects on *open* Pledges,
	# indicating future submitted info.
	if len(open_pledges) == 0:
		profiles = []
	else:
		profiles = set(p.profile for p in open_pledges)

	return render(request, "itfsite/user_home.html", {
		'pledges': pledges,
		'profiles': profiles,
		'total_pledged': total_pledged,
		'total_contribs': total_contribs,
		'notifs_freq': request.user.notifs_freq.name,
		})

@login_required
def user_contribution_details(request):
	# Assemble a table of all line-item transactions.
	items = []

	# Contributions.
	from contrib.models import Contribution
	contribs = Contribution.objects.filter(pledge_execution__pledge__user=request.user).select_related('pledge_execution', 'recipient', 'action', 'pledge_execution__trigger_execution__trigger')
	def contrib_line_item(c):
		return {
			'when': c.pledge_execution.created,
			'amount': c.amount,
			'recipient': c.name_long(),
			'trigger': c.pledge_execution.trigger_execution.trigger,
			'sort': (c.pledge_execution.created, 1, c.recipient.is_challenger, c.id),
		}
	items.extend([contrib_line_item(c) for c in contribs])

	# Fees.
	def fees_line_item(p):
		return {
			'when': p.created,
			'amount': p.fees,
			'recipient': 'if.then.fund fees',
			'trigger': p.trigger_execution.trigger,
			'sort': (p.created, 0),
		}
	items.extend([fees_line_item(p) for p in PledgeExecution.objects.filter(pledge__user=request.user).select_related('trigger_execution__trigger')])

	# Sort all together.
	items.sort(key = lambda x : x['sort'], reverse=True)

	if request.method == 'GET':
		# GET => HTML
		return render(request, "itfsite/user_contrib_details.html", {
			'items': items,
			})
	else:
		# POST => CSV
		from django.http import HttpResponse
		import csv
		from io import StringIO
		buf = StringIO()
		writer = csv.writer(buf)
		writer.writerow(['date', 'amount', 'recipient', 'action'])
		for item in items:
			writer.writerow([
				item['when'].isoformat(),
				item['amount'],
				item['recipient'],
				request.build_absolute_uri(item['trigger'].get_absolute_url()),
				])
		buf = buf.getvalue().encode('utf8')

		if True:
			resp = HttpResponse(buf, content_type="text/csv")
			resp['Content-Disposition'] = 'attachment; filename="contributions.csv"'
		else:
			resp = HttpResponse(buf, content_type="text/plain")
			resp['Content-Disposition'] = 'inline'
		resp["Content-Length"] = len(buf)
		return resp

@anonymous_view
def org_landing_page(request, path, id, slug):
	# get the object / redirect to canonical URL if slug does not match
	org = get_object_or_404(Organization, id=id)
	if request.path != org.get_absolute_url():
		return redirect(org.get_absolute_url())

	# get the triggers to display & sort
	from contrib.models import TriggerStatus
	triggers = list(org.triggers.filter(visible=True,
		trigger__status__in=(TriggerStatus.Open, TriggerStatus.Executed))\
		.select_related('trigger'))
	triggers.sort(key = lambda t : (t.trigger.status==TriggerStatus.Open, t.created), reverse=True)

	return render(request, "itfsite/organization.html", {
		"org": org,
		"triggers": triggers,
	})

def query_facebook(opengraph_id):
	import json
	import requests
	r = requests.get(
		"https://graph.facebook.com/v2.2/%s?access_token=%s" % (opengraph_id, settings.FACEBOOK_ACCESS_TOKEN),
		timeout=15,
		verify=True, # check SSL cert (is default, actually)
		)
	r.raise_for_status()
	return r.json()

def extract_opengraph_id(facebook_url):
	import re
	m = re.match("https?://www.facebook.com/pages/[^/]+/(\d+)", facebook_url)
	if m:
		return m.group(1)
	m = re.match("https?://www.facebook.com/([^/\?]+)", facebook_url)
	if m:
		return m.group(1)
	return None

@anonymous_view
def org_resource(request, path, id, slug, resource_type):
	org = get_object_or_404(Organization, id=id)
	if resource_type == "banner":
		# Get the org's banner image from their Facebook cover image.
		if org.facebook_url:
			graph_id = extract_opengraph_id(org.facebook_url)
			if graph_id:
				graph = query_facebook(graph_id) # Page
				graph = query_facebook(graph['cover']['id']) # Cover image
				desired_width = int(request.GET.get('width', '1024'))
				url = min(graph['images'], key = lambda im : abs(im['width']-desired_width))['source']
				return redirect(url)

		# No banner image available. Return the smallest transparent PNG.
		# Better than a 404. h/t http://garethrees.org/2007/11/14/pngcrush/
		return HttpResponse(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
			content_type="image/png")

	raise Http404()

@login_required
def dismiss_notifications(request):
	# Mark all of the supplied notification IDs as dismissed.
	Notification.objects.filter(
		user=request.user,
		id__in=request.POST.get('ids', '0').split(','),
		dismissed_at=None,
		)\
		.update(dismissed_at=timezone.now())
		
	# Return something, but this is ignored.
	return HttpResponse('OK', content_type='text/plain')

@login_required
def set_email_settings(request):
	user = request.user
	try:
		user.notifs_freq = NotificationsFrequency[request.POST['notifs_freq']]
		user.save()
	except (KeyError, ValueError) as e:
		return HttpResponse(repr(e), content_type='text/plain', status=400)
	# Return something, but this is ignored.
	return HttpResponse('OK', content_type='text/plain')
