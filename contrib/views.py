from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db import transaction

from twostream.decorators import anonymous_view

from contrib.models import Trigger, Pledge
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

@require_http_methods(['POST'])
@json_response
@transaction.atomic
def submit(request):
	p = Pledge()

	# trigger
	p.trigger = Trigger.objects.get(id=request.POST['trigger'])

	# user
	if request.user.is_authenticated():
		# This is an authentiated user.
		p.user = request.user
		exists_filters = { 'user': p.user }
	else:
		# Anonymous user is submitting a pledge with an email address.
		# Will do email verification below.
		p.email = request.POST.get('email').strip()
		from itfsite.accounts import validate_email, ValidateEmailResult
		if validate_email(p.email, simple=True) != ValidateEmailResult.Valid:
			raise Exception("email is out of range")
		exists_filters = { 'email': p.email }

	# If the user has already made this pledge, it is probably a
	# synchronization problem. Just redirect to that pledge.
	p_exist = Pledge.objects.filter(trigger=p.trigger, **exists_filters).first()
	if p_exist is not None:
		return { "status": "ok", "redirect": p_exist.get_absolute_url() }

	# integer fields that have the same field name as form element name
	for field in ('algorithm', 'desired_outcome'):
		try:
			setattr(p, field, int(request.POST[field]))
		except ValueError:
			raise Exception("%s is out of range" % field)

	# float fields that have the same field name as form element name
	for field in ('contrib_amount', 'total_amount', 'incumb_challgr'):
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
		'billingName', 
		'billingCCNum', 'billingCCExp', 'billingCCCVC', 
		'billingAddress', 'billingCity', 'billingState', 'billingZip',
		'contribNameFirst', 'contribNameLast',
		'contribAddress', 'contribCity', 'contribState', 'contribZip',
		'contribOccupation', 'contribEmployer'):
		p.extra[field] = request.POST[field]

	# Validation. Some are checked client side, so errors are internal
	# error conditions and not validation problems to show the user.
	if p.algorithm != Pledge.current_algorithm()["id"]:
		raise Exception("algorithm is out of range")
	if not (0 <= p.desired_outcome < len(p.trigger.outcomes)):
		raise Exception("desired_outcome is out of range")
	if not (Pledge.current_algorithm()["min_contrib"] <= p.contrib_amount <= Pledge.current_algorithm()["max_contrib"]):
		raise Exception("contrib_amount is out of range")
	if abs(p.contrib_amount*(1+Pledge.current_algorithm()["fees"]/100) - p.total_amount) > 1:
		# Checking that the total amount includes the right amount of fees, within one
		# cent in case Javascript does rounding differently than Python.
		raise Exception("total_amount is incorrect")
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

	if not request.user.is_authenticated():
		# The pledge needs to get confirmation of the user's email address,
		# which will lead to account creation.
		try:
			p.send_email_verification()
		except IOError:
			# If we can't synchronously send an email, just go on. We'll
			# try again asynchronously.
			pass

		# And in order for the user to be able to view the pledge on the
		# next page, we'll need to set a token to grant permission.
		request.session.setdefault('anon_pledge_created', []).add( p.id )

	# Tell the client to redirect to the page where the user can see the pledge.
	return { "status": "ok", "redirect": p.get_absolute_url() }
