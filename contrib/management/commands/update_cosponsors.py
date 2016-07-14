# Update bill cosponsor triggers.
# -------------------------------
#
# Uses the GovTrack API to update local data on bill (co)sponsorship.

from django.core.management.base import BaseCommand, CommandError

from contrib.models import Trigger
from contrib.legislative import create_trigger_for_sponsors, create_trigger_for_sponsors_with_companion_bill

import tqdm

class Command(BaseCommand):
	args = ''
	help = 'Update bill cosponsor triggers.'

	def handle(self, *args, **options):
		# Regular sponsors triggers. Set update=True to force a GovTrack API query.
		prefix = "usbill:sponsors:"
		for trigger in tqdm.tqdm(Trigger.objects.filter(key__startswith=prefix)):
			bill_id = trigger.key[len(prefix):]
			create_trigger_for_sponsors(bill_id, update=True)
		
		# Companion bill triggers.
		# update=False here because we don't need to update the regular sponsor
		# triggers via a GovTrack API lookup. We just need to refresh the supertrigger's
		# metadata, which always occurs.
		prefix = "usbill:sponsors-with-companion:"
		for trigger in tqdm.tqdm(Trigger.objects.filter(key__startswith=prefix)):
			bill_id = trigger.key[len(prefix):]
			create_trigger_for_sponsors_with_companion_bill(bill_id, update=False)
