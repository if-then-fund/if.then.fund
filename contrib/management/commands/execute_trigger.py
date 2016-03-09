# Execute a trigger using a congressional vote.
# ---------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import Trigger
from contrib.legislative import execute_trigger_from_votes

class Command(BaseCommand):
	args = 'trigger_id [-]vote_url [[-]vote_url...]'
	help = 'Executes a trigger (by ID) using the URL to a GovTrack vote page.'

	def handle(self, *args, **options):
		args = list(args)
		if len(args) < 2:
			print("Usage: ./manage.my execute_trigger trigger_id [[-]vote_url...]")
			print("Precede a vote URL with a minus sign to flip its valence.")
			return
		
		# What trigger to execute.	
		t = Trigger.objects.get(id=args.pop(0))

		# What votes?
		votes = []
		for arg in args:
			flip = False
			if arg[0] == "-":
				flip = True
				arg = arg[1:]
			votes.append({
				"url": arg,
				"flip": flip,
			})

		# Go!
		execute_trigger_from_votes(t, votes)

		# Show what happened.
		import pprint
		print(t.execution.description)
		pprint.pprint(t.execution.get_outcome_summary())
