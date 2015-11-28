# Send users emails of new notifications.
# ---------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from itfsite.models import Campaign

import sys
import tqdm

class Command(BaseCommand):
	args = ''
	help = ''

	def handle(self, *args, **options):
		for campaign in tqdm.tqdm(Campaign.objects.all()):
			if (campaign.extra or {}).get("style", {}).get("splash", {}).get("class") == "invert-text":
				del campaign.extra["style"]["splash"]["class"]
				campaign.extra["style"]["splash"]["invert_text"] = True
				campaign.save(update_fields=["extra"])