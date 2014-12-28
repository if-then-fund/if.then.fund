# Connects our Recipient objects to Democracy Engine recipient IDs.
# -----------------------------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contrib.models import Recipient
from contrib.bizlogic import DemocracyEngineAPI

import rtyaml

class Command(BaseCommand):
	args = ''
	help = 'Connects our Recipient objects to Democracy Engine recipient IDs.'

	@transaction.atomic
	def handle(self, *args, **options):
		# There shall be no connections to DE other than the recipients returned
		# to us.
		Recipient.objects.update(de_id=None)

		# Get remote recipients.
		recipients = DemocracyEngineAPI.recipients()

		# Assign.
		for r in recipients:
			# Skip staging recipients.
			if r['name'].startswith('ClientTest '): continue

			# Assign by GovTrack ID.
			if r['recipient_id'].startswith('p_'):
				try:
					rx = Recipient.objects.get(
						actor__govtrack_id=int(r['recipient_id'][2:]),
						challenger=None)
				except Recipient.DoesNotExist:
					print('No Recipient object for:')
					print(rtyaml.dump(r))
					continue

				rx.de_id = r['recipient_id']
				rx.save(update_fields=['de_id'])	

			else:
				print('Don\'t know what to do with:')
				print(rtyaml.dump(r))
				continue
