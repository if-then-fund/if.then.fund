# Load and parse current Members of Congress from GovTrack
# --------------------------------------------------------
#
# We use GovTrack and not the Github United States/Congress-legislators
# project because GovTrack provides us nice name formatting, role descriptions,
# etc.

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import requests

from contrib.models import Actor, ActorParty, Recipient

party_map = {
	'Democrat': ActorParty.Democratic,
	'Republican': ActorParty.Republican,
}

class Command(BaseCommand):
	args = ''
	help = 'Creates/updates Actor instances for current Members of Congress via the GovTrack API.'

	def handle(self, *args, **options):
		# Load and parse current Members of Congress from GovTrack.
		r = requests.get("https://www.govtrack.us/api/v2/role?current=true&limit=550").json()

		# Create Actor instances.
		for p in r['objects']:
			# Exclude president/vice president.
			if p['role_type'] not in ('representative', 'senator'):
				continue

			# Group independents with the party they caucus with.
			if p['party'] == "Independent":
				p['party'] = p['caucus']

			# Actor instance field values.
			fields = {
				'name_long': p['person']['name'],
				'name_short': p['person']['lastname'],
				'name_sort': p['person']['sortname'],
				'party': party_map[p['party']],
				'title': p['description'],	
			}

			# Create or update.
			actor, is_new = Actor.objects.get_or_create(
				govtrack_id = p["person"]["id"],
				defaults = fields,
				)

			if not is_new:
				# Update. These are required fields so we
				# had to specify them in get_or_create.
				# Now report what's changed.
				for k, v in fields.items():
					if getattr(actor, k) != v:
						self.stdout.write('%s\t%s=>%s' % (actor.name_long, getattr(actor, k), v))
					setattr(actor, k, v)

			# Store the full API response from GovTrack in the Actor instance.
			if actor.extra in (None, ''): actor.extra = { }
			actor.extra['govtrack_role'] = p
			actor.save()

			if is_new:
				self.stdout.write('Added: ' + actor.name_long)

			Recipient.create_for(actor)
