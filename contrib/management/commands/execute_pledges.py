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
		# Open pledges on executed triggers can be executed.
		pledges_to_execute = Pledge.objects.filter(status=PledgeStatus.Open, trigger__status=TriggerStatus.Executed)

		# Loop through them.
		for p in tqdm.tqdm(pledges_to_execute):
			# Execute the pledge.
			try:
				p.execute()

			# ValueError indicates a known condition that makes the pledge
			# non-executable. We should skip it. Sometimes it just means
			# we have to wait.
			except ValueError as e:
				print(p)
				print(e)
				print()
