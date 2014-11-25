import decimal
import rtyaml

from django.conf import settings

def create_de_donation_basic_dict(pledge):
	# Creates basic info for a Democracy Engine API call for creating
	# a transaction (both authtest and auth+capture calls).
	return {
		"donor_first_name": pledge.extra['contribNameFirst'],
		"donor_last_name": pledge.extra['contribNameLast'],
		"donor_address1": pledge.extra['contribAddress'],
		"donor_city": pledge.extra['contribCity'],
		"donor_state": pledge.extra['contribState'],
		"donor_zip": pledge.extra['contribZip'],
		"donor_email": pledge.get_email(),

		"compliance_employer": pledge.extra['contribEmployer'],
		"compliance_occupation": pledge.extra['contribOccupation'],

		"email_opt_in": False,
		"is_corporate_contribution": False,

		# use contributor info as billing info in the hopes that it might
		# reduce DE's merchant fees, and maybe we'll get back CC verification
		# info that might help us with data quality checks in the future?
		"cc_first_name": pledge.extra['contribNameFirst'],
		"cc_last_name": pledge.extra['contribNameLast'],
		"cc_zip": pledge.extra['contribZip'],
	}

def run_authorization_test(pledge, ccnum, ccexpmonth, ccexpyear, cccvc, request):
	# Runs an authorization test at the time the user is making a pledge,
	# which tests the card info and also gets a credit card token that
	# can be used later to make a real charge without other billing
	# details.

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
		"aux_data": rtyaml.dump({ # DE will gives this back to us encoded as YAML, but the dict encoding is ruby-ish so to be sure we can parse it, we'll encode it first
			"trigger": pledge.trigger.id,
			"pledge": pledge.id,

			# Add information from the HTTP request in case we need to
			# block IPs or something.
			"httprequest": { k: request.META.get(k) for k in ('REMOTE_ADDR', 'REQUEST_URI', 'HTTP_USER_AGENT') },
			})
		})

	# Perform the authorization test and return the transaction record.
	return DemocracyEngineAPI.create_donation(de_don_req)

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
			r = action.actor.get_recipient(incumbent=True)

		elif action.party == ActorParty.Independent:
			# Cannot give to the opponent of an Independent per FEC rules.
			continue

		else:
			# The incumbent did something other than what the user wanted, so the
			# challenger of the opposite party is the recipient.

			# Filter if the pledge is for incumbents only.
			if pledge.incumb_challgr == 1:
				continue

			# Party filtering is based on that opposite party.
			party = action.party.opposite()

			# Get the Recipient object.
			r = action.actor.get_recipient(challenger_party=party)

		# Filter by party.

		if pledge.filter_party is not None and party != pledge.filter_party:
			continue

		# TODO: Competitive races? Assuming all are competitive now so
		# nothing to filter.

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

def create_pledge_donation(pledge, recip_contribs, fees):
	# Pledge execution --- make a credit card charge and return
	# the DE transaction record.

	line_items = []

	# Create the line item for fees.
	line_items.append({
		"recipient_id": settings.DE_API['fees-recipient-id'],
		"amount": "$%0.2f" % fees,
		})

	# Create the line items for campaign recipients.
	for recipient, action, amount in recip_contribs:
		line_items.append({
			"recipient_id": settings.DE_API['testing-recipient-id'], # recipient.de_id
			"amount": "$%0.2f" % amount,
			})

	# Prepare the donation record for authorization & capture.
	de_don_req = create_de_donation_basic_dict(pledge)
	de_don_req.update({
		# billing info
		"token": pledge.extra['de_cc_token'],

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
	
	# Create the 'donation', which creates a transaction and performs cc authorization.
	return DemocracyEngineAPI.create_donation(de_don_req)

def void_pledge_transaction(de_txn_guid):
	# This raises a 404 exception if the transaction info is not
	# yet available.
	txn = DemocracyEngineAPI.get_transaction(de_txn_guid)

	if txn['status'] == "voided":
		# We are good
		return

	# Attempt void.
	try:
		DemocracyEngineAPI.void_transaction(de_txn_guid)
	except:
		import sys, json
		print(json.dumps(txn, indent=2), file=sys.stderr)
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
				if len(exc) > 0 and exc[0][0] == "base":
					# Not sure what 'base' means, but we get things like
					# "Card number is not a valid credit card number".
					raise HumanReadableValidationError(exc[0][1])
			except HumanReadableValidationError:
				raise # pass through/up
			except:
				pass # fall through to next
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

	def create_recipient(self, info):
		return self(
			method="recipients",
			post_data=
				{ "recipient":
					{
						"remote_recipient_id": info["id"],
						"name": info["committee_name"],
						"registered_id": info["committee_id"],
						"recipient_type": "federal_candidate",
						#"contact": { "first_name", "last_name", "phone", "address1", "city", "state", "zip" },
						"user": {
							"first_name": "Generic",
							"last_name": "User",
							"login": "c%d" % info["id"],
							"initial_password": info["user_password"],
							"email": "de.user@civicresponsibilityllc.com"
						},
						"recipient_tags": {
							"party": info["party"], # e.g. "Democrat"
							"state": info["state"], # USPS
							"office": info["office"], # senator, representative
							"district": info["district"], # integer
							"cycle": info["cycle"] # year, integer
						}
					}
				})

	def transactions(self, live_request=False):
		return self(method="transactions", live_request=live_request)

	def get_transaction(self, id, live_request=False):
		return self(method="transaction", argument=('transaction_id', id), live_request=live_request)

	def void_transaction(self, id, live_request=False):
		return self(method="transaction_void", argument=('transaction_id', id), http_method="put", live_request=live_request)

	def create_donation(self, info):
		return self(
			method="donation_process",
			post_data=
				{ "donation": info },
			)

# Replace with a singleton instance.
DemocracyEngineAPI = DemocracyEngineAPI()

