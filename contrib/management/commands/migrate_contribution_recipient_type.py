from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import Contribution, ContributionRecipientType

class Command(BaseCommand):
	args = ''
	help = ''

	def handle(self, *args, **options):
		Contribution.objects.exclude(recipient__actor=None).update(recipient_type = ContributionRecipientType.Incumbent)
		Contribution.objects.filter(recipient__actor=None).update(recipient_type = ContributionRecipientType.GeneralChallenger)

		assert(
			Contribution.objects.filter(recipient_type=ContributionRecipientType.Incumbent).count()
			== len([c for c in Contribution.objects.all().select_related('recipient') if not c.recipient.is_challenger]))
		assert(
			Contribution.objects.filter(recipient_type=ContributionRecipientType.GeneralChallenger).count()
			== len([c for c in Contribution.objects.all().select_related('recipient') if c.recipient.is_challenger]))		