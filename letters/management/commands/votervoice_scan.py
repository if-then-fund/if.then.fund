from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from optparse import make_option

from contrib.models import Actor
from letters.views import votervoice, state_at_large, state_no_senators

import csv, sys, multiprocessing
import difflib

class Command(BaseCommand):
	args = ''
	help = 'Scan VoterVoice\'s targets for unmatched IDs and unexpected messagedeliveryoptions.'

	def handle(self, *args, **options):
		# Get VoterVoice's list of US officials.
		all_officials = votervoice("GET", "governments/USA/officials", {
				"association": settings.VOTERVOICE_ASSOCIATION,
			}, {})

		# Pare down to federal legislators.
		all_officials = [o for o in all_officials if o['office']['electedBody'] in ('US Senate', "US House")]

		errors = []

		# Check ID mapping between Actor and VoterVoice officials.
		check_mapping_to_actors(all_officials, errors)

		# Process the legislators in parallel because we have to issue lots of
		# separate HTTP requests to check message delivery options.
		with multiprocessing.Pool() as pool:
			errors += sum(pool.map(check_message_delivery_options, all_officials), [])

		# Display errors.
		w = csv.writer(sys.stdout)
		for official, error in errors:
			w.writerow([official['id'], official['displayName'], error])

@transaction.atomic # faster saves so db doesn't commit after each
def check_mapping_to_actors(all_officials, errors):
	for official in all_officials:
		errors += check_mapping_to_actor(official)

def check_mapping_to_actor(official):
	# Do we have a mapping for this official to an Actor?
	if Actor.objects.filter(votervoice_id=official['id']).exists():
		# We do. Return.
		return []

	# Try to map this official to an Actor in our database.

	if official['office']['electedBody'] == 'US Senate':
		# This is a prefix, since our office IDs for senators
		# end with an election class. Get all possible senators.
		office_id = "S-%s-" % official['office']['state']
		actors = Actor.objects.filter(office__startswith=office_id)

		# Narrow to the one where the names have the shortest edit distance.
		if len(actors) == 0:
			actor = None
		else:
			actor = max(actors, key = lambda a :
				difflib.SequenceMatcher(None, official['displayName'], a.name_long).ratio()
				)

	elif official['office']['electedBody'] == 'US House':
		def s_d(state, district):
			district = int(district)
			if state in state_at_large + state_no_senators:
				assert district == 1
				district = 0
			return (state, district)
		office_id = "H-%s-%02d" % s_d(official['office']['state'], official['office']['electoralDistrict'])
		actor = Actor.objects.filter(office=office_id).first()

	else:
		raise ValueError(repr(official['office']))

	if actor is None:
		return [(official, "Could not map to Actor.")]
	elif actor.votervoice_id is not None:
		return [(official, "Wanted to map to actor that already has a votervoice_id: %d %s"  % (actor.id, str(actor)))]
	else:
		# Save the mapping.
		actor.votervoice_id = official['id']
		actor.save(update_fields=['votervoice_id'])

		# Report the new mapping for manual verification.
		return [(official, "Mapped to %d: %s." % (actor.id, str(actor)))]

def check_message_delivery_options(official):
	errors = []

	# Get current message delivery options from VoterVoice.
	mdos = votervoice("GET", "advocacy/messagedeliveryoptions", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"targettype": "E",
		"targetid": official['id'],
		}, {})

	# Can messages be delivered at all?
	if len(mdos) == 0:
		errors.append((official, "No messagedeliveryoptions."))
		return errors

	# Is it a delivery method we respect?
	mdos = mdos[0]
	if mdos['deliveryMethod'] not in ("webform", "communicatingwithcongressapi"):
		errors.append((official, "Top delivery method is %s." % mdos['deliveryMethod']))
		return errors

	# Are there any unexpected requiredUserFields?
	for rf in mdos.get('requiredUserFields', []):
		if rf not in ('address', 'phone', 'email'):
			errors.append((official, "has requiredField %s." % rf))

	# Are there any unexpected sharedQuestionIds?
	for sq in mdos.get('sharedQuestionIds', []):
		if sq not in ("US", "CommonHonorific", "CommunicatingWithCongressHonorific"):
			errors.append((official, "has sharedQuestion %s." % sq))

	# Are there any requiredQuestions?
	for rq in mdos.get('requiredQuestions', []):
		errors.append((official, "has requiredQuestion: %s" % repr(rq)))

	return errors
