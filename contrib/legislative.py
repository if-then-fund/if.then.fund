from contrib.models import Trigger, TextFormat, TriggerType, Actor
from django.conf import settings

ALLOW_DEAD_BILL = False

class TriggerAlreadyExistsException(Exception):
	pass

def get_trigger_type(chamber):
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
		},
		"extra": {
			"max_split":  { 's': 100, 'h': 435, 'x': 435 }[chamber],
		}
		})
	return trigger_type

def create_congressional_vote_trigger(chamber, title, short_title):
	t = Trigger()

	t.owner = None
	
	t.trigger_type = get_trigger_type(chamber)
	
	t.title = title[0:200]

	chamber_name = { 's': 'Senate', 'h': 'House', 'x': 'Congress' }[chamber]
	t.description = "The %s will soon vote on %s." % (chamber_name, short_title)
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
	from contrib.utils import query_json_api
	bill_search = query_json_api("https://www.govtrack.us/api/v2/bill", {
		"bill_type": bill_type, "number": bill_number, "congress": bill_congress })
	if len(bill_search['objects']) == 0: raise ValueError("Not a bill.")
	if len(bill_search['objects']) > 1: raise ValueError("Matched multiple bills?")

	bill = bill_search['objects'][0]
	if not bill['is_alive'] and not ALLOW_DEAD_BILL: raise ValueError("Bill is not alive.")

	# we're going to cache the bill info, so add a timestamp for the retreival date
	import datetime
	bill['as_of'] = datetime.datetime.now().isoformat()

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
	import requests, lxml.etree

	outcome_index = map_outcome_indexes(trigger, flip)

	# Get vote metadata from GovTrack's API, via the undocumented
	# '.json' extension added to vote pages.
	vote = requests.get(govtrack_url+'.json').json()

	# Sanity check that the chamber of the vote matches the trigger type.
	if trigger.trigger_type.key not in ('congress_floorvote_x', 'congress_floorvote_both', 'congress_floorvote_' + vote['chamber'][0], 'announced-positions'):
		raise Exception("The trigger type doesn't match the chamber the vote ocurred in.")

	# Parse the date, which is in US Eastern time. Must make it
	# timezone-aware to store in our database.
	from django.utils.timezone import make_aware
	import dateutil.parser, dateutil.tz
	when = dateutil.parser.parse(vote['created'])
	z = dateutil.tz.tzfile('/usr/share/zoneinfo/EST5EDT')
	when = make_aware(when, z)

	# Then get how Members of Congress voted via the XML, which conveniently
	# includes everything without limit/offset. The congress project vote
	# JSON doesn't use GovTrack IDs, so it's more convenient to use GovTrack
	# data.
	r = requests.get(govtrack_url+'/export/xml').content
	dom = lxml.etree.fromstring(r)
	actor_outcomes = { }
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

		actor_outcomes[actor] = outcome

	return (vote, when, actor_outcomes)

def execute_trigger_from_votes(trigger, votes):
	if len(votes) == 0: raise ValueError("votes")

	# Load all of the vote details from GovTrack.
	votes = list(map(
		lambda vote_dict :
			# (vote, when, actor_outcomes)
			load_govtrack_vote(trigger, vote_dict["url"], flip=vote_dict.get("flip", False)),
		votes))

	# Make a textual description of what happened.
	if len(votes) == 1:
		description = """The {chamber} voted on this on {date}. For more details, see the [vote record on GovTrack.us]({link}).
		""".format(
			chamber=votes[0][0]['chamber_label'],
			date=votes[0][1].strftime("%b. %d, %Y").replace(" 0", ""),
			link=votes[0][0]['link'],
		)
	else:
		description = "See " + "; ".join(
			"the [{chamber} vote on {date} at GovTrack.us]({link})".format(
				chamber=vote['chamber_label'],
				date=when.strftime("%b. %d, %Y").replace(" 0", ""),
				link=vote['link'],
			)
			for vote, when, actor_outcomes in votes) \
			+ "."

	# Merge the actor_outcomes of the votes. Check that an actor doesn't appear
	# in multiple votes.
	actor_outcomes = { }
	for vote, when, ao in votes:
		for actor, outcome in ao.items():
			if actor in actor_outcomes:
				raise ValueError("Actor %s is present in multiple votes." % str(actor))
			actor_outcomes[actor] = outcome

	# Execute.
	trigger.execute(
		min(when for vote, when, actor_outcomes in votes), # earliest vote date => Trigger.action_time
		actor_outcomes,
		description,
		TextFormat.Markdown,
		{
			"govtrack_votes": [vote for vote, when, actor_outcomes in votes],
		})

def load_govtrack_sponsors(trigger, govtrack_url, flip=False):
	import requests, lxml.etree

	outcome_index = map_outcome_indexes(trigger, flip)

	# Get bill metadata from GovTrack's API, via the undocumented
	# '.json' extension added to bill pages.
	bill = requests.get(govtrack_url+'.json').json()

	actor_outcomes = { }
	for person in [bill.get('sponsor')] + bill.get('cosponsors', []):
		if person is None: continue # empty sponsor
		try:
			actor = Actor.objects.get(govtrack_id=person.get('id'))
		except Actor.DoesNotExist:
			# See corresponding block for votes.
			raise Exception("No Actor instance exists here for Member of Congress with GovTrack ID %d." % int(person.get('id')))

		# Sponsors and cosponsors are all "pro".
		outcome = outcome_index.get("+")
		actor_outcomes[actor] = outcome

	return (bill, actor_outcomes)

def geocode(address):
	# Geocodes an address using the CDYNE Postal Address Verification API.
	# address should be a tuple of of the street, city, state and zip code.

	import requests, urllib.parse, lxml.etree, json
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

	from django.utils.timezone import now
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
