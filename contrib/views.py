from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.dispatch import receiver
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponseForbidden

from email_confirm_la.signals import post_email_confirm

from twostream.decorators import anonymous_view, user_view_for

from contrib.models import Trigger, Pledge, PledgeStatus
from contrib.utils import json_response

@anonymous_view
def trigger(request, id, slug):
	# get the object
	trigger = get_object_or_404(Trigger, id=id)

	# redirect to canonical URL if slug does not match
	if trigger.slug != slug:
		return redirect(trigger.get_absolute_url())

	return render(request, "contrib/trigger.html", {
		"trigger": trigger,
		"alg": Pledge.current_algorithm(),
	})

@user_view_for(trigger)
def trigger_user_view(request, id, slug):
	trigger = get_object_or_404(Trigger, id=id)
	ret = { }
	if request.user.is_authenticated():
		ret["pledge_defaults"] = get_recent_pledge_defaults(request.user)

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
		ret["pledge_made"] = template.render(django.template.Context({
			"trigger": trigger,
			"pledge": p,
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
	return get_recent_pledge_defaults(user)

def get_recent_pledge_defaults(user):
	ret = { }
	pledge = Pledge.objects.filter(user=user).order_by('-created').first()
	if pledge:
		for field in ('amount', 'incumb_challgr', 'filter_party', 'filter_competitive',
			'contribNameFirst', 'contribNameLast', 'contribAddress', 'contribCity', 'contribState', 'contribZip',
			'contribOccupation', 'contribEmployer'):
			ret[field] = getattr(pledge, field, pledge.extra.get(field))
			if type(ret[field]).__name__ == "Decimal":
				ret[field] = float(ret[field])
	return ret

@require_http_methods(['POST'])
@json_response
@transaction.atomic
def submit(request):
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

	# string fields that have the same field name as the form element name
	for field in ('filter_party',):
		setattr(p, field, request.POST[field])

	# string fields that go straight into the extras dict.
	p.extra = {}
	for field in (
		'contribNameFirst', 'contribNameLast',
		'contribAddress', 'contribCity', 'contribState', 'contribZip',
		'contribOccupation', 'contribEmployer'):
		p.extra[field] = request.POST[field].strip()

	# Store the last four digits of the credit card number so we can
	# quickly locate a Pledge by CC number (approximately).
	p.cclastfour = request.POST['billingCCNum'][-4:]

	# Store a hashed version of the credit card information so we can
	# do a verification if the user wants to look up a Pledge by CC
	# info. Use Django's built-in password hashing functionality to
	# handle this.
	from django.contrib.auth.hashers import make_password
	cc_key = ','.join(request.POST[field].strip() for field in ('billingCCNum', 'billingCCExpMonth', 'billingCCExpYear', 'billingCCCVC'))
	cc_key = cc_key.replace(' ', '')
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
	if len(p.filter_party) == 0:
		raise Exception("filter_party is out of range")
	for c in p.filter_party:
		if c not in ('D', 'R', 'I'):
			raise Exception("filter_party is out of range")

	# Well, we'd submit this to Democracy Engine here, which would tell
	# us whether many of these fields are OK.

	# But until then, the best we can do is save.
	try:
		p.save()
	except Exception as e:
		# Re-wrap into something @json_response will catch.
		raise ValueError("Something went wrong: " + str(e))

	if p.user:
		# Update state contingent on the pledge being confirmed.
		p.on_confirmed()
	else:
		# The pledge needs to get confirmation of the user's email address,
		# which will lead to account creation.
		try:
			p.send_email_verification()
		except IOError:
			# If we can't synchronously send an email, just go on. We'll
			# try again asynchronously.
			pass

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
	if request.POST['desire'] == "cancel":
		p.make_cancelled()
	else:
		p.make_uncancelled()
	return { "status": "ok" }
