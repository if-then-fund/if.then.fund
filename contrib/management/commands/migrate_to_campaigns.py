from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from itfsite.models import Campaign, CampaignStatus
from contrib.models import Trigger, TriggerStatus, Pledge

class Command(BaseCommand):
	args = ''
	help = 'Single-use data migration.'

	def handle(self, *args, **options):
		# Create a campaign for every trigger.
		for t in Trigger.objects.all():
			c = Campaign.objects.create(
				id=t.id,
				title=t.title,
				slug=t.slug,
				subhead=t.subhead,
				subhead_format=t.subhead_format,
				status=CampaignStatus.Open if t.status == TriggerStatus.Open else CampaignStatus.Closed,
				headline=t.title,
				body_text=t.description,
				body_format=t.description_format,
				extra={ },
				)
			c.contrib_triggers.add(t)

		# Set the via_campaign of every pledge.
		for p in Pledge.objects.all():
			p.via_campaign = Campaign.objects.get(id=p.trigger_id) # same id, per above
			p.save(update_fields=['via_campaign'])
