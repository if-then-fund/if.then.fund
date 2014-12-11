# Geocodes any executed pledges that haven't been geocoded yet.
# -------------------------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import PledgeExecution, PledgeExecutionProblem
from contrib.via_govtrack import geocode

class Command(BaseCommand):
	args = ''
	help = 'Geocodes executed pledges.'

	def handle(self, *args, **options):
		pledgexecs = PledgeExecution.objects.filter(
			problem=PledgeExecutionProblem.NoProblem,
			district=None,
			).select_related("pledge")

		for pe in pledgexecs:
			district, metadata = geocode([
				pe.pledge.extra['contribAddress'],
				pe.pledge.extra['contribCity'],
				pe.pledge.extra['contribState'],
				pe.pledge.extra['contribZip']])
			if district == None:
				# Could not geocode. But mark that we tried so we don't
				# try again.
				district = "UNKN"
			pe.update_district(district, metadata)
			print(district, pe)
