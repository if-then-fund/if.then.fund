from contrib.models import Trigger, TextFormat

def create_trigger_from_bill(bill_id, chamber):
	# split/validate the bill ID
	import re
	m = re.match("^([a-z]+)(\d+)-(\d+)$", bill_id)
	if not m: raise ValueError("Not a bill ID, e.g. hr1234-114.")
	bill_type, bill_number, bill_congress = m.groups()
	bill_type = { "hres": "house_resolution", "s": "senate_bill", "sjres": "senate_joint_resolution", "hr": "house_bill", "hconres": "house_concurrent_resolution", "sconres": "senate_concurrent_resolution", "hjres": "house_joint_resolution", "sres": "senate_resolution" }.get(bill_type)
	if not bill_type: raise ValueError("Not a bill ID, e.g. hr1234-114.")

	# validate chamber
	if chamber not in ('s', 'h'): raise ValueError("Chamber must be one of 'h' or 's'.")
	chamber_name = { 's': 'Senate', 'h': 'House' }[chamber]
	chamber_actors = { 's': 'senators', 'h': 'representatives' }[chamber]

	# get bill data from GovTrack
	from contrib.utils import query_json_api
	bill_search = query_json_api("https://www.govtrack.us/api/v2/bill", {
		"bill_type": bill_type, "number": bill_number, "congress": bill_congress })
	if len(bill_search['objects']) == 0: raise ValueError("Not a bill.")
	if len(bill_search['objects']) > 1: raise ValueError("Matched multiple bills?")

	bill = bill_search['objects'][0]
	if not bill['is_alive']: raise ValueError("Bill is not alive.")

	# we're going to cache the bill info, so add a timestamp for the retreival date
	import datetime
	bill['as_of'] = datetime.datetime.now().isoformat()

	# create object
	t = Trigger()
	t.key = "usbill:" + bill_id + ":" + chamber
	t.title = chamber_name + " Vote on " + bill['title']
	t.owner = None

	from django.template.defaultfilters import slugify
	t.slug = slugify(t.title)

	t.description = "The %s will soon vote on %s." % (chamber_name, bill["title"])
	t.description_format = TextFormat.Markdown

	short_title = bill["display_number"]
	t.outcomes = [
		{ "vote_key": "+", "label": "Yes on %s" % short_title },
		{ "vote_key": "-", "label": "No on %s" % short_title },
	]
	t.strings = {
		"actors": chamber_actors,
		"action": "vote",
	}

	t.extra = {
		"max_split":  { 's': 100, 'h': 435 }[chamber],
		"type": "usbill",
		"bill_id": bill_id,
		"chamber": chamber,
		"govtrack_bill_id": bill["id"],
		"bill_info": bill,
	}

	# save and return
	t.save()
	return t