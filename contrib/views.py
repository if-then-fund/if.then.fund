from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.dispatch import receiver
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.conf import settings

from email_confirm_la.signals import post_email_confirm

from twostream.decorators import anonymous_view, user_view_for

from contrib.models import Trigger, TriggerExecution, Pledge, PledgeStatus, PledgeExecution, Contribution, ActorParty, ContributionAggregate
from contrib.utils import json_response
from contrib.bizlogic import run_authorization_test, HumanReadableValidationError

import copy
import rtyaml

@anonymous_view
def trigger(request, id, slug):
	# get the object
	trigger = get_object_or_404(Trigger, id=id)

	# redirect to canonical URL if slug does not match
	if trigger.slug != slug:
		return redirect(trigger.get_absolute_url())

	outcomes = None
	actions = None
	avg_pledge = None
	avg_contrib = None
	num_contribs = None
	num_recips = None
	by_incumb_chlngr = []

	try:
		te = trigger.execution
	except TriggerExecution.DoesNotExist:
		te = None

	if te and te.pledge_count_with_contribs > 0:
		# Get the contribution aggregates by outcome and sort by total amount of contributions.
		outcomes = copy.deepcopy(trigger.outcomes)
		for i in range(len(outcomes)):
			outcomes[i]['index'] = i
			outcomes[i]['contribs'] = 0
		for rec in ContributionAggregate.objects.filter(trigger_execution=te).values('outcome', 'total'):
			outcomes[rec['outcome']]['contribs'] = rec['total']
		outcomes.sort(key = lambda x : x['contribs'], reverse=True)

		# Actions/Actors
		actions = list(te.actions.all().select_related('actor'))
		actions.sort(key = lambda a : (-(a.total_contributions_for - a.total_contributions_against), a.actor.name_sort))
		num_recips = 0
		for a in actions:
			if a.total_contributions_for > 0: num_recips += 1
			if a.total_contributions_against > 0: num_recips += 1

		# Incumbent/challengers.
		by_incumb_chlngr = [["Incumbents", 0, "text-success"], ["Opponents", 0, "text-danger"]]
		for a in actions:
			by_incumb_chlngr[0][1] += a.total_contributions_for
			by_incumb_chlngr[1][1] += a.total_contributions_against

		# Compute other summary stats.
		num_contribs = te.num_contributions
		avg_pledge = te.total_contributions / te.pledge_count_with_contribs
		avg_contrib = te.total_contributions / num_contribs


	return render(request, "contrib/trigger.html", {
		"trigger": trigger,
		"execution": te,
		"outcomes": outcomes,
		"alg": Pledge.current_algorithm(),
		"actions": actions,
		"by_incumb_chlngr": by_incumb_chlngr,
		"avg_pledge": avg_pledge,
		"num_contribs": num_contribs,
		"num_recips": num_recips,
		"avg_contrib": avg_contrib,
	})

@user_view_for(trigger)
def trigger_user_view(request, id, slug):
	trigger = get_object_or_404(Trigger, id=id)
	ret = { }

	# Most recent pledge info so we can fill in defaults on the user's next pledge.
	ret["pledge_defaults"] = get_recent_pledge_defaults(request.user, request)

	p = None
	if request.user.is_authenticated():
		p = Pledge.objects.filter(trigger=trigger, user=request.user).first()
	elif request.session.get('anon_pledge_created'):
		p = Pledge.objects.filter(trigger=trigger,
			id__in=request.session.get('anon_pledge_created')).first()

	if p:
		# The user already made a pledge on this.
		import django.template
		template = django.template.loader.get_template("contrib/contrib.html")
		pe = PledgeExecution.objects.filter(pledge=p).first()
		contribs = sorted(Contribution.objects.filter(pledge_execution=pe).select_related("action"), key=lambda c : c.action.name_sort)
		ret["pledge_made"] = template.render(django.template.Context({
			"trigger": trigger,
			"pledge": p,
			"execution": pe,
			"contribs": contribs,
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
	from itfsite.accounts import User, try_login
	user = try_login(request)
	if not isinstance(user, User):
		return { "status": str(user) }

	# get recent data
	return get_recent_pledge_defaults(user, request)

def get_recent_pledge_defaults(user, request):
	ret = { }

	if request.user.is_authenticated():
		pledge = Pledge.objects.filter(user=user).order_by('-created').first()
		if not pledge: return ret
	elif request.session.get('anon_pledge_created'):
		most_recent = request.session.get('anon_pledge_created')[-1]
		try:
			pledge = Pledge.objects.get(id=most_recent)
		except Pledge.DoesNotExist:
			return ret
	else:
		return ret

	for field in ('email', 'amount', 'incumb_challgr', 'filter_party', 'filter_competitive',
		'contribNameFirst', 'contribNameLast', 'contribAddress', 'contribCity', 'contribState', 'contribZip',
		'contribOccupation', 'contribEmployer'):
		ret[field] = getattr(pledge, field, pledge.extra.get(field))
		if type(ret[field]).__name__ == "Decimal":
			ret[field] = float(ret[field])
		elif isinstance(ret[field], ActorParty):
			ret[field] = str(ret[field])

	return ret

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

@transaction.atomic
def create_pledge(request):
	p = Pledge()

	# trigger
	p.trigger = Trigger.objects.get(id=request.POST['trigger'])

	# Set user from logged in state.
	if request.user.is_authenticated():
		# This is an authentiated user.
		p.user = request.user
		exists_filters = { 'user': p.user }

	# Anonymous user is submitting a pledge with an email address & password.
	elif request.POST.get("hasPassword") == "1":
		from itfsite.accounts import User, try_login
		user = try_login(request)
		if isinstance(user, User):
			# Login succeeded.
			p.user = user
			exists_filters = { 'user': p.user }
		else:
			# Login failed. We did client-side validation so this should
			# not occur. Treat as if the user didn't provide a password.
			pass

	# Anonymous user and/or authentication failed.
	# Will do email verification below.
	if not p.user:
		p.email = request.POST.get('email').strip()
		from itfsite.accounts import validate_email, ValidateEmailResult
		if validate_email(p.email, simple=True) != ValidateEmailResult.Valid:
			raise Exception("email is out of range")
		exists_filters = { 'email': p.email }

	# If the user has already made this pledge, it is probably a
	# synchronization problem. Just redirect to that pledge.
	p_exist = Pledge.objects.filter(trigger=p.trigger, **exists_filters).first()
	if p_exist is not None:
		return { "status": "ok" }

	# Field values & validation.

	# integer fields that have the same field name as form element name
	for field in ('algorithm', 'desired_outcome', 'filter_competitive'):
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

	# string fields that go straight into the extras dict.
	p.extra = {}
	for field in (
		'contribNameFirst', 'contribNameLast',
		'contribAddress', 'contribCity', 'contribState', 'contribZip',
		'contribOccupation', 'contribEmployer'):
		p.extra[field] = request.POST[field].strip()

	# normalize the filter_party field
	if request.POST['filter_party'] in ('DR', 'RD'):
		p.filter_party = None # no filter
	elif request.POST['filter_party'] == 'D':
		p.filter_party = ActorParty.Democratic
	elif request.POST['filter_party'] == 'R':
		p.filter_party = ActorParty.Republican

	# Store the last four digits of the credit card number so we can
	# quickly locate a Pledge by CC number (approximately).
	p.cclastfour = request.POST['billingCCNum'][-4:]
	ccnum = request.POST['billingCCNum'].replace(" ", "").strip() # Stripe's javascript inserts spaces
	ccexpmonth = int(request.POST['billingCCExpMonth'])
	ccexpyear = int(request.POST['billingCCExpYear'])
	cccvc = request.POST['billingCCCVC'].strip()

	# Store a hashed version of the credit card information so we can
	# do a verification if the user wants to look up a Pledge by CC
	# info. Use Django's built-in password hashing functionality to
	# handle this.
	from django.contrib.auth.hashers import make_password
	cc_key = ','.join((ccnum, str(ccexpmonth), str(ccexpyear)))
	p.extra['billingInfoHashed'] = make_password(cc_key)
			
	# Validation. Some are checked client side, so errors are internal
	# error conditions and not validation problems to show the user.
	if p.algorithm != Pledge.current_algorithm()["id"]:
		raise Exception("algorithm is out of range")
	if not (0 <= p.desired_outcome < len(p.trigger.outcomes)):
		raise Exception("desired_outcome is out of range")
	if not (Pledge.current_algorithm()["min_contrib"] <= p.amount <= Pledge.current_algorithm()["max_contrib"]):
		raise Exception("amount is out of range")
	if p.incumb_challgr not in (-1, 0, 1):
		raise Exception("incumb_challgr is out of range")
	if p.filter_party == ActorParty.Independent:
		raise Exception("filter_party is out of range")

	# Save so we get a pledge ID so we can store that in the transaction test.
	try:
		p.save()
	except Exception as e:
		# Re-wrap into something @json_response will catch.
		raise ValueError("Something went wrong: " + str(e))

	# Perform an authorization test on the credit card.
	#   a) This tests that the billing info is valid.
	#   b) We get a token that we can use on future transactions so that we
	#      do not need to collect the credit card info again.
	# This may raise all sorts of exceptions, which will cause the database
	# transaction to roll back. A HumanReadableValidationError will be caught
	# in the calling function and shown to the user. Other exceptions will
	# just generate generic unhandled error messages.
	de_txn = run_authorization_test(p, ccnum, ccexpmonth, ccexpyear, cccvc, request)

	# Note that any exception after this point is okay because the authorization
	# will expire on its own anyway.

	# Store the transaction authorization, which contains the credit card token,
	# into the pledge.
	p.extra["authorization"] = de_txn
	p.extra["de_cc_token"] = de_txn['token']
	p.save()

	# Increment the trigger's pledge_count and total_pledged fields (atomically).
	from django.db import models
	p.trigger.pledge_count = models.F('pledge_count') + 1
	p.trigger.total_pledged = models.F('total_pledged') + p.amount
	p.trigger.save(update_fields=['pledge_count', 'total_pledged'])

	if not p.user:
		# The pledge needs to get confirmation of the user's email address,
		# which will lead to account creation.

		def mailer(context):
			from htmlemailer import send_mail
			send_mail(
				"contrib/mail/confirm_email",
				settings.DEFAULT_FROM_EMAIL,
				[context['email']],
				{
					"confirmation_url": context['confirmation_url'],
					"pledge": p,
				})

		from email_confirm_la.models import EmailConfirmation
		ec = EmailConfirmation.objects.set_email_for_object(
			email=p.email,
			content_object=p,
			mailer=mailer,
		)

		# And in order for the user to be able to view the pledge on the
		# next page, prior to email confirmation, we'll need to set a token
		# to grant permission. Only hold up to 20 values.
		request.session['anon_pledge_created'] = \
			request.session.get('anon_pledge_created', [])[-20:] \
			+ [p.id]

	# If the user had good authentication but wasn't logged in yet, log them
	# in now. This messes up the CSRF token but the client should redirect to
	# a new page anyway.
	if p.user and p.user != request.user:
		from django.contrib.auth import login
		login(request, p.user)

	# Client will reload the page.
	return { "status": "ok" }

# A user confirms an email address on an anonymous pledge.
@receiver(post_email_confirm)
def post_email_confirm_callback(sender, confirmation, request=None, **kwargs):
	# The user making the request confirms that he owns an email address
	# tied to a pledge.

	pledge = confirmation.content_object
	email = confirmation.email

	# Get or create the user account.

	from itfsite.accounts import User
	user = User.get_or_create(email)

	# Confirm the pledge. This signal may be called more than once, and
	# confirm_email is okay with that. It returns True just on the first
	# time (when the pledge is actually confirmed).
	if pledge.confirm_email(user):
		messages.add_message(request, messages.SUCCESS, 'Your contribution for %s has been confirmed.'
			% pledge.trigger.title)

	# The user may be new, so take them to a welcome page.
	# pledge.user may not be set because confirm_email uses a clone for locking.
	from itfsite.accounts import first_time_confirmed_user
	return first_time_confirmed_user(request, user, pledge.trigger.get_absolute_url())

@json_response
def cancel_pledge(request):
	# Get the pledge. Check authorization.
	p = Pledge.objects.get(id=request.POST['pledge'])
	if not (p.user == request.user or p.id in request.session.get('anon_pledge_created', [])):
		raise Exception()
	p.delete()
	return { "status": "ok" }
