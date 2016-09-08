from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone

from itfsite.models import Organization, Notification, NotificationsFrequency, Campaign, CampaignStatus
from itfsite.middleware import get_branding

from twostream.decorators import anonymous_view, user_view_for

def render2(request, template, *args, **kwargs):
	import os.path
	from django.template import TemplateDoesNotExist
	template1 = os.path.join('branding', get_branding(request)['BRAND_ID'], 'templates', template)
	try:
		# Try a brand-specific template.
		return render(request, template1, *args, **kwargs)
	except TemplateDoesNotExist as e:
		# Raise if the template that doesn't exist is one that is loaded by an include tag.
		if hasattr(e, 'django_template_source'):
			raise
		# Try a default template.
		return render(request, template, *args, **kwargs)

@anonymous_view
def homepage(request):
	# The site homepage.

	# What campaigns *can* we show (logically)? Open campaigns for the brand we're looking at.
	open_campaigns = Campaign.objects.filter(status=CampaignStatus.Open, brand=get_branding(request)['BRAND_INDEX'])

	# How many to show?
	count = 12 if not settings.DEBUG else 100

	# Actually show recent campaigns (with some activity) + top performing campaigns.
	#
	# To efficiently query top performing campaigns we order by the sum of total_pledged (which only contains
	# Pledges made prior to trigger execution) and total_contributions (which only exists after the trigger
	# has been executed), since we don't have a field that just counts a simple total (ugh).
	open_campaigns = open_campaigns\
		.annotate(total=Sum('contrib_triggers__total_pledged')+Sum('contrib_triggers__execution__total_contributions'))\
		.exclude(total=None) # no Trigger associated with the Campaign
	open_campaigns = set( # uniqify
		c for c in 
		  list(open_campaigns.order_by('-created')[0:count])
		+ list(open_campaigns.order_by("-total")[0:count])
		if c.total > 0
		)
	if len(open_campaigns) > 0:
		# Order by a mix of recency and popularity. Prefer recency a bit.
		from math import sqrt
		newest = max(c.created for c in open_campaigns)
		oldest = min(c.created for c in open_campaigns)
		max_t = max(float(getattr(c, 'total', 0)) for c in open_campaigns) or 1.0 # Decimal => float
		open_campaigns = sorted(open_campaigns, key = lambda campaign:
			    1.1 - 1.1*(newest-campaign.created).total_seconds()/((newest-oldest).total_seconds() or 1)
			  + sqrt(float(getattr(campaign, 'total', 0)) / max_t)
			, reverse=True)[0:count]

	return render2(request, "itfsite/homepage.html", {
		"open_campaigns": open_campaigns,
	})

def simplepage(request, pagename):
	# Renders a page that has no special processing.
	# simplepage is validated by urls.py.
	pagename = pagename.replace('/', '-')
	return render2(request, "itfsite/%s.html" % pagename)

@login_required
def user_home(request):
	from contrib.models import Pledge, PledgeStatus

	# Get the user's actions that took place on the brand site that the user is actually on.
	brand_filter = { "via_campaign__brand": get_branding(request)['BRAND_INDEX'] }
	pledges = Pledge.objects.filter(user=request.user, **brand_filter).prefetch_related()
	actions = list(pledges)
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
	brand = get_branding(request) # only looking at contributions made on the site the user is looking at
	from contrib.models import Contribution
	contribs = Contribution.objects.filter(
		pledge_execution__pledge__user=request.user,
		pledge_execution__pledge__via_campaign__brand=brand['BRAND_INDEX'])\
		.select_related('pledge_execution', 'recipient', 'action', 'pledge_execution__trigger_execution__trigger')
	def contrib_line_item(c):
		return {
			'when': c.pledge_execution.created,
			'amount': c.amount,
			'recipient': c.name_long(),
			'trigger': c.pledge_execution.trigger_execution.trigger,
			'campaign': c.pledge_execution.pledge.via_campaign,
			'sort': (c.pledge_execution.created, 1, c.recipient.is_challenger, c.id),
		}
	items.extend([contrib_line_item(c) for c in contribs])

	# Fees.
	def fees_line_item(p):
		return {
			'when': p.created,
			'amount': p.fees,
			'recipient': '%s fees' % brand['SITE_NAME'],
			'trigger': p.trigger_execution.trigger,
			'campaign': p.pledge.via_campaign,
			'sort': (p.created, 0),
		}
	items.extend([fees_line_item(p) for p in PledgeExecution.objects.filter(
		pledge__user=request.user,
		pledge__via_campaign__brand=brand['BRAND_INDEX'])\
		.select_related('trigger_execution__trigger')])

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
		writer.writerow(['date', 'amount', 'recipient', 'action', 'link'])
		for item in items:
			writer.writerow([
				item['when'].isoformat(),
				item['amount'],
				item['recipient'],
				item['campaign'].title,
				item['campaign'].get_short_url(),
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

def campaign(request, id, action, api_format_ext):
	# get the object, make sure it is for the right brand that the user is viewing
	campaign = get_object_or_404(Campaign, id=id, brand=get_branding(request)['BRAND_INDEX'])

	# redirect to canonical URL if slug does not match
	# (pass along any query string variables like utm_campaign; when
	# a .json page is requested, the canonical path omits the slug)
	if not api_format_ext:
		canonical_path = campaign.get_absolute_url() + (api_format_ext or "")
	else:
		canonical_path = "/a/%d%s" % (campaign.id, api_format_ext)
	if action:
		canonical_path += "/" + action
	qs = (("?"+request.META['QUERY_STRING']) if request.META['QUERY_STRING'] else "")
	if request.path != canonical_path:
		@anonymous_view
		def redirector(request):
			return redirect(canonical_path+qs)
		return redirector(request)

	# The rest of this view is handled in the next two functions.
	if action is None:
		f = campaign_show
	elif api_format_ext is not None:
		raise Http404()
	elif action == "contribute":
		f = campaign_action_trigger
	else:
		raise Http404()

	# Cache?
	if campaign.status == CampaignStatus.Draft:
		# When a campaign is in draft status, we won't
		# cache the output to allow the user editing the
		# campaign's settings to reload the page to see
		# updated settings.
		pass
	else:
		# As soon as the campaign exits draft status we'll
		# mark the response as cachable so that the http
		# layer strongly caches the output.
		pass # f = anonymous_view(f)

	return f(request, campaign, api_format_ext == ".json")

def campaign_show(request, campaign, is_json_api):
	# What Trigger and TriggerCustomization should we show?
	trigger, tcust = campaign.get_active_trigger()

	if trigger:
		outcome_strings = (tcust or trigger).outcome_strings()
		for i, os in enumerate(outcome_strings): os["id"] = i
	else:
		outcome_strings = []

	# for .json calls, just return data in JSON format
	if is_json_api:
		from .utils import json_response, serialize_obj, mergedicts
		brand = get_branding(request)
		return json_response({
			"site": {
				"name": brand["SITE_NAME"],
				"link": brand["ROOT_URL"],
				"logo": {
					"w500": brand["ROOT_URL"] + "/static/branding/" + brand["BRAND_ID"] + "/logo.png",
				}
			},
			"campaign": mergedicts(
				serialize_obj(campaign, keys=("id", "created", "updated", "title", "headline", "subhead", "body_text"),
						render_text_map={ "subhead": "subhead_format", "body_text": "body_format" }),
				{
					"link": request.build_absolute_uri(campaign.get_absolute_url()),
				}),
			"trigger": mergedicts(
				serialize_obj(trigger, keys=("id", "created", "updated", "title", "description"),
						render_text_map={ "description": "description_format" }),
				{
					"type": trigger.trigger_type.title,
					"outcomes": outcome_strings,
					"strings": trigger.trigger_type.strings,
					"max_split": trigger.max_split(),
					"desired_outcome": outcome_strings[tcust.outcome] if tcust else None,
				}) if trigger else None,
			})

	try:
		pref_outcome = int(request.GET["outcome"])
		if pref_outcome < 0 or pref_outcome >= len(outcome_strings): raise ValueError()
	except:
		pref_outcome = -1 # it's hard to distinguish 0 from None in templates

	# render page

	splash_image_qs = ""
	try:
		splash_image_qs += "&blur=" + ("1" if campaign.extra["style"]["splash"]["blur"] else "")
	except:
		pass
	try:
		splash_image_qs += "&brightness=" + str(campaign.extra["style"]["splash"]["brightness"] or "")
	except:
		pass

	# a/b testing
	import random
	experimental_condition = random.choice([1])

	return render(request, "itfsite/campaign_exp%d.html" % experimental_condition, {
		"campaign": campaign,
		"splash_image_qs": splash_image_qs,

		# for contrib.Trigger actions
		"trigger": trigger,
		"tcust": tcust,
		"trigger_outcome_strings": outcome_strings,
		"pref_outcome": pref_outcome,

		# for a/b testing
		"experiment": experimental_condition,
		})

def campaign_action_trigger(request, campaign, is_json_api):
	import json
	from contrib.models import TriggerStatus, Pledge
	from contrib.bizlogic import get_pledge_recipient_breakdown

	# What Trigger and TriggerCustomization should we show?
	trigger, tcust = campaign.get_active_trigger()
	if not trigger: raise Http404()
	outcome_strings = (tcust or trigger).outcome_strings()

	# What outcome is selected? Validate against trigger and
	# trigger customization.
	try:
		outcome = int(request.GET.get("outcome"))
		if outcome < 0 or outcome >= len(trigger.outcomes):
			raise ValueError("outcome is out of range")
		if tcust and tcust.has_fixed_outcome() and outcome != tcust.outcome:
			raise ValueError("outcome does not match TriggerCustomization")
	except (ValueError, TypeError):
		raise Http404()

	# render page
	return render(request, "itfsite/campaign_action.html", {
		"campaign": campaign,

		"trigger": trigger,
		"tcust": tcust,
		"all_outcome_strings": outcome_strings,
		"outcome": outcome,
		"outcome_strings": outcome_strings[outcome],
		"suggested_pledge": trigger.get_suggested_pledge(),
		"alg": Pledge.current_algorithm(),
		"trigger_recips": json.dumps(get_pledge_recipient_breakdown(trigger) if trigger and trigger.status == TriggerStatus.Executed else None),

		})


@user_view_for(campaign)
def campaign_user_view(request, id, action, api_format_ext):
	from contrib.views import get_recent_pledge_defaults, get_user_pledges, render_pledge_template

	campaign = get_object_or_404(Campaign, id=id)

	ret = { }
	ret["actions"] = []

	# What actions has the user already taken?
	pledges = get_user_pledges(request.user, request).filter(trigger__campaigns=campaign).order_by('-created')

	# CONTRIB

	# Most recent pledge info so we can fill in defaults on the user's next pledge.
	ret["pledge_defaults"] = get_recent_pledge_defaults(request.user, request)

	# Pull in all of the user's existing pledges for this campaign.
	ret["actions"] += [
		{
			"type": "contrib.Pledge",
			"date": pledge.created.isoformat(),
			"trigger": pledge.trigger.id,
			"rendered": render_pledge_template(request, pledge, campaign, show_long_title=len(pledges) > 1),
		} for pledge in pledges
	]

	# Other stuff.
	ret["actions"].sort(key = lambda x : x["date"], reverse=True)
	ret["show_utm_tool"] = (request.user.is_authenticated() and request.user.is_staff)

	return ret

def create_automatic_campaign_from_trigger(trigger):
	# Create/update a Campaign
	if not trigger.extra.get('auto-campaign'):
		# Create a new empty campaign - details are filled in below.
		campaign = Campaign.objects.create(
			brand=1,
			owner=None,
			status=CampaignStatus.Open,
			extra={},
			# other fields set below
		)

		# Associate this Campaign with the Trigger.
		trigger.extra['auto-campaign'] = campaign.id
		trigger.save()

		if not campaign.extra: campaign.extra = { }
		campaign.extra['auto'] = "create_automatic_campaign_from_trigger"

	return update_automatic_campaign_from_trigger(trigger)

def update_automatic_campaign_from_trigger(trigger):
	# Update the campaign based on the info in the trigger.

	campaign = Campaign.objects.get(id=trigger.extra['auto-campaign'])

	from contrib.models import TriggerStatus
	from itfsite.utils import TextFormat
	from django.template.defaultfilters import slugify
	campaign.title = trigger.title
	campaign.slug = slugify(trigger.title)
	campaign.subhead = trigger.extra['auto-campaign-subhead']
	campaign.subhead_format = TextFormat.Markdown
	campaign.headline = trigger.extra['auto-campaign-headline']
	campaign.body_text = trigger.description
	campaign.body_format = trigger.description_format
	campaign.status = CampaignStatus.Open
	campaign.save()

	if trigger not in campaign.contrib_triggers.all():
		campaign.contrib_triggers.add(trigger)

	return campaign

@anonymous_view
def redirect_for_bill_cosponsors(request, bill_id):
	# Redirect to an automaticallg generated campaign for the (co)sponsors
	# of the given bill and its companion bill.
	from contrib.models import Trigger
	from contrib.legislative import create_trigger_for_sponsors
	try:
		# Get the trigger. If it's already created, don't update it
		# so that we don't have to wait on the GovTrack API to continue.
		# TODO: Set update to False in production.
		trigger = create_trigger_for_sponsors(bill_id, with_companion=True, update=True)
	except ValueError:
		# Invalid bill ID.
		raise Http404()

	# Get/update the campaign.
	campaign = create_automatic_campaign_from_trigger(trigger)

	# Redirect.
	return redirect(campaign.get_absolute_url())
