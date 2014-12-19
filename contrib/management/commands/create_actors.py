# Load and parse current Members of Congress
# ------------------------------------------
#
# Data is obtained from https://github.com/unitedstates/congress-legislators.

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal

import requests
import rtyaml

from contrib.models import Actor, ActorParty, Recipient

party_map = {
	'Democrat': ActorParty.Democratic,
	'Republican': ActorParty.Republican,
}

statenames = {"AL":"Alabama", "AK":"Alaska", "AS":"American Samoa", "AZ":"Arizona", "AR":"Arkansas", "CA":"California", "CO":"Colorado", "CT":"Connecticut", "DE":"Delaware", "DC":"District of Columbia", "FL":"Florida", "GA":"Georgia", "GU":"Guam", "HI":"Hawaii", "ID":"Idaho", "IL":"Illinois", "IN":"Indiana", "IA":"Iowa", "KS":"Kansas", "KY":"Kentucky", "LA":"Louisiana", "ME":"Maine", "MD":"Maryland", "MA":"Massachusetts", "MI":"Michigan", "MN":"Minnesota", "MS":"Mississippi", "MO":"Missouri", "MT":"Montana", "NE":"Nebraska", "NV":"Nevada", "NH":"New Hampshire", "NJ":"New Jersey", "NM":"New Mexico", "NY":"New York", "NC":"North Carolina", "ND": "North Dakota", "MP":"Northern Mariana Islands", "OH":"Ohio", "OK":"Oklahoma", "OR":"Oregon", "PA":"Pennsylvania", "PR":"Puerto Rico", "RI":"Rhode Island", "SC":"South Carolina", "SD":"South Dakota", "TN":"Tennessee", "TX":"Texas", "UT":"Utah", "VT":"Vermont", "VI":"Virgin Islands", "VA":"Virginia", "WA":"Washington", "WV":"West Virginia", "WI":"Wisconsin", "WY":"Wyoming", "DK": "Dakota Territory", "PI": "Philippines Territory/Commonwealth", "OL": "Territory of Orleans"}

class Command(BaseCommand):
	args = ''
	help = 'Creates/updates Actor instances for current Members of Congress via the unitedstates/congress-legislators project.'

	def handle(self, *args, **options):
		# Load and parse current Members of Congress YAML.
		r = requests.get("https://raw.githubusercontent.com/unitedstates/congress-legislators/master/legislators-current.yaml")
		r = rtyaml.load(r.content)

		# Create Actor instances.
		for p in r:
			# The last term is the Member of Congress's current term.
			term = p['terms'][-1]
			del p['terms']
			p['term'] = term

			# Group independents with the party they caucus with. Try the
			# 'caucus' field first, and if it's not set (which is typical)
			# then use the party field. After that there should be no
			# independents.
			party = party_map[term.get('caucus', term['party'])]

			# Actor instance field values.
			fields = {
				'name_long': build_name(p, term, mode="full"),
				'name_short': p['name']['last'],
				'name_sort': build_name(p, term, mode="sort"),
				'party': party,
				'title': build_title(p, term),
			}

			# Create or update.
			actor, is_new = Actor.objects.get_or_create(
				govtrack_id = p["id"]["govtrack"],
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
			actor.extra['legislators-current'] = p
			actor.save()

			if is_new:
				self.stdout.write('Added: ' + actor.name_long)

			Recipient.create_for(actor)

def build_name(p, t, mode):
	# Based on:
	# https://github.com/govtrack/govtrack.us-web/blob/master/person/name.py

	# First name.
	firstname = p['name']['first']
	if firstname.endswith('.'):
		firstname = p['name']['middle']
	if p['name'].get('nickname') and len(p['name']['nickname']) < len(firstname):
			firstname = p['name']['nickname']

	# Last name.
	lastname = p['name']['last']
	if p['name'].get('suffix'):
		lastname += ' ' + p['name']['suffix']

	# Title.
	if t['type'] == "sen":
		title = "Sen."
	elif t['state'] == "PR":
		# Puerto Rico's delegate is a Resident Commissioner. Currently delegates
		# have no real voting privileges, so we may not need this, but we'll
		# include for completeness.
		title = "Commish"
	elif t['state'] in ('AS', 'DC', 'GU', 'MP', 'VI'):
		# The delegates.
		title = "Del."
	else:
		# Normal representatives.
		title = "Rep."

	# Role info.
	# Using an en dash to separate the party from the state
	# and a U+2006 SIX-PER-EM SPACE to separate state from
	# district. Will that appear ok/reasonable?
	if t.get('district') in (None, 0):
		role = "(%s–%s)" % (t['party'][0], t['state'])
	else:
		role = "(%s–%s %d)" % (t['party'][0], t['state'], t['district'])

	if mode == "full":
		return title + ' ' + firstname + ' ' + lastname + ' ' + role
	elif mode == "sort":
		return lastname + ', ' + firstname + ' (' + title + ') ' + role
	else:
		raise ValueError(mode)

def build_title(p, t):
	if t['type'] == "sen":
		return t['state_rank'][0].upper() + t['state_rank'][1:] + " Senator from " + statenames[t['state']]
	elif t['state'] == "PR":
		return "Resident Commissioner for Puerto Rico"
	elif t['state'] in ('AS', 'DC', 'GU', 'MP', 'VI'):
		return "Delegate from " + statenames[t['state']]
	elif t['district'] == 0:
		return "Representative for " + statenames[t['state']] + " At-Large"
	else:
		return "Representative for " + statenames[t['state']] + "’s " + ordinal(t['district']) + " Congressional District"
