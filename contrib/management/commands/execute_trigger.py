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
		args = list(args)
		if len(args) < 2:
			print("Usage: ./manage.my execute_trigger trigger_id [flip] vote_url")
			return
		
		# What trigger to execute.	
		t = Trigger.objects.get(id=args.pop(0))

		# Whether the aye/nays of the vote correspond to +/- of the
		# trigger, or the reverse if we're using a vote on the polar
		# opposite of how the trigger is layed out.
		flip = False
		if args[0] == "flip":
			flip = True
			args.pop(0)

		# The GovTrack URL to pull vote data from.
		url = args.pop(0)

		# Go!
		execute_trigger_from_vote(t, url, flip=flip)
