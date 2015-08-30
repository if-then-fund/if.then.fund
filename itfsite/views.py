from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone

from itfsite.models import Organization, Notification, NotificationsFrequency, Campaign, CampaignStatus

from twostream.decorators import anonymous_view, user_view_for

def homepage(request):
	# The site homepage.

	return render(request, "itfsite/homepage.html", {
		"open_campaigns": Campaign.objects.filter(status=CampaignStatus.Open).order_by('-created')[0:16], # 16 for debugging
	})

def simplepage(request, pagename):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.
	pagename = pagename.replace('/', '-')
	return render(request, "itfsite/%s.html" % pagename)

@login_required
def user_home(request):
	from contrib.models import Pledge, PledgeStatus
	from letters.models import UserLetter

	# Get the user's actions.
	pledges = Pledge.objects.filter(user=request.user).prefetch_related()
	letters = UserLetter.objects.filter(user=request.user).prefetch_related()
	actions = list(pledges) + list(letters)
	actions.sort(key = lambda obj : obj.created, reverse=True)
	
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
		'actions': actions,

		'profiles': profiles,

		'letters_written': letters.count(),
		'total_pledged': total_pledged,
		'total_contribs': total_contribs,

		'notifs_freq': request.user.notifs_freq.name,
		})

@login_required
def user_contribution_details(request):
	from contrib.models import PledgeExecution

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

	return render(request, "itfsite/organization.html", {
		"org": org,
		"campaigns": org.open_campaigns(),
	})

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

@anonymous_view
def campaign(request, id):
	# get the object, redirect to canonical URL if slug does not match
	# (pass along any query string variables like utm_campaign)
	campaign = get_object_or_404(Campaign, id=id)
	qs = (("?"+request.META['QUERY_STRING']) if request.META['QUERY_STRING'] else "")
	if request.path != campaign.get_absolute_url():
		return redirect(campaign.get_absolute_url()+qs)

	from contrib.models import TriggerStatus, TriggerCustomization, Pledge

	# What trigger should the user take action on?
	trigger = campaign.contrib_triggers.filter(status__in=(TriggerStatus.Open,TriggerStatus.Executed)).order_by('-created').first()
	tcust = None
	if trigger and campaign.owner: # campaigns without an owner cannot have a trigger customization
		tcust = TriggerCustomization.objects.filter(trigger=trigger, owner=campaign.owner).first()

	# Which letter-writing campaign should the user take action on?
	from letters.models import LettersCampaign, CampaignStatus as LettersCampaignStatus, UserLetter
	from letters.views import state_abbrs
	letters_campaign = campaign.letters.filter(status=LettersCampaignStatus.Open).order_by('-created').first()

	# render page
	return render(request, "itfsite/campaign.html", {
		"campaign": campaign,

		# for contrib.Trigger actions
		"trigger": trigger,
		"tcust": tcust,
		"trigger_outcome_strings": tcust.outcome_strings() if tcust else trigger.outcome_strings(),
		"suggested_pledge": 5,
		"alg": Pledge.current_algorithm(),

		# for letter writing campaigns
		"letters_campaign": letters_campaign,
		"state_abbrs": state_abbrs,
		"letters_sent": UserLetter.objects.filter(letterscampaign__campaigns=campaign).count(),

		})
	
@user_view_for(campaign)
def campaign_user_view(request, id):
	from contrib.views import get_recent_pledge_defaults, get_user_pledges, render_pledge_template
	from letters.views import get_recent_letter_defaults, get_user_letters, render_letter_template

	campaign = get_object_or_404(Campaign, id=id)

	ret = { }
	ret["actions"] = []

	# What actions has the user already taken?
	pledges = get_user_pledges(request.user, request).filter(trigger__campaigns=campaign).order_by('-created')
	letters = get_user_letters(request.user, request).filter(letterscampaign__campaigns=campaign).order_by('-created')

	# CONTRIB

	# Most recent pledge info so we can fill in defaults on the user's next pledge.
	ret["pledge_defaults"] = get_recent_pledge_defaults(request.user, request)

	# Pull in all of the user's existing pledges for this campaign.
	ret["actions"] += [
		{
			"type": "contrib.Pledge",
			"date": pledge.created.isoformat(),
			"trigger": pledge.trigger.id,
			"rendered": render_pledge_template(request, pledge, campaign, show_long_title=len(pledges)+len(letters) > 1),
		} for pledge in pledges
	]

	# LETTERS

	ret["letter_defaults"] = get_recent_letter_defaults(request.user, request)

	ret["actions"] += [
		{
			"type": "letters.UserLetter",
			"date": letter.created.isoformat(),
			"letterscampaign": letter.letterscampaign.id,
			"rendered": render_letter_template(request, letter, show_long_title=len(pledges)+len(letters) > 1),
		} for letter in letters
	]

	# Other stuff.
	ret["actions"].sort(key = lambda x : x["date"], reverse=True)
	ret["show_utm_tool"] = (request.user.is_authenticated() and request.user.is_staff)

	return ret
