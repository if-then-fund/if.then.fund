# Dups all Democracy Engine recipients
# ------------------------------------

from django.core.management.base import BaseCommand, CommandError

import rtyaml

from contrib.bizlogic import DemocracyEngineAPI

class Command(BaseCommand):
	args = ''
	help = 'Dumps all Democracy Engine recipients.'

	def handle(self, *args, **options):
		print(rtyaml.dump(DemocracyEngineAPI.recipients()))
