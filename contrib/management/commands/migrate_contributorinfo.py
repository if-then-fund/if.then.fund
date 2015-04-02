# one-time migration to the new ContributorInfo model

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contrib.models import Pledge, ContributorInfo

import json

class Command(BaseCommand):
	args = ''

	@transaction.atomic
	def handle(self, *args, **options):
		# Fix the pledges one by one in order of creation.
		for p in Pledge.objects.order_by('created'):
			c = ContributorInfo()
			c.cclastfour = p.cclastfour
			c.extra = { }
			c.extra['contributor'] = p.extra['contributor']
			c.extra['billing'] = p.extra['billing']
			if "via_pledge" in c.extra['billing']: del c.extra['billing']['via_pledge'] # not needed anymore

			# dedup
			for c2 in ContributorInfo.objects.filter(cclastfour=c.cclastfour):
				if c.same_as(c2):
					c = c2
					break

			# save and assign
			if not c.id: c.save()
			print(p.id, c.id)
			p.profile = c
			p.save(update_fields=['profile'])