# Executes any open pledges on executed triggers.
# -----------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from contrib.models import TriggerStatus, Pledge, PledgeStatus
from contrib.legislative import execute_trigger_from_vote

import sys, tqdm
from taskutils import exclusive_process

class Command(BaseCommand):
	args = ''
	help = 'Executes any open pledges on executed triggers.'

	def handle(self, *args, **options):
		# Ensure this process does not run concurrently.
		exclusive_process('itf-execute-pledges')

		# Open pledges on executed triggers can be executed.
		pledges_to_execute = Pledge.objects.filter(status=PledgeStatus.Open, trigger__status=TriggerStatus.Executed)\
			.select_related('trigger')

		# Skip recent pledges with unconfirmed email addresses to give the user
		# time to confirm their address. For new trigger executions, this may
		# delay executing all of the triggers. For pledges on already-executed
		# triggers, give the pledge sort of a time-out before marking it as
		# executed with a problem (unconfirmed email).
		pledges_to_execute = [p for p in pledges_to_execute
			if p.user
				or p.created < timezone.now() - timedelta(days=1) ]

		# Loop through them.
		if sys.stdout.isatty(): pledges_to_execute = tqdm.tqdm(pledges_to_execute)
		for p in pledges_to_execute:
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
