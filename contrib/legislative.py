from contrib.models import Trigger, TextFormat, TriggerType, Actor
from contrib.utils import query_json_api

from django.conf import settings
from django.utils.timezone import now

ALLOW_DEAD_BILL = False

def parse_uscapitol_local_time(dt):
	from django.utils.timezone import make_aware
	import dateutil.parser, dateutil.tz
	if not hasattr(parse_uscapitol_local_time, 'tz'):
		parse_uscapitol_local_time.tz = dateutil.tz.tzfile('/usr/share/zoneinfo/EST5EDT')
	return make_aware(dateutil.parser.parse(dt), parse_uscapitol_local_time.tz)

class TriggerAlreadyExistsException(Exception):
	pass

def get_trigger_type_for_vote(chamber):
	# get/create TriggerType for 'h' 's' or 'x' votes
	# (in production the object should always exist, but in testing it
	# needs to be created)
	trigger_type, is_new = TriggerType.objects.get_or_create(
		key = "congress_floorvote_%s" % chamber,
		title = { 's': 'Senate Vote', 'h': 'House Vote', 'x': 'House or Senate Vote (Whichever Comes First)' }[chamber],
		defaults = {
		"strings": {
			"actor": { 's': 'senator', 'h': 'representative', 'x': 'member of Congress' }[chamber],
			"actors": { 's': 'senators', 'h': 'representatives', 'x': 'members of Congress' }[chamber],
			"action_noun": "vote",
			"action_vb_inf": "vote",
			"action_vb_pres_s": "votes",
			"action_vb_past": "voted",
			"prospective_vp": "the vote occurs",
			"retrospective_vp": "the vote ocurred",
		},
		"extra": {
			"max_split":  { 's': 100, 'h': 435, 'x': 435 }[chamber],
		}
		})
	return trigger_type

def create_congressional_vote_trigger(chamber, title, short_title):
	t = Trigger()

	t.owner = None
	
	t.trigger_type = get_trigger_type_for_vote(chamber)
	
	t.title = title[0:200]

	chamber_name = { 's': 'Senate', 'h': 'House', 'x': 'Congress' }[chamber]
	t.description = "Your contribution will be distributed depending on how the %s votes on %s." % (chamber_name, short_title)
	t.description_format = TextFormat.Markdown

	t.outcomes = [
		{ "vote_key": "+", "label": "Yes on %s" % short_title, "object": "in favor of %s" % short_title },
		{ "vote_key": "-", "label": "No on %s" % short_title, "object": "against %s" % short_title },
	]

	t.extra = { }

	return t

def create_trigger_from_bill(bill_id, chamber):
	import re

	if bill_id.startswith("https://"):
		# This is a GovTrack URL to a bill page.
		m = re.match("https://www.govtrack.us/congress/bills/(\d+)/([a-z]+)(\d+)$", bill_id)
		if not m: raise ValueError("Invalid bill URL.")
		bill_congress, bill_type, bill_number = m.groups()
		bill_id = "%s%d-%d" % (bill_type, int(bill_number), int(bill_congress))
	else:
		# split/validate the bill ID
		m = re.match("^([a-z]+)(\d+)-(\d+)$", bill_id)
		if not m: raise ValueError("'%s' is not a bill ID, e.g. hr1234-114." % bill_id)
		bill_type, bill_number, bill_congress = m.groups()

	bill_type = { "hres": "house_resolution", "s": "senate_bill", "sjres": "senate_joint_resolution", "hr": "house_bill", "hconres": "house_concurrent_resolution", "sconres": "senate_concurrent_resolution", "hjres": "house_joint_resolution", "sres": "senate_resolution" }.get(bill_type)
	if not bill_type: raise ValueError("Not a bill ID, e.g. hr1234-114.")

	# validate chamber
	if chamber not in ('s', 'h', 'x'): raise ValueError("Chamber must be one of 'h' or 's'.")

	# get bill data from GovTrack
	bill_search = query_json_api("https://www.govtrack.us/api/v2/bill", {
		"bill_type": bill_type, "number": bill_number, "congress": bill_congress })
	if len(bill_search['objects']) == 0: raise ValueError("Not a bill.")
	if len(bill_search['objects']) > 1: raise ValueError("Matched multiple bills?")

	bill = bill_search['objects'][0]
	if not bill['is_alive'] and not ALLOW_DEAD_BILL: raise ValueError("Bill is not alive.")

	# we're going to cache the bill info, so add a timestamp for the retreival date
	bill['as_of'] = now().isoformat()

	# create object

	t = create_congressional_vote_trigger(chamber, bill['title'], bill["display_number"])

	t.key = "usbill:" + bill_id + ":" + chamber
	if Trigger.objects.filter(key=t.key).exists():
		raise TriggerAlreadyExistsException("A trigger for this bill and chamber already exists.")

	t.extra.update({
		"type": "usbill",
		"bill_id": bill_id,
		"chamber": chamber,
		"govtrack_bill_id": bill["id"],
		"bill_info": bill,
	})

	# save and return
	t.save()
	return t

def map_outcome_indexes(trigger, flip):
	# Map vote keys '+' and '-' to outcome indexes.
	outcome_index = { }
	for i, outcome in enumerate(trigger.outcomes):
		k = outcome['vote_key']

		# If the valence of the vote outcomes are opposite to how they
		# are structured in the trigger, we have to flip them.
		if flip:
			if len(trigger.outcomes) != 2:
				raise ValueError("Can't flip a vote on a trigger with not two outcomes.")
			k = { "+": "-", "-": "+" }[k]

		outcome_index[k] = i

	return outcome_index

def load_govtrack_vote(trigger, govtrack_url, flip):
	import lxml.etree

	outcome_index = map_outcome_indexes(trigger, flip)

	# Get vote metadata from GovTrack's API, via the undocumented
	# '.json' extension added to vote pages.
	vote = query_json_api(govtrack_url+'.json', {})

	# Sanity check that the chamber of the vote matches the trigger type.
	if trigger.trigger_type.key not in ('congress_floorvote_x', 'congress_floorvote_both', 'congress_floorvote_' + vote['chamber'][0], 'announced-positions'):
		raise Exception("The trigger type doesn't match the chamber the vote ocurred in.")

	# Parse the date, which is in US Eastern time. Must make it
	# timezone-aware to store in our database.
	when = parse_uscapitol_local_time(vote['created'])

	# Then get how Members of Congress voted via the XML, which conveniently
	# includes everything without limit/offset. The congress project vote
	# JSON doesn't use GovTrack IDs, so it's more convenient to use GovTrack
	# data.
	r = query_json_api(govtrack_url+'/export/xml', {}, raw=True)
	dom = lxml.etree.fromstring(r)
	actor_outcomes = [ ]
	for voter in dom.findall('voter'):
		# Validate.
		if not voter.get('id'):
			 # VP tiebreaker
			if voter.get('VP'):
				continue
			raise Exception("Missing data in GovTrack XML.")

		# Get the Actor.
		try:
			actor = Actor.objects.get(govtrack_id=voter.get('id'))
		except Actor.DoesNotExist:
			# We don't have an Actor object for this person. If we're loading
			# in an old vote to do a post-vote trigger with, some voters may
			# no longer be serving and that's ok.
			if when.year < 2015:
				continue

			if settings.DEBUG:
				print("No Actor instance exists here for Member of Congress with GovTrack ID %d." % int(voter.get('id')))
				continue
				
			raise Exception("No Actor instance exists here for Member of Congress with GovTrack ID %d." % int(voter.get('id')))

		# Map vote keys '+' and '-' to outcome indexes.
		# Treat not voting (0 and P) as a null outcome, meaning the Actor didn't
		# take action for our purposes but should be recorded as not participating.
		outcome = outcome_index.get(voter.get('vote'))

		if outcome is None:
			if voter.get('vote') == "0":
				outcome = "Did not vote."
			elif voter.get('vote') == "P":
				outcome = "Voted 'present'."
			else:
				raise ValueError("Invalid vote option key: " + str(voter.get('vote')))

		actor_outcomes.append({
			"actor": actor,
			"outcome": outcome,
		})

	return (vote, when, actor_outcomes)

def execute_trigger_from_data_urls(trigger, url_specs):
	if len(url_specs) == 0: raise ValueError("url_specs")

	# Load all of the data details.
	for url_spec in url_specs:
		if "/votes/" in url_spec["url"]:
			(vote, when, actor_outcomes) = load_govtrack_vote(trigger, url_spec["url"], flip=url_spec.get("flip", False))
			url_spec["noun"] = vote['chamber_label'] + " vote on " + when.strftime("%b. %d, %Y").replace(" 0", " ")
			url_spec["link"] = vote['link']
			url_spec["vote"] = vote
			url_spec["when"] = when
			url_spec["actor_outcomes"] = actor_outcomes
		elif "/bills/" in url_spec["url"]:
			# Get bill metadata from GovTrack's API, via the undocumented
			# '.json' extension added to bill pages.
			bill = query_json_api(url_spec["url"]+'.json')
			(bill, actor_outcomes) = load_govtrack_sponsors(trigger, url_spec["url"], flip=url_spec.get("flip"))
			url_spec["noun"] = "sponsors as of " + now().strftime("%b. %d, %Y").replace(" 0", " ")
			url_spec["link"] = bill['link']
			url_spec["bill"] = bill
			url_spec["when"] = now()
			url_spec["actor_outcomes"] = actor_outcomes
		else:
			raise ValueError("unrecognized URL type")

	# Make a textual description of what happened.
	description = "Contributions are being made based on " + "; ".join(
		"the [{noun}]({link})".format(
			noun=url_spec["noun"],
			link=url_spec['link'],
		)
		for url_spec in url_specs) \
		+ "."

	# Merge the actor_outcomes of the votes. Check that an actor doesn't appear
	# in multiple votes.
	actor_outcomes = [ ]
	seen_actors = set()
	for url_spec in url_specs:
		for actor_outcome in url_spec["actor_outcomes"]:
			if actor_outcome["actor"] in seen_actors:
				raise ValueError("Actor %s is present in multiple data URLs." % str(actor))
			actor_outcomes.append(actor_outcome)
			seen_actors.add(actor_outcome["actor"])

	# Execute.
	trigger.execute(
		min(url_spec["when"] for url_spec in url_specs), # earliest vote date => Trigger.action_time
		actor_outcomes,
		description,
		TextFormat.Markdown,
		{
			"govtrack_votes": [url_spec["vote"] for url_spec in url_specs if "vote" in url_spec],
			"govtrack_bills": [url_spec["bill"] for url_spec in url_specs if "bill" in url_spec],
		})

def load_govtrack_sponsors(trigger, bill, flip=False):
	outcome_index = map_outcome_indexes(trigger, flip)

	# Sanity check that the chamber of the vote matches the trigger type.
	if trigger.trigger_type.key not in ('congress_sponsors_both', 'congress_sponsors_' + bill['bill_type'][0].lower(), 'announced-positions'):
		raise Exception("The trigger type isn't one about bill sponsors or is for the wrong chamber.")

	actor_outcomes = [ ]
	for person in [bill.get('sponsor')] + bill.get('cosponsors', []):
		# Convert GovTrack ID to Actor object.
		if person is None: continue # empty sponsor
		try:
			actor = Actor.objects.get(govtrack_id=person.get('id'))
		except Actor.DoesNotExist:
			# See corresponding block for votes.
			raise Exception("No Actor instance exists here for Member of Congress with GovTrack ID %d." % int(person.get('id')))

		# Sponsors and cosponsors are all "pro".
		outcome = outcome_index.get("+")
		actor_outcomes.append({
			"actor": actor,
			"outcome": outcome,
		})

	return (bill, actor_outcomes)


def get_trigger_type_for_sponsors(chamber):
	# get/create TriggerType for House ('h') or Senate ('s') sponsors of a bill.
	# (A bill can only have sponsors in its originating chamber.)
	# (in production the object should always exist, but in testing it
	# needs to be created)
	trigger_type, is_new = TriggerType.objects.get_or_create(
		key = "congress_sponsors_%s" % chamber,
		title = { 's': 'Senate', 'h': 'House', 'x': 'Congressional' }[chamber] + ' Sponsors/Cosponsors',
		defaults = {
		"strings": {
			"actor": { 's': 'senator', 'h': 'representative', 'x': 'senator or representative' }[chamber],
			"actors": { 's': 'senators', 'h': 'representatives', 'x': 'senators and representatives' }[chamber],
			"action_noun": "bill",
			"action_vb_inf": "sponsor",
			"action_vb_past": "sponsored",
			"action_vb_pres_s": "sponsors",
			"prospective_vp": None,
			"retrospective_vp": None,
		},
		"extra": {
			# There is only one Action outcome for these sorts of Triggrs.
			# Either a Member of Congress sponsors/cosponsors the bill or
			# they took no action on it.
			"monovalent": True,

			# This is not used since these Triggers are always immediately executed
			# and then the actual split is known. But for completeness we'll include
			# the info. House delegates can cosponsor bills, so 441 for the House
			# rather than the usual 435.
			"max_split":  { 's': 100, 'h': 441, 'x': 541 }[chamber],
		}
		})
	return trigger_type

def create_trigger_for_sponsors(bill_id, update=True, with_companion=False):
	# Gets or creates a Trigger that is immediately executed according to
	# the sponsor and cosponsors of a federal bill. If the Trigger already
	# exists, the Actions are updated according to the latest (co)sponsor
	# information.
	#
	# bill_id is a congress-project-style bill ID like hr1024-114.
	#
	# If with_companion is True and the bill has a companion bill in the
	# other chamber, then creates a Trigger for this bill, for the companion,
	# and a super-trigger that combines them both.

	if with_companion:
		return create_trigger_for_sponsors_with_companion_bill(bill_id, update=update)

	import re
	from .models import TriggerExecution, TriggerStatus

	# Validate that this is a valid-looking bill ID.
	m = re.match("^([a-z]+)(\d+)-(\d+)$", bill_id)
	if not m: raise ValueError("'%s' is not a bill ID, e.g. hr1234-114." % bill_id)
	govtrack_api_url = 'https://www.govtrack.us/congress/bills/%s/%s%s.json' \
		% (m.group(3), m.group(1), m.group(2))
	chamber = bill_id[0] # chamber 'h' or 's' is first character

	existing_trigger = Trigger.objects.filter(key="usbill:sponsors:" + bill_id).first()
	if not existing_trigger:
		# We don't have a Trigger for it yet.
		#
		# Get bill metadata from GovTrack's API, via the undocumented
		# '.json' extension added to bill pages -- so that we don't have
		# to query the API to get a numeric bill ID first.
		bill = query_json_api(govtrack_api_url)

		# Validate that we can create a new Trigger for this bill.
		# Guard against an attack that generates Triggers for the ~200,000
		# bills on GovTrack.
		if bill['congress'] < 114:
			raise ValueError("Bills before the 114th are blocked.")

		# Create the trigger.
		t = Trigger()
		t.owner = None
		t.key = "usbill:sponsors:" + bill_id
		t.trigger_type = get_trigger_type_for_sponsors(chamber)
		t.outcomes = [] # set below
		t.extra = { }
		t.save()

	else:
		# Update an existing trigger.
		t = existing_trigger
		if not update and t.status == TriggerStatus.Executed:
			return t

		# If the caller wants us to update the information, then
		# fetch bill metadata from the API.
		bill = query_json_api(govtrack_api_url)

	# Execute the trigger. (Paused could mean there is or isn't a TriggerExecution.)
	if not TriggerExecution.objects.filter(trigger=t).exists():
		t.execute_empty()

	# Update metadata.
	t.title = "Sponsors of " + bill["title"][0:200]

	# This is a monovalent trigger type --- the only outcome that Actors can take
	# is the first one. But users can choose either side.
	t.outcomes = [
		{ "label": "Support %s" % bill["display_number"],
		  "object": bill["display_number"],
		},
		{ "label": "Oppose %s" % bill["display_number"],
		  "object": None, # only the first outcome's 'object' should ever be used in a monovalent trigger
		},
	]

	t.extra.update({
		"type": "sponsors",
		"bill_id": bill_id,
		"govtrack_bill_id": bill["id"],
		"bill_info": bill,
	})

	# Get a current list of the bill's sponsor and cosponsors, with the date
	# each joined.

	# Start with the sponsor.
	sponsors = []
	if bill.get("sponsor"):
		# Not all bills have a sponsor.
		sponsors.append({
			"id": bill['sponsor']['id'],
			"joined": parse_uscapitol_local_time(bill['introduced_date']),
			"withdrawn": None,
			"is_primary_sponsor": True,
		})

	# Add cosponsors.
	cosponsors = query_json_api('https://www.govtrack.us/api/v2/cosponsorship?bill=%d'
		% bill['id'])['objects']
	for cosponsor in cosponsors:
		sponsors.append({
			"id": cosponsor['person'],
			"joined": parse_uscapitol_local_time(cosponsor['joined']),
			"withdrawn": parse_uscapitol_local_time(cosponsor['withdrawn']) if cosponsor['withdrawn'] else None,
		})


	# Update the TriggerExecution's Actions.
	from .models import Action
	execution = t.execution
	seen_actions = set()
	for record in sponsors:
		# Convert GovTrack ID to Actor object.
		try:
			actor = Actor.objects.get(govtrack_id=record['id'])
		except Actor.DoesNotExist:
			# Slilently skip person if we aren't yet in sync with Actors for all
			# possible (co)sponsors.
			continue

		# There are a few reasons why an Action would be marked as not having an outcome.
		if actor.inactive_reason:
			# The Actor is not currently a candidate for office.
			reason_for_no_outcome = actor.inactive_reason
		elif record['withdrawn']:
			# The cosponsor withdrew.
			reason_for_no_outcome = "Cosponsorship withdrawn on " + record["withdrawn"].strftime("%x") + "."
		else:
			# All good.
			reason_for_no_outcome = None

		# Update Actions.
		action = Action.objects.filter(execution=execution, actor=actor).first()
		if not action:
			# Create an Action. It's always outcome zero. If the cosponsor is already
			# withdrawn or isn't running for re-election, then they get that reason
			# which replaces the outcome integer index.
			if not reason_for_no_outcome:
				action = Action.create(execution, actor, 0, record['joined'])
			else:
				action = Action.create(execution, actor, reason_for_no_outcome, record['withdrawn'])
		else:
			# Update an existing action.
			if not reason_for_no_outcome:
				action.outcome = 0
				action.reason_for_no_outcome = None
			else:
				action.outcome = None
				action.reason_for_no_outcome = reason_for_no_outcome
			action.save()

		if not action.extra: action.extra = { }
		if record.get('is_primary_sponsor'):
			action.extra['usbill:sponsors:sponsor_type'] = "primary"
		elif record['joined'] == parse_uscapitol_local_time(bill['introduced_date']):
			action.extra['usbill:sponsors:sponsor_type'] = "original-cosponsor"
		else:
			action.extra['usbill:sponsors:sponsor_type'] = "joined-cosponsor"
		action.save(update_fields=['extra'])

		seen_actions.add(action.id)

	# If any cosponsorship records disappeared from the GovTrack API, typically
	# from incorrect upstream data from Congress, mark those Actions as no longer
	# active. Skip outcome=None Actions because we may have already marked them
	# as obsoleted.
	for obsolete_action in \
		Action.objects.filter(execution=execution)\
		.exclude(id__in=seen_actions)\
		.exclude(outcome=None):
		obsolete_action.outcome = None
		obsolete_action.reason_for_no_outcome = "Cosponsorship record was removed on %s due to erroneous information reported by Congress." \
			% now().strftime("%s")
		obsolete_action.save()

	# Update the metadata.

	# Since the trigger is executed, the description isn't used like it normally is.
	# Instead, itfsite.views.create_automatic_campaign_from_trigger uses it to
	# populate the campaign body.
	body_a, body_b = build_sponsor_trigger_action_list(execution, bill)
	t.description = "<p>Make a campaign contribution to the sponsors of %s if you support the %s or to their opponents if you oppose it.</p>" % (bill["title"], bill["noun"])
	t.description += "<p>The sponsors are:</p>"
	t.description += body_b
	t.description_format = TextFormat.HTML
	t.extra['auto-campaign-headline'] = bill['title']
	t.extra['auto-campaign-subhead'] = "Support or oppose the sponsors of %s." % bill['display_number']
	t.save()

	execution.description = "<p>Contribution are being distributed to " + body_a + ".</p>"
	execution.description_format = TextFormat.HTML
	execution.save()

	# Update the Trigger's status -- pause it if there are no sponsors.
	t.status = TriggerStatus.Executed if (execution.actions.exclude(outcome=None).count() > 0) \
	   else TriggerStatus.Paused
	t.save()

	return t

def build_sponsor_trigger_action_list(trigger_execution, bill):
	from html import escape

	ret1 = "the %d sponsors of <a href='%s'>%s</a> or their opponents" % (
		trigger_execution.actions.filter(outcome=0).count(), bill["link"], bill["display_number"])
	
	ret = "<ul>\n"
	for action in trigger_execution.actions.filter(outcome=0).order_by('action_time', 'name_sort'):
		info = ""
		if action.extra['usbill:sponsors:sponsor_type'] == "primary":
			info = "primary sponsor"
		elif action.extra['usbill:sponsors:sponsor_type'] == "joined-cosponsor":
			info = "joined " + escape(action.action_time.strftime("%x"))
		ret += "<li>%s%s</li>\n" % (
			escape(action.name_long),
			(" (" + escape(info) + ")") if info else ""
		)

	excluded_cosponsors = trigger_execution.actions.filter(outcome=None).order_by('action_time', 'name_sort')
	if excluded_cosponsors.count():
		ret += "<p>Sponsors who cannot receive campaign contributions: %s</p>\n" % "; ".join(
			escape(action.name_long + " (" + action.reason_for_no_outcome + ")")
			for action in excluded_cosponsors)

	ret += "</ul>\n"

	return ret1, ret
		

def create_trigger_for_sponsors_with_companion_bill(bill_id, update=True):
	# Get the trigger for the particular bill.
	t1 = create_trigger_for_sponsors(bill_id, update=update)

	# If the bill has any identical related bills, form a new Trigger,
	# that is empty-executed, which merely lists the triggers of the
	# two bills as sub-triggers.
	companion_bill = None
	for rb in t1.extra['bill_info'].get("related_bills", []):
		if rb['relation'] == "identical":
			companion_bill = rb['bill']

	if not companion_bill:
		# There is no companion bill. Just return this bill's trigger.
		return t1

	# Get a bill_id for the companion bill. Not so great code here.
	b = query_json_api('https://www.govtrack.us/api/v2/bill/%d' % companion_bill)
	bill_id2 = b['bill_type_label'].replace(".", "").lower() + str(b['number']) + '-' + str(b['congress'])

	# Get a trigger for it.
	t2 = create_trigger_for_sponsors(bill_id2, update=update)

	# Form a key for the super-trigger.
	key = "usbill:sponsors-with-companion:" + bill_id

	# If either bill's trigger already identify a super-trigger, then we'll return that.
	# The key of the super-trigger is based on the ID of just one of the two bills, so
	# we have to check both.
	if t1.extra and t1.extra.get("supertrigger-with-companion"):
		tt = Trigger.objects.get(id=t1.extra.get("supertrigger-with-companion"))
	elif t2.extra and t2.extra.get("supertrigger-with-companion"):
		tt = Trigger.objects.get(id=t2.extra.get("supertrigger-with-companion"))

	elif Trigger.objects.filter(key=key).exists():
		# We seem to have already created it, even though the triggers don't
		# know about it.
		tt =Trigger.objects.filter(key=key).first()

	# Create a super-trigger. It lists t1 and t2 as subtriggers.
	# It maps outcomes 0 and 1 of the supertrigger to the same
	# outcomes as the subtrigger.
	else:
		tt = Trigger()
		tt.owner = None
		tt.key = key
		tt.trigger_type = get_trigger_type_for_sponsors("x")
		tt.outcomes = [] # set below
		tt.extra = {
			"subtriggers": [
				{
					"trigger": t1.id,
					"outcome-map": [0, 1], # for (super-trigger, sub-trigger) in enumerate(outcome-map)
				},
				{
					"trigger": t2.id,
					"outcome-map": [0, 1], # for (super-trigger, sub-trigger) in enumerate(outcome-map)
				}
			]
		}
		tt.save()

	# Update the Trigger's metadata. Get the bill metadata for the two triggers.
	# Get the bills in a stable order so that it doesn't change depending on which
	# of the two bills this function was called on.
	triggers = sorted((t1, t2), key=lambda t : t.id)
	bills = [t.extra['bill_info'] for t in triggers]
	
	tt.outcomes = [
		{ "label": "Support the %s" % bills[0]['noun'],
		  "object": "/".join(b["display_number"] for b in bills),
		},
		{ "label": "Oppose the %s" % bills[0]['noun'],
		  "object": None, # only the first outcome's 'object' should ever be used in a monovalent trigger
		},
	]
	
	tt.title = "Sponsors of " + bills[0]['title_without_number']

	# Since the trigger is executed, the description isn't used like it normally is.
	# Instead, itfsite.views.create_automatic_campaign_from_trigger uses it to
	# populate the campaign body.
	body_texts = [build_sponsor_trigger_action_list(t.execution, t.extra["bill_info"]) for t in triggers]
	tt.description = "<p>Make a campaign contribution to the sponsors and cosponsors of %s if you support the %s or to their opponents if you oppose it.</p>" % (
		"/".join(("<a href='%s'>%s</a>" % (b["link"], b["display_number"])) for b in bills),
		bills[0]["noun"])
	tt.description += "<p>The sponsors are:</p>"
	tt.description += "\n".join(r[1] for r in body_texts)
	tt.description_format = TextFormat.HTML
	tt.extra['auto-campaign-headline'] = bills[0]['title_without_number']
	tt.extra['auto-campaign-subhead'] = "Support or oppose the sponsors of %s." % "/".join(b['display_number'] for b in bills)
	tt.save(update_fields=['outcomes', 'title', 'description', 'description_format', 'extra'])

	# Ensure the super-trigger is executed.
	from .models import TriggerExecution, TriggerStatus
	if not TriggerExecution.objects.filter(trigger=tt).exists():
		tt.execute_empty()
		tt = Trigger.objects.get(id=tt.id) # reload
	assert tt.status == TriggerStatus.Executed

	# Update the execution.
	execution = tt.execution
	execution.description = "<p>Contribution are being distributed to " \
	 + " and ".join(r[0] for r in body_texts) \
	 + "</p>"
	execution.description_format = TextFormat.HTML
	execution.save()

	# Store the super-trigger ID on the two bill triggers so that the
	# next time around we know we've already created the super-trigger.
	for t in (t1, t2):
		t.extra["supertrigger-with-companion"] = tt.id
		t.save(update_fields=['extra'])

	# Return it.
	return tt


def geocode(address):
	# Geocodes an address using the CDYNE Postal Address Verification API.
	# address should be a tuple of of the street, city, state and zip code.

	import requests, urllib.parse, json
	from django.conf import settings

		# http version: "http://pav3.cdyne.com/PavService.svc/VerifyAddressAdvanced"
	r = requests.post("https://pav3.cdyne.com/PavService.svc/rest_s/VerifyAddressAdvanced",
		data=json.dumps({
			"PrimaryAddressLine": address[0],
			"CityName": address[1],
			"State": address[2],
			"ZipCode": address[3],
			"LicenseKey": settings.CDYNE_API_KEY,
			"ReturnCensusInfo": True,
			"ReturnGeoLocation": True,
			"ReturnLegislativeInfo": True,
		}),
		headers={ "Content-Type": "application/json", "Accept": "application/json" }
		)

	# Raise an exception for non-200 OK responses.
	r.raise_for_status()

	# Parse XML.
	r = r.json()
	retcode = int(r["ReturnCode"])
	if retcode in (1, 2):
		raise Exception("CDYNE returned error code %d. See http://wiki.cdyne.com/index.php/PAV_VerifyAddressAdvanced_Output." % retcode)

	ret = {
		'timestamp': now().isoformat(), # Add a timestamp to the response in case we need to know later when we performed the geocode.
		'cdyne': r,
	}	

	if retcode in (10,):
		# Input Address is Not Found.
		return ret

	# Store the congressional district as of the 114th Congress as XX##.
	ret["cd114"] = r['StateAbbreviation'] + r['LegislativeInfo']['CongressionalDistrictNumber']

	# Store the user's time zone. Convert from the CDYNE time zone
	# code to a standard Unix time zone name.
	# http://wiki.cdyne.com/index.php/Postal_Address_Verification
	tz = r['GeoLocationInfo']['TimeZone'].strip()
	tz = {
			"EST": "US/Eastern", # aka America/New_York
			"CST": "US/Central", # aka America/Chicago
			"MST": "US/Mountain", # aka America/Denver
			"PST": "US/Pacific", # aka America/Los_Angeles
			"PST-1": "US/Alaska", # aka America/Anchorage
			"PST-2": "US/Hawaii", # aka Pacific/Honolulu
			"EST+1": "America/Puerto_Rico",
		}.get(tz)
	if tz:
		ret['tz'] = tz

	return ret
