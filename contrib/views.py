from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.conf import settings

from twostream.decorators import anonymous_view, user_view_for

from contrib.models import Trigger, TriggerStatus, TriggerExecution, ContributorInfo, Pledge, PledgeStatus, PledgeExecution, PledgeExecutionProblem, Contribution, ActorParty, ContributionAggregate, IncompletePledge, TriggerCustomization
from contrib.utils import json_response
from contrib.bizlogic import HumanReadableValidationError, run_authorization_test

import copy
import rtyaml
import random
import decimal

# Used by unit tests to override the suggested pledge.
SUGGESTED_PLEDGE_AMOUNT = None

@anonymous_view
def trigger(request, id, trigger_customization_id):
	# get the object / redirect to canonical URL if slug does not match
	trigger = get_object_or_404(Trigger, id=id)
	if not trigger_customization_id:
		if request.path != trigger.get_absolute_url():
			return redirect(trigger.get_absolute_url())
		tcust = None
	else:
		tcust = get_object_or_404(TriggerCustomization, id=trigger_customization_id)
		if request.path != tcust.get_absolute_url():
			return redirect(tcust.get_absolute_url())
		if not tcust.visible: raise Http404()

	# Related TriggerCustomization campaigns the user can take action on.
	campaigns = TriggerCustomization.objects.filter(
		trigger=trigger,
		pledge_count__gt=0,
		visible=True)\
		.exclude(id=tcust.id if tcust else None)\
		.order_by('-pledge_count')\
		[0:8]

	# What pre-execution statistics should we show?
	#
	# If we're on a TriggerCustomization that allows all outcomes to be
	# chosen, then use that for statistics. It has the same pledge_count/
	# total_pledged interface as a Trigger.
	t_pre_ex_stats = trigger
	if tcust and tcust.outcome is None:
		t_pre_ex_stats = tcust

	# What post-execution statistics should we show?
	#
	# Defaults. Note that these are also used for triggers that have been executed
	# but for which there were no pledges that resulted in transactions, so use
	# zeros instead of None's where needed.

	outcome_totals = None
	actions = None

	total_pledges = 0
	avg_pledge = 0

	total_contribs = 0
	num_contribs = None
	avg_contrib = 0

	num_recips = 0
	by_incumb_chlngr = []

	try:
		te = trigger.execution
	except TriggerExecution.DoesNotExist:
		te = None

	if te and te.pledge_count_with_contribs > 0 and te.pledge_count >= .75 * trigger.pledge_count:
		# Get the contribution aggregates by outcome and sort by total amount of contributions.
		outcome_totals = te.get_outcomes(via=tcust)

		# Get the Actions/Actors and the total disbursed for each action
		# to the incumbent or challenger.
		actions = { a.id:
			{
				"action": a,
				"actor": a.actor,
				"outcome": a.outcome,
				"reason_for_no_outcome": a.reason_for_no_outcome,
				"total_for": decimal.Decimal(0),
				"total_against": decimal.Decimal(0)
			}
			for a in te.actions.all().select_related('actor') }

		# Pull in aggregates.
		for agg in ContributionAggregate.get_slices('action', 'incumbent', trigger_execution=te, via=tcust):
			actions[agg['action']]["total_for" if agg['incumbent'] else "total_against"] = agg['total']

		# Sort with actors that received no contributions either for or against at
		# the end of the list, since they're sort of no-data rows. After that, sort by the sum of
		# the contributions plus the negative of the contributions to their challengers. For ties,
		# sort alphabetically on name.
		actions = list(actions.values())
		actions.sort(key = lambda a : (
			a['outcome'] is None, # non-voting actors at the end
			(a['total_for'] + a['total_against']) == 0, # no contribs either way at end
			-(a['total_for'] - a['total_against']), # sort by contribs for minus contribs against
			a['reason_for_no_outcome'], # among non-voting actors, sort by the reason
			a['outcome'], # among voting actors, group by vote
			a['actor'].name_sort, # finally, by last name
			)
		)

		# Compute a few other aggregates.
		num_recips = 0
		by_incumb_chlngr = [["Incumbent", 0, "text-success"], ["Opponent", 0, "text-danger"]]
		for a in actions:
			# counts of actors/recipients
			if a['total_for'] > 0: num_recips += 1
			if a['total_against'] > 0: num_recips += 1

			# totals by incumbent/challenger
			by_incumb_chlngr[0][1] += a['total_for']
			by_incumb_chlngr[1][1] += a['total_against']

		# Compute other summary stats.
		ag = ContributionAggregate.get_slice(trigger_execution=te, via=tcust)
		total_contribs = ag['total']
		num_contribs = ag['count']
		if num_contribs > 0:
			avg_contrib = total_contribs / num_contribs
		if tcust is None:
			total_pledges = te.pledge_count_with_contribs
		else:
			total_pledges = PledgeExecution.objects.filter(trigger_execution=te, pledge__via=tcust, charged__gt=0).count()
		if total_pledges > 0:
			avg_pledge = total_contribs / total_pledges
	else:
		# If the trigger has been executed but not enough pledges
		# have completed being executed yet, then pretend like
		# nothing has been executed.
		te = None

	return render(request, "contrib/trigger.html", {
		"trigger": trigger,
		"tcust": tcust,
		"T": tcust if tcust else trigger,
		"T_pre": t_pre_ex_stats,
		
		"execution": te,
		"outcome_totals": outcome_totals,
		"alg": Pledge.current_algorithm(),
		"min_contrib": trigger.get_minimum_pledge(),

		"suggested_pledge": SUGGESTED_PLEDGE_AMOUNT or random.choice([5, 10]),
		"campaigns": campaigns,
		
		"actions": actions,
		"by_incumb_chlngr": by_incumb_chlngr,
		"total_pledges": total_pledges,
		"avg_pledge": avg_pledge,
		"total_contribs": total_contribs,
		"num_contribs": num_contribs,
		"num_recips": num_recips,
		"avg_contrib": avg_contrib,
	})

def get_user_pledges(user, request):
	# Returns the Pledges that a user owns as a QuerySet.
	ret = Pledge.objects.none() # empty QuerySet
	if user and user.is_authenticated():
		ret |= Pledge.objects.filter(user=user)
	if request.session.get('anon_pledge_created'):
		ret |= Pledge.objects.filter(id__in=request.session.get('anon_pledge_created'))
	return ret.distinct()

@user_view_for(trigger)
def trigger_user_view(request, id, trigger_customization_id):
	trigger = get_object_or_404(Trigger, id=id)
	ret = { }

	# Most recent pledge info so we can fill in defaults on the user's next pledge.
	ret["pledge_defaults"] = get_recent_pledge_defaults(request.user, request)

	# Get the user's pledge, if any, on this trigger.
	p = get_user_pledges(request.user, request).filter(trigger=trigger).first()

	if p:
		# The user already made a pledge on this. Render another template
		# to show what the user's pledge was (and how it was executed, if
		# it was.)
		import django.template
		template = django.template.loader.get_template("contrib/contrib.html")
		pe = PledgeExecution.objects.filter(pledge=p).first()
		contribs = sorted(Contribution.objects.filter(pledge_execution=pe).select_related("action"), key=lambda c : (c.recipient.is_challenger, c.action.name_sort))

		# Also include recommendations for further actions.
		recs = []
		for t in Trigger.objects.filter(status=TriggerStatus.Open).order_by('-total_pledged'):
			# Not something the user already took action on (including this pledge!).
			if p.user is not None and t.pledges.filter(user=p.user).exists(): continue
			if p.email is not None and t.pledges.filter(email=p.email).exists(): continue
			# Get up to three.
			recs.append(t)
			if len(recs) == 3:
				break

		ret["pledge_made"] = template.render(django.template.Context({
			"trigger": trigger,
			"pledge": p,
			"execution": pe,
			"contribs": contribs,
			"recommendations": recs,
			"url": request.build_absolute_uri(trigger.get_absolute_url()),
		}))

	return ret

@require_http_methods(['POST'])
@json_response
def get_user_defaults(request):
	# Get the user's past contributor information to pre-populate fields.
	# We avoid doing an actual login here because login() changes the
	# CSRF token, and a mid-page token change will cause future AJAX
	# requests to fail.

	# authenticate
	from itfsite.accounts import User
	from itfsite.betteruser import LoginException
	try:
		user = User.authenticate(request.POST['email'].strip(), request.POST['password'].strip())
	except LoginException as e:
		return { "status": "NotValid", "message": str(e) }

	# check that the user hasn't already done this
	trigger = Trigger.objects.get(id=request.POST['trigger'])
	if trigger.pledges.filter(user=user).exists():
		return { "status": "AlreadyPledged" }

	# get recent data
	return get_recent_pledge_defaults(user, request)

def get_recent_pledge_defaults(user, request):
	# Return a dictionary of information submitted with the user's most recent pledge
	# so that we can pre-fill form fields.

	ret = { }

	# Get the user's most recent Pledge. If the user has no Pledges,
	# just return the empty dict.
	pledges = get_user_pledges(user, request)
	pledge = pledges.order_by('-created').first()
	if not pledge:
		return ret

	# How many open pledges does this user already have?
	ret['open_pledges'] = pledges.filter(status=PledgeStatus.Open).count()

	# Copy Pledge fields.
	for field in ('email', 'amount', 'incumb_challgr', 'filter_party', 'filter_competitive'):
		ret[field] = getattr(pledge, field)
		if type(ret[field]).__name__ == "Decimal":
			ret[field] = float(ret[field])
		elif isinstance(ret[field], ActorParty):
			ret[field] = str(ret[field])

	# Copy contributor fields from the profile's extra dict.
	for field in ('contribNameFirst', 'contribNameLast', 'contribAddress', 'contribCity', 'contribState', 'contribZip',
		'contribOccupation', 'contribEmployer'):
		ret[field] = pledge.profile.extra['contributor'][field]

	# Return a summary of billing info to show how we would bill.
	ret['cclastfour'] = pledge.profile.cclastfour

	# And indicate which pledge we're sourcing this from so that in
	# the submit view we can retreive it again without having to
	# pass it back from the (untrusted) client.
	ret['from_pledge'] = pledge.id

	return ret

# Validates the email address a new user is providing during
# the pledge (user says they have no password). Returns "OK"
# or a human-readable error message about the email address
# not being valid.
#
# Also record every email address users enter so we can follow-up
# if the user did not finish the pledge form.
@csrf_exempt # for testing via curl
@require_http_methods(["POST"])
def validate_email(request):
	from itfsite.models import User
	from email_validator import validate_email, EmailNotValidError

	email = request.POST['email'].strip()

	# Validate the email address. If it is invalid, return the
	# error message.
	try:
		validate_email(email, allow_smtputf8=False) # DE does not accept internationalized addresses
	except EmailNotValidError as e:
		return HttpResponse(str(e), content_type="text/plain")

	if not User.objects.filter(email=email).exists():
		# Store for later, if this is not a user already with an account.
		# Only have at most one of these records per trigger-email address pair.
		IncompletePledge.objects.get_or_create(
			trigger=Trigger.objects.get(id=request.POST['trigger']),
			via=TriggerCustomization.objects.get(id=request.POST['via']) if request.POST['via'] != '0' else None,
			email=email,
			defaults={
				"extra": {
					"desired_outcome": request.POST['desired_outcome'],
					"campaign": get_sanitized_campaign(request),
				}
			})

	return HttpResponse("OK", content_type="text/plain")

@require_http_methods(['POST'])
@json_response
def submit(request):
	# In order to return something in an error condition, we
	# have to wrap the transaction *inside* a try/except and
	# form the response based on the exception.
	try:
		return create_pledge(request)
	except HumanReadableValidationError as e:
		return { "status": "error", "message": str(e) }

def get_sanitized_campaign(request):
	campaign = request.POST['campaign']
	if campaign is not None:
		if campaign.strip().lower() in ("", "none"):
			campaign = None
	return campaign

@transaction.atomic
def update_pledge_profiles(pledges, new_profile):
	# The user is updating their ContributorInfo profile. Set
	# the profile of any open pledges to the new instance. Delete
	# any ContributorInfo objects no longer needed.

	# Lock.
	pledges = pledges.select_for_update()

	# Sanity check that we do not update a pledge that is not open.
	if pledges.exclude(status=PledgeStatus.Open).exists():
		raise ValueError('pledges should be a QuerySet of only open pledges')

	# Get existing ContributorInfos on those pledges.
	prev_profiles = set(p.profile for p in pledges)

	# Update pledges to new profile.
	pledges.update(profile=new_profile)

	# Delete any of the previous ContributorInfos that are no longer needed.
	for ci in prev_profiles:
		if not ci.pledges.exists():
			ci.delete()

@transaction.atomic
def create_pledge(request):
	p = Pledge()

	# trigger
	p.trigger = Trigger.objects.get(id=request.POST['trigger'])
	p.made_after_trigger_execution = (p.trigger.status == TriggerStatus.Executed)

	# campaign (i.e. utf_campaigm) and TriggerCustomization ('via')
	p.campaign = get_sanitized_campaign(request)
	if request.POST['via'] != '0':
		p.via = TriggerCustomization.objects.get(id=request.POST['via'])

	# Set user from logged in state.
	if request.user.is_authenticated():
		# This is an authentiated user.
		p.user = request.user
		exists_filters = { 'user': p.user }

	# Anonymous user is submitting a pledge with an email address & password.
	elif request.POST.get("hasPassword") == "1":
		from itfsite.accounts import User
		from itfsite.betteruser import LoginException
		try:
			user = User.authenticate(request.POST['email'].strip(), request.POST['password'].strip())
			# Login succeeded.
			p.user = user
			exists_filters = { 'user': p.user }
		except LoginException as e:
			# Login failed. We did client-side validation so this should
			# not occur. Treat as if the user didn't provide a password.
			pass

	# Anonymous user and/or authentication failed.
	# Will do email verification below, but at least not validate it
	# (should have already been validated client side).
	if not p.user:
		p.email = request.POST.get('email').strip()

		from email_validator import validate_email, EmailNotValidError
		try:
			validate_email(p.email, allow_smtputf8=False)
		except EmailNotValidError as e:
			raise HumanReadableValidationError(str(e))

		exists_filters = { 'email': p.email }

	# If the user has already made this pledge, it is probably a
	# synchronization problem. Just redirect to that pledge.
	p_exist = Pledge.objects.filter(trigger=p.trigger, **exists_filters).first()
	if p_exist is not None:
		return { "status": "ok" }

	# Field values & validation.

	# integer fields that have the same field name as form element name
	for field in ('algorithm', 'desired_outcome'):
		try:
			setattr(p, field, int(request.POST[field]))
		except ValueError:
			raise Exception("%s is out of range" % field)

	# float fields that have the same field name as form element name
	for field in ('amount', 'incumb_challgr'):
		try:
			setattr(p, field, float(request.POST[field]))
		except ValueError:
			raise Exception("%s is out of range" % field)

	# normalize the filter_party field
	if request.POST['filter_party'] in ('DR', 'RD'):
		p.filter_party = None # no filter
	elif request.POST['filter_party'] == 'D':
		p.filter_party = ActorParty.Democratic
	elif request.POST['filter_party'] == 'R':
		p.filter_party = ActorParty.Republican

	# Validation. Some are checked client side, so errors are internal
	# error conditions and not validation problems to show the user.
	if p.algorithm != Pledge.current_algorithm()["id"]:
		raise Exception("algorithm is out of range")
	if not (0 <= p.desired_outcome < len(p.trigger.outcomes)):
		raise Exception("desired_outcome is out of range")
	if not (p.trigger.get_minimum_pledge() <= p.amount <= Pledge.current_algorithm()["max_contrib"]):
		raise Exception("amount is out of range")
	if p.incumb_challgr not in (-1, 0, 1):
		raise Exception("incumb_challgr is out of range")
	if p.filter_party == ActorParty.Independent:
		raise Exception("filter_party is out of range")
	if p.via and p.via.incumb_challgr and p.incumb_challgr != p.via.incumb_challgr:
		raise Exception("incumb_challgr is out of range (via)")
	if p.via and p.via.filter_party and p.filter_party != p.via.filter_party:
		raise Exception("filter_party is out of range (via)")

	# Get a ContributorInfo to assign to the Pledge.
	if not request.POST["copyFromPledge"]:
		# Create a new ContributorInfo record from the submitted info.
		contribdata = { }

		# string fields that go straight into the extras dict.
		contribdata['contributor'] = { }
		for field in (
			'contribNameFirst', 'contribNameLast',
			'contribAddress', 'contribCity', 'contribState', 'contribZip',
			'contribOccupation', 'contribEmployer'):
			contribdata['contributor'][field] = request.POST[field].strip()
			
		# Validate & store the billing fields.
		#
		# (Including the expiration date so that we can know that a
		# card has expired prior to using the DE token.)
		ccnum = request.POST['billingCCNum'].replace(" ", "").strip() # Stripe's javascript inserts spaces
		ccexpmonth = int(request.POST['billingCCExpMonth'])
		ccexpyear = int(request.POST['billingCCExpYear'])
		cccvc = request.POST['billingCCCVC'].strip()
		contribdata['billing'] = {
			'cc_num': ccnum, # is hashed before going into database
			'cc_exp_month': ccexpmonth,
			'cc_exp_year': ccexpyear,
		}

		# Create a ContributorInfo instance. We need a saved instance
		# so we can assign it to the pledge (the profile field is NOT NULL).
		# It's saved again below.
		ci = ContributorInfo.objects.create()
		ci.set_from(contribdata)

		# Save. We need a Pledge ID to form an authorization test.
		p.profile = ci
		p.save()

		# For logging:
		# Add information from the HTTP request in case we need to
		# block IPs or something.
		aux_data = {
			"httprequest": { k: request.META.get(k) for k in ('REMOTE_ADDR', 'REQUEST_URI', 'HTTP_USER_AGENT') },
		}

		# Perform an authorization test on the credit card and store some CC
		# details in the ContributorInfo object.
		#
		# This may raise all sorts of exceptions, which will cause the database
		# transaction to roll back. A HumanReadableValidationError will be caught
		# in the calling function and shown to the user. Other exceptions will
		# just generate generic unhandled error messages.
		#
		# Note that any exception after this point is okay because the authorization
		# will expire on its own anyway.
		run_authorization_test(p, ccnum, cccvc, aux_data)

		# Re-save the ContributorInfo instance now that it has the CC token.
		ci.save(override_immutable_check=True)

		# If the user has other open pledges, update their profiles to the new
		# ContributorInfo instance --- i.e. update their contributor and payment
		# info.
		update_pledge_profiles(get_user_pledges(p.user, request).filter(status=PledgeStatus.Open), ci)

	else:
		# This is a returning user and we are re-using info from a previous pledge.
		# That pledge might be one that hasn't had its email address confirmed yet,
		# or if it has the user might not be logged in, but the user's session cookie
		# may grant the user access to it. Or if the user is logged in, it might be
		# a pledge tied to the account.
		prev_p = Pledge.objects.get(id=request.POST["copyFromPledge"])
		if not get_user_pledges(p.user, request).filter(id=prev_p.id).exists():
			raise Exception("copyFromPledge is set to a pledge ID that the user did not create or is no longer stored in their session.")
		p.profile = prev_p.profile
		p.save()

	if not p.user:
		# The pledge needs to get confirmation of the user's email address,
		# which will lead to account creation.
		p.send_email_confirmation(first_try=True)

		# And in order for the user to be able to view the pledge on the
		# next page, prior to email confirmation, we'll need to set a token
		# to grant permission. Only hold up to 20 values.
		request.session['anon_pledge_created'] = \
			request.session.get('anon_pledge_created', [])[-20:] \
			+ [p.id]

		# Wipe the IncompletePledge because the user finished the form.
		IncompletePledge.objects.filter(email=p.email, trigger=p.trigger).delete()

	# If the user had good authentication but wasn't logged in yet, log them
	# in now. This messes up the CSRF token but the client should redirect to
	# a new page anyway.
	if p.user and p.user != request.user:
		from django.contrib.auth import login
		login(request, p.user)

	# Client will reload the page.
	return { "status": "ok" }

@json_response
def cancel_pledge(request):
	# Get the pledge. Check authorization.
	p = Pledge.objects.get(id=request.POST['pledge'])
	if not (p.user == request.user or p.id in request.session.get('anon_pledge_created', [])):
		raise Exception()
	p.delete()
	return { "status": "ok" }

@anonymous_view
def report(request):
	context = {

	}
	context.update(report_fetch_data(request))
	return render(request, "contrib/totals.html", context)

def report_fetch_data(request):
	pledge_slice_fields = { }
	slice_fields = { }

	if "trigger" in request.GET:
		# get the object & validate that there is data
		trigger = get_object_or_404(Trigger, id=request.GET['trigger'])
		pledge_slice_fields["trigger"] = trigger
		try:
			te = trigger.execution
		except TriggerExecution.DoesNotExist:
			raise Http404("This trigger is not executed.")
		if te.pledge_count_with_contribs == 0:
			raise Http404("This trigger did not have any contributions.")
		if te.pledge_count < .75 * trigger.pledge_count:
			raise Http404("This trigger is still being executed.")
		slice_fields["trigger_execution"] = te

	# form response
	ret = { }

	# number of pledges & users making pledges
	pledges = Pledge.objects.filter(**pledge_slice_fields)
	ret["users_pledging"] = pledges.values("user").distinct().count()
	ret["pledges"] = pledges.count()
	from django.db.models import Sum
	ret["pledge_aggregate"] = pledges.aggregate(amount=Sum('amount'))["amount"]

	# number of executed pledges and users with executed pledges
	pledge_executions = PledgeExecution.objects.filter(problem=PledgeExecutionProblem.NoProblem, **slice_fields)
	ret["users"] = pledge_executions.values("pledge__user").distinct().count()
	ret["num_triggers"] = pledge_executions.values("trigger_execution").distinct().count()
	ret["first_contrib_date"] = pledge_executions.order_by('created').first().created
	ret["last_contrib_date"] = pledge_executions.order_by('created').last().created

	# aggregate count and amount of campaign contributions
	ret["total"] = ContributionAggregate.get_slice(**slice_fields)
	if ret["total"]["count"] > 0:
		ret["total"]["average"] = ret["total"]["total"] / ret["total"]["count"]

	if "trigger_execution" in slice_fields:
		# Aggregates by outcome.
		ret['outcomes'] = ContributionAggregate.get_slices('outcome', **slice_fields)

	# Aggregates by actor.
	from collections import defaultdict
	ret['actors'] = defaultdict(lambda : defaultdict( lambda : decimal.Decimal(0) ))
	for rec in ContributionAggregate.get_slices('actor', 'incumbent', **slice_fields):
		ret['actors'][rec['actor']]['actor'] = rec['actor']
		ret['actors'][rec['actor']][str(rec['incumbent'])] += rec['total']
	ret['actors'] = sorted(ret['actors'].values(), key = lambda x : (-(x['True'] + x['False']), -x['True'], x['actor'].name_sort))

	# Aggregates by incumbent/chalenger.
	ret['by_incumb_chlngr'] = ContributionAggregate.get_slices('incumbent', **slice_fields)

	# Aggregates by party.
	ret['by_party'] = ContributionAggregate.get_slices('party', **slice_fields)

	# report
	return ret
