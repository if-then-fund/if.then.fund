import decimal
import rtyaml

from django.conf import settings

def create_de_donation_basic_dict(pledge):
	# Creates basic info for a Democracy Engine API call for creating
	# a transaction (both authtest and auth+capture calls).
	return {
		"donor_first_name": pledge.extra['contributor']['contribNameFirst'],
		"donor_last_name": pledge.extra['contributor']['contribNameLast'],
		"donor_address1": pledge.extra['contributor']['contribAddress'],
		"donor_city": pledge.extra['contributor']['contribCity'],
		"donor_state": pledge.extra['contributor']['contribState'],
		"donor_zip": pledge.extra['contributor']['contribZip'],
		"donor_email": pledge.get_email(),

		"compliance_employer": pledge.extra['contributor']['contribEmployer'],
		"compliance_occupation": pledge.extra['contributor']['contribOccupation'],

		"email_opt_in": False,
		"is_corporate_contribution": False,

		# use contributor info as billing info in the hopes that it might
		# reduce DE's merchant fees, and maybe we'll get back CC verification
		# info that might help us with data quality checks in the future?
		"cc_first_name": pledge.extra['contributor']['contribNameFirst'],
		"cc_last_name": pledge.extra['contributor']['contribNameLast'],
		"cc_zip": pledge.extra['contributor']['contribZip'],
	}

def run_authorization_test(pledge, ccnum, ccexpmonth, ccexpyear, cccvc, aux_data):
	# Runs an authorization test at the time the user is making a pledge,
	# which tests the card info and also gets a credit card token that
	# can be used later to make a real charge without other billing
	# details.

	# Store the last four digits of the credit card number so we can
	# quickly locate a Pledge by CC number (approximately).
	pledge.cclastfour = ccnum[-4:]

	# Store a hashed version of the credit card number so we can
	# do a verification if the user wants to look up a Pledge by CC
	# info. Use Django's built-in password hashing functionality to
	# handle this.
	#
	# Also store the expiration date so that we can know that a
	# card has expired prior to using the DE token.
	from django.contrib.auth.hashers import make_password
	pledge.extra['billing'] = {
		'cc_num_hashed': make_password(ccnum),
		'cc_exp_month': ccexpmonth,
		'cc_exp_year': ccexpyear,
	}

	# Logging.
	aux_data.update({
		"trigger": pledge.trigger.id,
		"pledge": pledge.id,
	})

	# Basic contributor details.
	de_don_req = create_de_donation_basic_dict(pledge)

	# Add billing details.
	de_don_req.update({
		"authtest_request":  True,
		"token_request": True,

		# billing details
		"cc_number": ccnum,
		"cc_month": ccexpmonth,
		"cc_year": ccexpyear,
		"cc_verification_value": cccvc,

		# no line items are necessary for an authorization test
		"line_items": [],

		# tracking info, which for an auth test stays private?
		"source_code": "itfsite pledge auth", 
		"ref_code": "", 
		"aux_data": rtyaml.dump(aux_data), # DE will gives this back to us encoded as YAML, but the dict encoding is ruby-ish so to be sure we can parse it, we'll encode it first
		})

	# Perform the authorization test and return the transaction record.
	#
	#   a) This tests that the billing info is valid.
	#   b) We get a token that we can use on future transactions so that we
	#      do not need to collect the credit card info again.
	de_txn = DemocracyEngineAPI.create_donation(de_don_req)

	# Store the transaction authorization, which contains the credit card token,
	# into the pledge.
	pledge.extra['billing']['authorization'] = de_txn
	pledge.extra['billing']['de_cc_token'] = de_txn['token']

def get_pledge_recipients(trigger, pledge):
	# For pledge execution, figure out how to split the contribution
	# across actual recipients.

	from contrib.models import ActorParty, Recipient

	recipients = []

	for action in trigger.execution.actions.all().select_related('actor'):
		# Skip actions with null outcomes, meaning the Actor didn't really
		# take an action and so no contribution for or against is made.

		if action.outcome is None:
			continue

		# Get a recipient object.

		if action.outcome == pledge.desired_outcome:
			# The incumbent did what the user wanted, so the incumbent is the recipient.

			# Filter if the pledge is for challengers only.
			if pledge.incumb_challgr == -1:
				continue

			# Party filtering is based on the party of the incumbent at the time of the action.
			party = action.party

			# Get the Recipient object.
			try:
				r = Recipient.objects.get(actor=action.actor)
			except Recipient.DoesNotExist:
				raise Recipient.DoesNotExist("There is no recipient for " + str(action.actor))

		else:
			# The incumbent did something other than what the user wanted, so the
			# challenger of the opposite party is the recipient.

			# Filter if the pledge is for incumbents only.
			if pledge.incumb_challgr == 1:
				continue

			if action.challenger is None:
				# We don't have a challenger Recipient associated. There should always
				# be a challenger. If there is not, create a Recipient and set its
				# active field to false.
				raise ValueError("Action has no challenger: %s" % action)

			# Get the Recipient object.
			r = action.challenger

			# Party filtering is based on the party on the recipient object.
			party = r.party

		# The Recipient may not be currently taking contributions.
		# Silently skip.

		if not r.active:
			continue

		# Filter by party.

		if pledge.filter_party is not None and party != pledge.filter_party:
			continue

		# If we got here, then r is an acceptable recipient.
		recipients.append( (r, action) )

	return recipients

def compute_charge(pledge, recipients):
	# Return a tuple of:
	#  * a list of (recipient, action, amount) line items
	#  * the fees line-item amount
	#  * the total charge

	from contrib.models import Pledge

	# What's the total amount of contributions after fess? The inputs
	# here are all decimal.Decimal instances, so we are doing exact
	# decimal math up to the default precision.
	fees_fixed = Pledge.current_algorithm()['fees_fixed']
	fees_percent = Pledge.current_algorithm()['fees_percent']
	max_contrib = (pledge.amount - fees_fixed) / (1 + fees_percent)

	# If we divide that evenly among the recipients, what is the ideal contribution?
	# Round it down to the nearest cent because we can only make whole-cent contributions
	# and contributions must be equal and the total must not exceed the original amount.
	recip_contrib = max_contrib / len(recipients)
	recip_contrib = recip_contrib.quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_DOWN)
	if recip_contrib < decimal.Decimal('0.01'):
		# The pledge amount was so small that we can't divide it.
		# This should never happen because our minimum pledge is
		# more than one cent for each potential recipient for a
		# Trigger.
		raise ValueError("Pledge amount is too small to distribute.")

	# Make a list of line items.
	recip_contribs = [(recipient, action, recip_contrib) for (recipient, action) in recipients]

	# Multiply out to create the total before fees.
	contrib_total = len(recipients) * recip_contrib

	# Compute the total with fees. Rather than computing the fees first
	# and hoping the total is under the original pledge amount (the
	# maximum), compute the total, round, clip at the ceiling, and then
	# work backwards to the fees.
	total_charge = contrib_total * (1 + fees_percent) + fees_fixed

	# Round to the nearest cent, then ensure we haven't exeeded maximum.
	total_charge = total_charge.quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_HALF_EVEN)
	if total_charge > pledge.amount:
		total_charge = pledge.amount

	# Fees are the difference between the total and the contributions.
	fees = total_charge - contrib_total

	# Return!
	return (recip_contribs, fees, total_charge)

def create_pledge_donation(pledge, recipients):
	# Pledge execution --- make a credit card charge and return
	# the DE donation record and other details.

	# Compute the amount to charge the user. We can only make whole-penny
	# contributions, so the exact amount of the charge may be less than
	# what the user pledged. recip_contribs is the line item amounts for
	# each recipient as a tuple of (recipient, action, amount).
	recip_contribs, fees, total_charge = compute_charge(pledge, recipients)

	# Prepare line items for the API.
	line_items = []

	def fmt_decimal(value):
		# Ensure decimal value has no more than two decimal places.
		try:
			sign, digits, exp = value.quantize(decimal.Decimal('0.01')).as_tuple()
		except decimal.InvalidOperation:
			raise ValueError("Rounding issue with %s." % value)
		if sign != 0:
			raise ValueError("Rounding issue with %s (sign=%d)." % (value, sign))
		if exp != -2:
			raise ValueError("Rounding issue with %s (^%d)." % (value, exp))

		# Format with dollar sign, decimal point, and at least a leading zero.
		digits = [str(d) for d in digits]
		while len(digits) < 3: digits.insert(0, '0')
		return "$%s.%s" % (''.join(digits[:-2]), ''.join(digits[-2:]))

	# Create the line item for fees.
	line_items.append({
		"recipient_id": settings.DE_API['fees-recipient-id'],
		"amount": fmt_decimal(fees),
		})

	# Create the line items for campaign recipients.
	for recipient, action, amount in recip_contribs:
		line_items.append({
			"recipient_id": recipient.de_id,
			"amount": fmt_decimal(amount),
			})

	# Prepare the donation record for authorization & capture.
	de_don_req = create_de_donation_basic_dict(pledge)
	de_don_req.update({
		# billing info
		"token": pledge.extra['billing']['de_cc_token'],

		# line items
		"line_items": line_items,

		# reported to the recipient
		"source_code": "itfsite", 
		"ref_code": pledge.trigger.get_short_url(), 

		# tracking info for internal use
		"aux_data": rtyaml.dump({ # DE will gives this back to us encoded as YAML, but the dict encoding is ruby-ish so to be sure we can parse it, we'll encode it first
			"trigger": pledge.trigger.id,
			"pledge": pledge.id,
			})
		})

	# Sanity check the total.
	if sum(decimal.Decimal(li['amount'].replace("$", "")) for li in de_don_req['line_items']) \
		!= total_charge:
		raise ValueError("Sum of line items does not match total charge.")
	
	# Create the 'donation', which creates a transaction and performs cc authorization.
	don = DemocracyEngineAPI.create_donation(de_don_req)

	# Return.
	return (recip_contribs, fees, total_charge, don)

def void_pledge_transaction(txn_guid, allow_credit=False):
	# This raises a 404 exception if the transaction info is not
	# yet available.
	txn = DemocracyEngineAPI.get_transaction(txn_guid)

	if txn['status'] in ("voided", "credited"):
		# We are good.
		return

	if txn['status'] not in ("authorized", "captured"):
		raise ValueError("Not sure what to do with a transaction with status %s." % txn['status'])

	# Attempt void.
	try:
		DemocracyEngineAPI.void_transaction(txn_guid)
	except HumanReadableValidationError as e:
		# Void failed. Try credit.
		try:
			if not allow_credit:
				raise
			print(e) # Can we detect when we shouldn't attempt a credit.
			DemocracyEngineAPI.credit_transaction(txn_guid)
		except:
			import sys, json
			print(json.dumps(txn, indent=2), file=sys.stderr)
			print("Tried first:", e, file=sys.stderr)
			raise

class HumanReadableValidationError(Exception):
	pass

class DemocracyEngineAPI(object):
	de_meta_info = None

	def __call__(self, method, post_data=None, argument=None, live_request=False, http_method=None):
		import json
		import requests
		from requests.auth import HTTPDigestAuth

		# Cache meta info. If method is None, don't infinite recurse.
		if (self.de_meta_info == None) and (method is not None):
			self.de_meta_info = self(None, None, live_request=live_request)

		if method is None:
			# This is an internal call to get the meta subscriber info.
			url = settings.DE_API['api_baseurl'] + ('/subscribers/%s.json' % settings.DE_API['account_number'])
		elif method == "META":
			# This is a real call to get the meta info, which is always cached.
			return self.de_meta_info
		else:
			# Get the correct URL from the meta info, and do argument substitution
			# if necessary.
			url = self.de_meta_info[method + "_uri"]
			if argument:
				import urllib.parse
				url = url.replace(":"+argument[0], urllib.parse.quote(argument[1]))

		# GET or POST?
		if post_data == None:
			payload = None
			headers = None
			urlopen = requests.get
		else:
			payload = json.dumps(post_data)
			headers = {'content-type': 'application/json'}
			urlopen = requests.post

		# Override HTTP method.
		if http_method:
			urlopen = getattr(requests, http_method)

		# Log requests. Definitely don't do this in production since we'll
		# have sensitive data here!
		if False and settings.DEBUG:
			print(urlopen.__name__.upper(), url)
			if payload:
				print(json.dumps(json.loads(payload), indent=True))
			print()

		# issue request
		r = urlopen(
			url,
			auth=HTTPDigestAuth(settings.DE_API['username'], settings.DE_API['password']),
			data=payload,
			headers=headers,
			timeout=30 if not live_request else 20,
			verify=True, # check SSL cert (is default, actually)
			)

		# raises exception on anything but 200 OK
		try:
			r.raise_for_status()
		except:
			try:
				exc = r.json()
				if isinstance(exc, list) and len(exc) > 0 and exc[0][0] == "base":
					# Not sure what 'base' means, but we get things like
					# "Card number is not a valid credit card number".
					raise HumanReadableValidationError(exc[0][1])
				if isinstance(exc, dict) and isinstance(exc.get('base'), list):
					# Not sure what 'base' means, but we get things like
					# "Card number is not a valid credit card number".
					raise HumanReadableValidationError(exc.get('base')[0])
			except HumanReadableValidationError:
				raise # pass through/up
			except:
				pass # fall through to next

			import sys
			print(r.content, file=sys.stderr)
			raise IOError("DemocrayEngine API failed: %d %s" % (r.status_code, url))

		# The PUT requests have no response. A 200 response is success.
		if http_method == "put":
			return None

		# all other responses are JSON
		return r.json()

	def recipients(self, live_request=False):
		return self(method="recipients", live_request=live_request)

	def get_recipient(self, id, live_request=False, http_method=None):
		return self(method="recipient", argument=('recipient_id', id), http_method=http_method, live_request=live_request)

	def transactions(self, live_request=False):
		return self(method="transactions", live_request=live_request)

	def get_transaction(self, id, live_request=False):
		return self(method="transaction", argument=('transaction_id', id), live_request=live_request)

	def void_transaction(self, id):
		return self(method="transaction_void", argument=('transaction_id', id), http_method="put")

	def credit_transaction(self, id):
		return self(method="transaction_credit", argument=('transaction_id', id), http_method="put")

	def create_donation(self, info):
		return self(
			method="donation_process",
			post_data=
				{ "donation": info },
			)

# Replace with a singleton instance.
DemocracyEngineAPI = DemocracyEngineAPI()

class DummyDemocracyEngineAPI(object):
	"""A stand-in for the DE API for unit tests."""

	issued_tokens = set()

	def create_donation(self, info):
		if info.get('token_request'):
			import random, hashlib
			token = hashlib.md5(str(random.random()).encode('ascii')).hexdigest()
			self.issued_tokens.add(token)
			return {
				"dummy_response": True,
				"token": token,
			}
		else:
			if info['token'] not in self.issued_tokens:
				raise Exception("Charge on an invalid token.")
			return {
				"dummy_response": True,
			}
