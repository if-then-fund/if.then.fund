# Execute a trigger using a congressional vote.
# ---------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import Trigger
from contrib.legislative import execute_trigger_from_vote

class Command(BaseCommand):
	args = 'trigger_id vote_url'
	help = 'Executes a trigger (by ID) using the URL to a GovTrack vote page.'

	def handle(self, *args, **options):
		if len(args) < 2:
			print("Usage: ./manage.my execute_trigger trigger_id vote_url")
			return
			
		t = Trigger.objects.get(id=args[0])
		url = args[1]
		execute_trigger_from_vote(t, url)
