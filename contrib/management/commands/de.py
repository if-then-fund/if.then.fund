# Makes a Democracy Engine API call
# ---------------------------------

from django.core.management.base import BaseCommand, CommandError

import rtyaml

from contrib.bizlogic import DemocracyEngineAPI

class Command(BaseCommand):
	args = 'method_name arg1 arg2 . . .'
	help = 'Makes a Democracy Engine API call.'

	def handle(self, *args, **options):
		if len(args) == 0:
			print("Specify a method name.")
			return

		# get the function to call
		args = list(args)
		method = args.pop(0)
		method = getattr(DemocracyEngineAPI, method)

		# invoke
		ret = method(*args)

		# display
		print(rtyaml.dump(ret))
