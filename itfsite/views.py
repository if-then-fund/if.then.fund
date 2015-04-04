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

	return render(request, "itfsite/user_home.html", {
		'pledges': pledges,
		'total_pledged': total_pledged,
		'total_contribs': total_contribs,
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
