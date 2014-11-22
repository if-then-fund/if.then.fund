import decimal
import rtyaml

from django.conf import settings

def create_de_txn_basic_dict(pledge):
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
	}

def run_authorization_test(pledge, ccnum, ccexpmonth, ccexpyear, cccvc, request):
	# Runs an authorization test at the time the user is making a pledge,
	# which tests the card info and also gets a credit card token that
	# can be used later to make a real charge without other billing
	# details.

	from contrib.utils import DemocracyEngineAPI

	# Basic contributor details.
	de_txn_req = create_de_txn_basic_dict(pledge)

	# Add billing details.
	de_txn_req.update({
		"authtest_request":  True,
		"token_request": True,

		# billing details
		"cc_number": ccnum,
		"cc_month": ccexpmonth,
		"cc_year": ccexpyear,
		"cc_verification_value": cccvc,

		# use contributor info as billing info in the hopes that it might
		# reduce DE's merchant fees, and maybe we'll get back CC verification
		# info that might help us with data quality checks in the future?
		"cc_first_name": pledge.extra['contribNameFirst'],
		"cc_last_name": pledge.extra['contribNameLast'],
		"cc_zip": pledge.extra['contribZip'],

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
	return DemocracyEngineAPI.create_transaction(de_txn_req)

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
	fees_rate = Pledge.current_algorithm()['fees']
	max_contrib = pledge.amount / (1 + fees_rate)

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
	total_charge = contrib_total * (1 + fees_rate)

	# Round to the nearest cent, then ensure we haven't exeeded maximum.
	total_charge = total_charge.quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_HALF_EVEN)
	if total_charge > pledge.amount:
		total_charge = pledge.amount

	# Fees are the difference between the total and the contributions.
	fees = total_charge - contrib_total

	# Return!
	return (recip_contribs, fees, total_charge)

def create_pledge_transaction(pledge, recip_contribs, fees):
	# Pledge execution --- make a credit card charge and return
	# the DE transaction record.

	from contrib.utils import DemocracyEngineAPI

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

	# Execute the authorization & capture.
	de_txn_req = create_de_txn_basic_dict(pledge)
	de_txn_req.update({
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
	return DemocracyEngineAPI.create_transaction(de_txn_req)
