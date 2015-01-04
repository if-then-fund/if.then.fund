# Executes any open pledges on executed triggers.
# -----------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import TriggerStatus, Pledge, PledgeStatus
from contrib.legislative import execute_trigger_from_vote

import tqdm

class Command(BaseCommand):
	args = ''
	help = 'Executes any open pledges on executed triggers.'

	def handle(self, *args, **options):
		for p in tqdm.tqdm(Pledge.objects.filter(status=PledgeStatus.Open, trigger__status=TriggerStatus.Executed)):
			p.execute()
