# Geocodes any executed pledges that haven't been geocoded yet.
# -------------------------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import ContributorInfo

class Command(BaseCommand):
	args = ''
	help = 'Geocodes ContributorInfos.'

	def handle(self, *args, **options):
		profiles = ContributorInfo.objects.filter(is_geocoded=False)
		for profile in profiles:
			try:
				profile.geocode()
			except OSError as e:
				print(profile.id, profile, e)
