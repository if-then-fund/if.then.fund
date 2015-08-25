from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from optparse import make_option

from letters.views import votervoice

import multiprocessing

class Command(BaseCommand):
	args = ''
	help = 'Report VoterVoice\'s unexpected messagedeliveryoptions.'

	def handle(self, *args, **options):
		all_officials = votervoice("GET", "governments/USA/officials", {
				"association": settings.VOTERVOICE_ASSOCIATION,
			})
		all_officials = [o for o in all_officials if o['office']['electedBody'] in ('US Senate', "US House")]

		with multiprocessing.Pool() as pool:
			errors = pool.map(get_official_message_delivery_options, all_officials)
		errors = sum(errors, [])

		for error in errors:
			print(error[0]['id'], error[0]['displayName'], error[1])

def get_official_message_delivery_options(official):
	# official['id']
	# official['office']['electedBody']
	# official['office']['state']
	# int(official['office']['electoralDistrict']
	# official['displayName']

	print(official['displayName'] + '...')

	errors = []

	# Get current message delivery options from VoterVoice.
	mdos = votervoice("GET", "advocacy/messagedeliveryoptions", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"targettype": "E",
		"targetid": official['id'],
		})

	if len(mdos) == 0:
		errors.append((official, "No messagedeliveryoptions."))
		return errors

	mdos = mdos[0]
	if mdos['deliveryMethod'] not in ("webform", "communicatingwithcongressapi"):
		errors.append((official, "Top delivery method is %s." % mdos['deliveryMethod']))
		return errors

	for rf in mdos.get('requiredUserFields', []):
		if rf not in ('address', 'phone', 'email'):
			errors.append((official, "has requiredField %s." % rf))

	for sq in mdos.get('sharedQuestionIds', []):
		if sq not in ("US", "CommonHonorific", "CommunicatingWithCongressHonorific"):
			errors.append((official, "has sharedQuestion %s." % sq))

	for rq in mdos.get('requiredQuestions', []):
		errors.append((official, "has requiredQuestion: %s" % repr(rq)))

	return errors
