# Update bill cosponsor triggers.
# -------------------------------
#
# Uses the GovTrack API to update local data on bill (co)sponsorship.

from django.core.management.base import BaseCommand, CommandError

from contrib.models import Trigger
from contrib.legislative import create_trigger_for_sponsors

import tqdm

class Command(BaseCommand):
	args = ''
	help = 'Update bill cosponsor triggers.'

	def handle(self, *args, **options):
		prefix = "usbill:sponsors:"
		for trigger in tqdm.tqdm(Trigger.objects.filter(key__startswith=prefix)):
			bill_id = trigger.key[len(prefix):]
			create_trigger_for_sponsors(bill_id, update=True)
		