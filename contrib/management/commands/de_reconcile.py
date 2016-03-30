# Reconciles our records with Democracy Engine
# --------------------------------------------

from decimal import Decimal
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

import rtyaml

from contrib.models import Pledge, PledgeStatus, PledgeExecutionProblem
from contrib.bizlogic import DemocracyEngineAPI

class Command(BaseCommand):
	args = ''
	help = 'Reports reconciliation issues between our records and Democracy Engine.'

	def handle(self, *args, **options):
		# Get recent donations from DE.
		donations = DemocracyEngineAPI.donations()

		# Process each.
		pledge_donations = defaultdict(lambda : [])
		for don in donations:
			self.process_donation(don, pledge_donations)

		# Any executed pledges missing from the apparent range of donations DE is returning?
		first_pledge = min(pledge_donations, key = lambda p : p.id)
		last_pledge = max(pledge_donations, key = lambda p : p.id)
		print("Reconciliation between pledge", first_pledge.id, first_pledge.created, "and", last_pledge.id, last_pledge.created, ".")
		for i in range(first_pledge.id+1, last_pledge.id):
			# Get a pledge for each ID in the range of pledges DE is reporting for us.
			# Only get executed pledges, and exclude executed pledges with client-side problems
			# (i.e. skip ones that never went to DE).
			# A pledge may not exist for every id, since a pledge may be canceled (=>deleted).
			p = Pledge.objects\
				.filter(id=i, status=PledgeStatus.Executed)\
				.exclude(execution__problem__in=(PledgeExecutionProblem.EmailUnconfirmed, PledgeExecutionProblem.FiltersExcludedAll))\
				.first()
			if p:
				# This pledge exists. Do we have a donation record for it?
				if not p in pledge_donations:
					print("No transaction for", p.id, p)

		# Dangling transactions.
		for p, dons in sorted(pledge_donations.items(), key = lambda kv : kv[0].id):
			# If a pledge is not executed, it should have no non-void/credit donation records.
			# When there's a weird problem, we might manually void/credit.
			active_donations = [don for don in dons if don["line_items"][0]["status"] not in ("voided", "credited")]
			if p.status != PledgeStatus.Executed:
				if len(active_donations) > 0:
					print(p.id, p, "is not executed but donations exist for it!")
					for don in active_donations:
						print("\t", don["donation_id"], don["created_at"], don["line_items"][0]["status"], don["line_items"][0]["transaction_amount"], "=>", "void_transaction", don["line_items"][0]["transaction_guid"])
					print()

			# Check that the transaction details look OK - first for failed transactions.
			elif p.execution.problem == PledgeExecutionProblem.TransactionFailed:
				# Ensure this pledge is associated only with failed transactions. If there is more
				# than one such domation, well that's odd, but it ultimately doesn't matter.
				for don in dons:
					if not don["line_items"][0]["transaction_error"] or don["line_items"][0]["transaction_amount"] != "$0.00":
						print(p.id, p, don["donation_id"], don["created_at"], don["line_items"][0]["status"], don["line_items"][0]["transaction_amount"], "=>", "transaction", don["line_items"][0]["transaction_guid"], "had a transaction error but transaction doesn't show an error.")

			# ... and transactions that we voided or credited.
			elif p.execution.problem == PledgeExecutionProblem.Voided:
				# Ensure this pledge is associated only with voided/credited transactions. If there is more
				# than one such donation, well, it doesn't really matter since the money was returned.
				for don in dons:
					if don["line_items"][0]["status"] not in ("voided", "credited"):
						print(p.id, p, don["donation_id"], "was voided but DE shows status", don["line_items"][0]["status"])

			# Now check successfully executed pledges.

			# There should be exactly one non-voided/credited donation record.
			elif len(active_donations) > 1:
				print(p.id, p, "has more than one donation:")
				for don in dons:
					print("\t", don["donation_id"], don["created_at"], don["line_items"][0]["status"], don["line_items"][0]["transaction_amount"], "=>", "void_transaction", don["line_items"][0]["transaction_guid"])
				print()
			elif len(active_donations) == 0:
				print(p.id, p, "has only voided/credited donations:")
				for don in dons:
					print("\t", don["donation_id"], don["created_at"], don["line_items"][0]["status"], don["line_items"][0]["transaction_amount"], don["line_items"][0]["status"])
				print()

			# And that record should match our execution's record.
			else:
				don = active_donations[0]

				if don["line_items"][0]["transaction_error"]:
					print(p.id, p, don["donation_id"], "had a transaction error but we think it went ok.")

				amt = Decimal(don["line_items"][0]["transaction_amount"].replace("$", ""))
				if amt != p.execution.charged:
					print(p.id, p, don["donation_id"], "disagreement on the transaction amount.")


	def process_donation(self, don, pledge_donations):
		if don["authtest_request"]:
			# This was an authorization test. There's no need to
			# reconcile these. The pledge may have been cancelled,
			# whatever.
			return

		# This is an actual transaction.

		# Sanity checks.

		if not don["authcapture_request"]:
			print(don["donation_id"], "has authtest_request, authcapture_request both False")
			return

		if len(don["line_items"]) == 0:
			print(don["donation_id"], "has no line items")
			return

		txns = set()
		for line_item in don["line_items"]:
			txns.add(line_item["transaction_guid"])
		if len(txns) != 1:
			print(don["donation_id"], "has more than one transaction (should be one)")
			return
		
		# What pledge does this correspond to?

		pledge = Pledge.objects.get(id=rtyaml.load(don["aux_data"])["pledge"])

		# Map the pledge to the donation(s) we see for it.

		pledge_donations[pledge].append(don)
