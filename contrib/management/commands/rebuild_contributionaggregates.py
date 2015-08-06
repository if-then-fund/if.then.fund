from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import ContributionAggregate

class Command(BaseCommand):
	args = ''
	help = 'Rebuilds the ContributionAggregate table.'

	def handle(self, *args, **options):
		ContributionAggregate.rebuild()
		