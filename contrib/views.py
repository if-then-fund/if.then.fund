from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.conf import settings

from twostream.decorators import anonymous_view, user_view_for

from contrib.models import Trigger, TriggerStatus, TriggerExecution, ContributorInfo, Pledge, PledgeStatus, PledgeExecution, PledgeExecutionProblem, Contribution, ActorParty, IncompletePledge, TriggerCustomization
from contrib.utils import json_response
from contrib.bizlogic import HumanReadableValidationError, run_authorization_test

import copy
import rtyaml
import random
import decimal

def get_user_pledges(user, request):
	# Returns the Pledges that a user owns as a QuerySet.
	# (A simple "|" of QuerySets is easier to construct but it creates a UNION
	# that then requires a DISTINCT which in Postgres is incompatible with
	# SELECT FOR UPDATE. So we form a proper 'WHERE x OR y' clause.)
	
	filters = Q(id=-99999) # a dummy filter that excludes everything, in case no other filters apply

	if user and user.is_authenticated():
		filters |= Q(user=user)

	anon_user = request.session.get("anonymous-user")
	if anon_user is not None:
		filters |= Q(anon_user_id=anon_user)

	return Pledge.objects.filter(filters)


@require_http_methods(['POST'])
@ensure_csrf_cookie
@json_response
def get_user_defaults(request):
	# A user is in the process of making a pledge and wants to log in.
	# Authenticate, log them in, and then return default values to
	# pre-populate fields like their name & address.

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

	# login() resets the CSRF token. This might be redundant, but
	# @ensure_csrf_cookie ensures that we send that CSRF token in
	# the response (as a cookie). The twostream library will detect
	# the new token in the AJAX response.
	from django.contrib.auth import login
	login(request, user)

	# Return the user's past contributor information to pre-populate fields.
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
	ret['emailEmail'] = pledge.get_email()
	for field in ('amount', 'incumb_challgr', 'filter_party', 'filter_competitive'):
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
	from itfsite.models import User, Campaign
	from email_validator import validate_email, EmailNotValidError

	email = request.POST['email'].strip()

	# Validate the email address. If it is invalid, return the
	# error message. See create_pledge below - we repeat this
	# as server-slide validation again.
	try:
			 # DE does not accept internationalized addresses
			 # during testing, don't check deliverability so that tests can operate off-line
		validate_email(email, allow_smtputf8=False, check_deliverability=settings.VALIDATE_EMAIL_DELIVERABILITY)
	except EmailNotValidError as e:
		return HttpResponse(str(e), content_type="text/plain")

	if not User.objects.filter(email=email).exists():
		# Store for later, if this is not a user already with an account.
		# We store a max of one per email address.
		IncompletePledge.objects.get_or_create(
			email=email,
			defaults={
				"trigger": Trigger.objects.get(id=request.POST['trigger']),
				"via_campaign": Campaign.objects.get(id=request.POST['via_campaign']),
				"extra": {
					"desired_outcome": request.POST['desired_outcome'],
					"ref_code": get_sanitized_ref_code(request),
				}
			})

	return HttpResponse("OK", content_type="text/plain")

@require_http_methods(['POST'])
@json_response
def submit(request):
	try:
		# Create an un-saved Pledge instance. If the user is anonymous,
		# it may create an AnonymousUser instance and associate with the
		# user's session.
		p = create_pledge_object(request)

		# If the Trigger is executed, validate that there are going
		# to be any recipients.
		if p.trigger.status == TriggerStatus.Executed:
			from contrib.bizlogic import get_pledge_recipients
			if len(get_pledge_recipients(p)) == 0:
				return { "status": "error", "message": "The filters you chose have eliminated all possible recipients!" }

		# Get contributor info, save, and run a credit card
		# authorization.
		if not reuse_authorized_contributorinfo(p, request):
			save_and_authorize_contributorinfo(p, request)

	except HumanReadableValidationError as e:
		return { "status": "error", "message": str(e) }
	except AlreadyPledgedError as e:
		return { "status": "already-pledged" }

	# If the Trigger has been executed and possibly other conditions are met, then we
	# can execute the Pledge immediately.
	if p.can_execute():
		# refresh the object - it's confused now because we pulled it
		# out of a transaction? lots of weird errors with Sqlite
		p = Pledge.objects.get(id=p.id)
		p.execute()

	# If the user is anonymous...
	if not p.user:
		# The pledge needs to get confirmation of the user's email address,
		# which will lead to account creation. We must do this after pledge
		# execution so that the email that is sent knows the status of the
		# pledge.
		p.anon_user.send_email_confirmation()

		# Wipe the IncompletePledge because the user finished the form.
		IncompletePledge.objects.filter(email=p.anon_user.email, trigger=p.trigger).delete()

	# Done.
	return {
		"status": "ok",
		"html": render_pledge_template(request, p, p.via_campaign, response_page=True),
	}

def get_sanitized_ref_code(request):
	ref_code = request.POST['ref_code']
	if ref_code is not None:
		if ref_code.strip().lower() in ("", "none"):
			ref_code = None
	return ref_code

@transaction.atomic
def update_pledge_profiles(newest_pledge):
	# When a Pledge is created with new profile information, all
	# of the user's still-open Pledges are updated to use the new
	# profile.

	# Get all of the user's open pledges, excluding p.
	pledges = Pledge.objects\
		.filter(status=PledgeStatus.Open)\
		.exclude(id=newest_pledge.id)
	if newest_pledge.user:
		pledges = pledges.filter(user=newest_pledge.user)
	else:
		pledges = pledges.filter(anon_user=newest_pledge.anon_user)

	# Lock.
	pledges = pledges.select_for_update()

	# Get existing ContributorInfos on those pledges.
	prev_profiles = set(p.profile for p in pledges)

	# Update the open pledges to new profile.
	pledges.update(profile=newest_pledge.profile)

	# Delete any of the previous ContributorInfos that are no longer needed.
	# (Some may be used on non-open Pledges and cannot be deleted.)
	for ci in prev_profiles:
		if ci.can_delete():
			ci.delete()

class InvalidArgumentError(Exception):
	pass

class AlreadyPledgedError(Exception):
	def __init__(self, existing_pledge):
		self.existing_pledge = existing_pledge

def create_pledge_object(request):
	# Creates an un-saved Pledge instance.
	#
	# Raises an AlreadyPledgedError if the user has already made a Pledge
	# for the specified Trigger.

	p = Pledge()

	# trigger

	try:
		p.trigger = Trigger.objects.get(id=request.POST['trigger'])
	except Trigger.DoesNotExist:
		raise InvalidArgumentError("The trigger ID is invalid.")
	if p.trigger.status == TriggerStatus.Draft:
		raise InvalidArgumentError("This trigger is still a draft. A contribution cannot yet be made.")
	elif p.trigger.status not in (TriggerStatus.Open, TriggerStatus.Executed):
		raise InvalidArgumentError("This trigger is in the wrong state to make a contribution.")

	p.made_after_trigger_execution = (p.trigger.status == TriggerStatus.Executed)

	# ref_code (i.e. utm_campaign code) and Campaign ('via_campaign')

	from itfsite.models import Campaign, AnonymousUser
	p.ref_code = get_sanitized_ref_code(request)
	p.via_campaign = Campaign.objects.get(id=request.POST['via_campaign'])

	# user / anon_user

	if request.user.is_authenticated():
		# This is an authentiated user.
		p.user = request.user
		exists_filters = { 'user': p.user }

	else:
		# This is an anonymous user.
		email = request.POST.get('email').strip()

		# If the user makes multiple actions anonymously, we'll associate
		# a single AnonymousUser instance with all of the Pledges.
		anon_user = AnonymousUser.objects.filter(id=request.session.get("anonymous-user")).first()
		if anon_user and anon_user.email == email:
			# Reuse this AnonymousUser instance.
			p.anon_user = anon_user
		else:
			# Validate email. See our function validate_email above.
			from email_validator import validate_email, EmailNotValidError
			try:
				validate_email(email, allow_smtputf8=False, check_deliverability=settings.VALIDATE_EMAIL_DELIVERABILITY)
			except EmailNotValidError as e:
				raise HumanReadableValidationError(str(e))

			# Create a new AnonymousUser instance.
			p.anon_user = AnonymousUser.objects.create(email=email)

			# Record in the session so the user can reuse this instance and
			# to grant the user temporary (within the session cookie's session)
			# access to the resources the user creates while anonymous.
			request.session['anonymous-user'] = p.anon_user.id

		exists_filters = { 'anon_user': p.anon_user }

	# If the user has already made this pledge, it is probably a
	# synchronization problem. Just redirect to that pledge.
	p_exist = Pledge.objects.filter(trigger=p.trigger, **exists_filters).first()
	if p_exist is not None:
		raise AlreadyPledgedError(p_exist)

	# Field values & validation.

	def set_field(model_field, form_field, converter):
		try:
			setattr(p, model_field, converter(request.POST[form_field]))
		except ValueError:
			raise InvalidArgumentError("%s is out of range" % form_field)

	set_field('algorithm', 'algorithm', int)
	set_field('desired_outcome', 'desired_outcome', int)
	set_field('incumb_challgr', 'incumb_challgr', int) # -1, 0, 1 --- but one day we want a slider so model field is a float
	set_field('amount', 'amount', decimal.Decimal)
	if request.POST.get("contribTipOrg"):
		set_field('tip_to_campaign_owner', 'tip_amount', decimal.Decimal)

	if request.POST['filter_party'] in ('DR', 'RD'):
		p.filter_party = None # no filter
	else:
		p.filter_party = ActorParty.from_letter(request.POST['filter_party'])

	# Validation. Some are checked client side, so errors are internal
	# error conditions and not validation problems to show the user.
	if p.algorithm != Pledge.current_algorithm()["id"]:
		raise InvalidArgumentError("algorithm is out of range")
	if not (0 <= p.desired_outcome < len(p.trigger.outcomes)):
		raise InvalidArgumentError("desired_outcome is out of range")
	if not (p.trigger.get_minimum_pledge() <= p.amount <= Pledge.current_algorithm()["max_contrib"]):
		raise InvalidArgumentError("amount is out of range")
	if p.incumb_challgr not in (-1, 0, 1):
		raise InvalidArgumentError("incumb_challgr is out of range")
	if p.filter_party == ActorParty.Independent:
		raise InvalidArgumentError("filter_party is out of range")
	if p.tip_to_campaign_owner < 0:
		raise InvalidArgumentError("tip_to_campaign_owner is out of range")
	if p.tip_to_campaign_owner > 0 and (not p.via_campaign.owner or not p.via_campaign.owner.de_recip_id):
		raise InvalidArgumentError("tip_to_campaign_owner cannot be non-zero")
	if (p.trigger.trigger_type.extra or {}).get("monovalent") and p.incumb_challgr != 0:
		# With a monovalent trigger, Actors only ever take outcome zero.
		# Therefore not all filters make sense. A pledge cannot be filtered
		# to incumbents who take action 1 or to the opponents of actors
		# who do not take action 0.
		raise InvalidArgumentError("monovalent triggers do not permit an incumbent/challenger filter")

	tcust = TriggerCustomization.objects.filter(owner=p.via_campaign.owner, trigger=p.trigger).first()
	if tcust and tcust.incumb_challgr and p.incumb_challgr != tcust.incumb_challgr:
		raise InvalidArgumentError("incumb_challgr is out of range (campaign customization)")
	if tcust and tcust.filter_party and p.filter_party != tcust.filter_party:
		raise InvalidArgumentError("filter_party is out of range (campaign customization)")

	return p

def save_and_authorize_contributorinfo(p, request):
	# Save the user's information to a ContributorInfo object, save the Pledge,
	# and run a credit card authorization to get a token that we can use to
	# make a charge later.

	# If the credit card authorization fails, roll back and don't save the Pledge
	# or the ContributorInfo.
	with transaction.atomic():

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
		# card has expired prior to using the DE token at a later time.)
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

		# If the user has other open pledges, update their profiles to the new
		# ContributorInfo instance --- i.e. update their contributor and payment
		# info.
		update_pledge_profiles(p)

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

def reuse_authorized_contributorinfo(p, request):
	# See if the user wants to re-use an existing ContributorInfo that
	# has a credit card token already in it that we can use.
	if not request.POST["copyFromPledge"]:
		return False

	else:
		# This is a returning user and we are re-using info from a previous pledge.
		# That pledge might be one that hasn't had its email address confirmed yet,
		# or if it has the user might not be logged in, but the user's session cookie
		# may grant the user access to it. Or if the user is logged in, it might be
		# a pledge tied to the account.
		prev_p = Pledge.objects.get(id=request.POST["copyFromPledge"])
		if not get_user_pledges(p.user, request).filter(id=prev_p.id).exists():
			raise InvalidArgumentError("copyFromPledge is set to a pledge ID that the user did not create or is no longer stored in their session.")
		p.profile = prev_p.profile
		p.save()
		return True

@json_response
def cancel_pledge(request):
	# Get the pledge. Check authorization.
	p = Pledge.objects.get(id=request.POST['pledge'])
	if get_user_pledges(request.user, request).filter(id=p.id).exists():
		try:
			p.delete()
		except Exception as e:
			return { "status": "error", "message": "Could not cancel pledge: " + str(e) }
		return { "status": "ok" }
	else:
		return { "status": "error", "message": "You don't own that pledge." }

def render_pledge_template(request, pledge, campaign, show_long_title=False, response_page=False):
	# Get the user's pledges, if any, on any trigger tied to this campaign.
	import django.template
	template = django.template.loader.get_template("contrib/contrib.html")
	
	ctx = {
		"response_page": response_page,
		"show_long_title": show_long_title,
		"pledge": pledge,
		"campaign": campaign,
		"execution": PledgeExecution.objects.filter(pledge=pledge).first(),
		"contribs": sorted(Contribution.objects.filter(pledge_execution__pledge=pledge).select_related("action", "recipient"), key=lambda c : (c.recipient_type.value, c.action.name_sort)),
		"share_url": request.build_absolute_uri(pledge.via_campaign.get_short_url()),
	}

	from itfsite.middleware import get_branding
	ctx.update(get_branding(request))
	
	return template.render(ctx)

@anonymous_view
def report(request):
	context = { }
	context.update(report_fetch_data(None, None))
	return render(request, "contrib/totals.html", context)

def report_fetch_data(trigger, via_campaign):
	pledge_slice_fields = { }
	pledgeexec_slice_fields = { }
	ca_slice_fields = { }

	if trigger:
		pledge_slice_fields["trigger"] = trigger
		try:
			te = trigger.execution
		except TriggerExecution.DoesNotExist:
			raise Http404("This trigger is not executed.")
		if te.pledge_count_with_contribs == 0:
			raise Http404("This trigger did not have any contributions.")
		if te.pledge_count < .75 * trigger.pledge_count:
			raise Http404("This trigger is still being executed.")
		pledgeexec_slice_fields["trigger_execution"] = te
		ca_slice_fields["pledge_execution__trigger_execution"] = te

	if via_campaign:
		pledge_slice_fields["via_campaign"] = via_campaign
		pledgeexec_slice_fields["pledge__via_campaign"] = via_campaign
		ca_slice_fields["pledge_execution__pledge__via_campaign"] = via_campaign

	# form response
	ret = { }

	# number of pledges & users making pledges
	pledges = Pledge.objects.filter(**pledge_slice_fields)
	ret["users_pledging"] = pledges.exclude(user=None).values("user").distinct().count()
	ret["users_pledging_twice"] = pledges.exclude(user=None).values("user").annotate(count=Count('id')).filter(count__gt=1).count()
	ret["pledges"] = pledges.count()
	ret["pledges_confirmed"] = pledges.exclude(user=None).count()
	from django.db.models import Sum
	ret["pledge_aggregate"] = pledges.aggregate(amount=Sum('amount'))["amount"]

	# number of executed pledges and users with executed pledges
	pledge_executions = PledgeExecution.objects.filter(problem=PledgeExecutionProblem.NoProblem, **pledgeexec_slice_fields)
	ret["users"] = pledge_executions.values("pledge__user").distinct().count()
	ret["num_triggers"] = pledge_executions.values("trigger_execution").distinct().count()
	if ret["num_triggers"] > 0:
		ret["first_contrib_date"] = pledge_executions.order_by('created').first().created
		ret["last_contrib_date"] = pledge_executions.order_by('created').last().created

	# aggregate count and amount of campaign contributions
	ret["total"] = dict(zip(["count", "total"], Contribution.aggregate(**ca_slice_fields)))
	if ret["total"]["count"] > 0:
		ret["total"]["average"] = ret["total"]["total"] / ret["total"]["count"]

	if trigger:
		# Aggregates by outcome. Return in the same order as Trigger.outcomes
		# (don't change that!).
		ret['outcomes'] = []
		outcome_totals = dict(Contribution.aggregate('desired_outcome', **ca_slice_fields))
		for outcome_index, outcome_info in enumerate(trigger.outcomes):
			outcome_total = outcome_totals.get((outcome_index,), (0, decimal.Decimal(0)))
			ret['outcomes'].append({
				"outcome": outcome_index,
				"label": outcome_info['label'],
				"total": outcome_total[1],
				"count": outcome_total[0],
			})

	# Aggregates by actor.
	from collections import defaultdict
	ret['actors'] = defaultdict(lambda : defaultdict( lambda : decimal.Decimal(0) ))
	for ((action_or_actor, recipient_type), (count, total)) in Contribution.aggregate('action' if trigger else "actor", 'recipient_type', **ca_slice_fields):
		actor = action_or_actor.actor if trigger else action_or_actor
		ret['actors'][actor.id]['actor'] = actor
		ret['actors'][actor.id][recipient_type.name] += total
		if trigger: ret['actors'][actor.id]['action'] = action_or_actor
	ret['actors'] = sorted(ret['actors'].values(), key = lambda x : (-(x['Incumbent'] - x['GeneralChallenger']), -x['Incumbent'], x['actor'].name_sort))

	# Aggregates by incumbent/chalenger.
	ret['by_recipient_type'] = [
		{
			"recipient_type": recipient_type.name,
			"count": count,
			"total": total,
		}
		for ((recipient_type,), (count, total))
		in Contribution.aggregate('recipient_type', **ca_slice_fields) ]

	# Aggregates by party. Have to do this in two steps - first
	# incumbents, then challengers, since the party is stored in
	# separate places.
	ret['by_party'] = defaultdict( lambda : [0, decimal.Decimal(0)] )
	for ((party,), (count, total)) in Contribution.aggregate('action__party', action__isnull=False, **ca_slice_fields):
		ret['by_party'][party][0] += count
		ret['by_party'][party][1] += total
	for ((party,), (count, total)) in Contribution.aggregate('recipient__party', action__isnull=True, **ca_slice_fields):
		ret['by_party'][party][0] += count
		ret['by_party'][party][1] += total
	ret['by_party'] = [ { "party": party, "count": count, "total": total } for (party, (count, total)) in ret['by_party'].items() ]
	ret['by_party'].sort(key = lambda item : item["total"], reverse=True)

	# report
	return ret
