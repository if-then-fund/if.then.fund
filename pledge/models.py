import enum

from django.db import models
from django.contrib.auth.models import User

from jsonfield import JSONField
from enum3field import EnumField, django_enum

@django_enum
class TriggerState(enum.Enum):
	Draft = 0
	Open = 1
	Paused = 2
	Executed = 3
	Vacated = 4

@django_enum
class TextFormat(enum.Enum):
	HTML = 0
	Markdown = 1

class Trigger(models.Model):
	"""A future event that triggers a camapaign contribution, such as a roll call vote in Congress."""

	key = models.CharField(max_length=64, blank=True, null=True, db_index=True, unique=True, help_text="An opaque look-up key to quickly locate this object.")

	title = models.CharField(max_length=200, help_text="The title for the trigger.")
	owner = models.ForeignKey(User, on_delete=models.PROTECT, help_text="The user which created the trigger and can update it.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	slug = models.SlugField(max_length=200, help_text="The URL slug for this trigger.")
	description = models.TextField(help_text="Description text in Markdown.")
	description_format = EnumField(TextFormat, help_text="The format of the description text.")
	state = EnumField(TriggerState, default=TriggerState.Draft, help_text="The current status of the trigger: Open (accepting pledges), Paused (not accepting pledges), Executed (funds distributed), Vacated (existing pledges invalidated).")
	outcomes = JSONField(default=[], help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].")

	strings = JSONField(default={}, help_text="Display strings.")
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	total_pledged = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="A cached total amount of pledges, i.e. prior to execution.")
	total_contributions = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="A cached total amount of campaign contributions executed (including pending contributions, but not vacated or aborted contributions).")

	def get_absolute_url(self):
		return "/a/%d/%s" % (self.id, self.slug)

	### constructor

	@staticmethod
	def new_from_bill(bill_id, chamber):
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
		from pledge.utils import query_json_api
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

		from django.contrib.auth.models import User
		t.owner = User.objects.get(username='admin')

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
			"type": "usbill",
			"bill_id": bill_id,
			"chamber": chamber,
			"govtrack_bill_id": bill["id"],
			"bill_info": bill,
		}

		# save and return
		t.save()
		return t


class TriggerStatusUpdate(models.Model):
	"""A status update about the Trigger providing further information to users looking at the Trigger that was not known when the Trigger was created."""

	trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, help_text="The Trigger that this update is about.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)
	text = models.TextField(help_text="Status update text in Markdown.")
	text_format = EnumField(TextFormat, help_text="The format of the text.")

class TriggerExecution(models.Model):
	"""How a Trigger was executed."""

	trigger = models.OneToOneField(Trigger, on_delete=models.PROTECT, help_text="The Trigger this execution information is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	cycle = models.IntegerField(help_text="The election cycle (year) that the trigger was executed in.")

	description = models.TextField(help_text="Once a trigger is executed, additional text added to explain how funds were distributed.")
	description_format = EnumField(TextFormat, help_text="The format of the description text.")

class Actor(models.Model):
	"""A public figure, e.g. elected official with an active election campaign, who might take an action."""

	key = models.CharField(max_length=64, db_index=True, unique=True, help_text="An opaque look-up key to quickly locate this object.")
	name_long = models.CharField(max_length=128, help_text="The long form of the person's current name, meant for a page title.")
	name_short = models.CharField(max_length=128, help_text="The short form of the person's current name, usually a last name, meant for in-page second references.")
	name_sort = models.CharField(max_length=128, help_text="The sorted list form of the person's current name.")
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

class Action(models.Model):
	"""The outcome of an actor taking an act described by a trigger."""

	execution = models.ForeignKey(TriggerExecution, on_delete=models.PROTECT, help_text="The TriggerExecution that created this object.")
	actor = models.ForeignKey(Actor, on_delete=models.PROTECT, help_text="The Actor who took this action.")
	outcome = models.IntegerField(help_text="The outcome index that was taken.")

	class Meta:
		unique_together = [('execution', 'actor')]

class Pledge(models.Model):
	"""A user's pledge of a contribution."""

	user = models.ForeignKey(User, on_delete=models.PROTECT, help_text="The user making the pledge.")
	trigger = models.ForeignKey(Trigger, on_delete=models.PROTECT, help_text="The Trigger that this update is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)
	algorithm = models.IntegerField(default=0, help_text="In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.")

	desired_outcome = models.IntegerField(help_text="The outcome index that the user desires.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The pledge amount in dollars, not including fees.")
	incumb_challgr = models.FloatField(help_text="A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)")
	filter_party = models.CharField(max_length=3, blank=True, help_text="A string containing one or more of the characters 'D' 'R' and 'I' that filters contributions to only candidates whose party matches on of the included characters.")
	filter_competitive = models.BooleanField(default=False, help_text="Whether to filter contributions to competitive races.")

	cancelled = models.BooleanField(default=False, help_text="True if the user cancels the pledge prior to execution.")
	vacated = models.BooleanField(default=False, help_text="True if the Trigger is vacated.")

	district = models.CharField(max_length=64, blank=True, null=True, db_index=True, help_text="The congressional district of the user (at the time of the pledge), if their address is in a congressional district.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	class Meta:
		unique_together = [('trigger', 'user')]

class PledgeExecution(models.Model):
	"""How a user's pledge was executed. Each pledge has a single PledgeExecution when the Trigger is executed, and immediately many Contribution objects are created."""

	pledge = models.OneToOneField(Pledge, on_delete=models.PROTECT, help_text="The Pledge this execution information is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)

	charged = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount the user's account was actually charged, in dollars. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates, and it will include fees.")
	fees = JSONField(help_text="A dictionary representing all fees on the charge.")
	contributions_executed = models.DecimalField(max_digits=6, decimal_places=2, help_text="The total amount of executed camapaign contributions to-date.")
	contributions_pending = models.DecimalField(max_digits=6, decimal_places=2, help_text="The current total amount of pending camapaign contributions.")

class Campaign(models.Model):
	"""A candidate in a particular election cycle."""

	cycle = models.IntegerField(help_text="The election cycle (year) of the campaign.")
	actor = models.ForeignKey(Actor, blank=True, null=True, help_text="If the candidate of this campaign is an Actor, then the Actor.")
	candidate = models.IntegerField(blank=True, null=True, db_index=True, help_text="For candidates that are not also Actors, a unique identifier for the candidate that spans Campaign objects (which are cycle-specific).")

	name_long = models.CharField(max_length=128, help_text="The long form of the candidates's name during this campaign, meant for a page title.")
	name_short = models.CharField(max_length=128, help_text="The short form of the candidates's name during this campaign, usually a last name, meant for in-page second references.")
	name_sort = models.CharField(max_length=128, help_text="The sorted list form of the candidates's name during this campaign.")
	party = models.CharField(max_length=128, help_text="Candidate's party during this campaign.")

	fec_id = models.CharField(max_length=64, blank=True, null=True, help_text="The FEC ID of the campaign.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

@django_enum
class ContributionStatus(enum.Enum):
	Pending = 1 # contribution is pending (e.g. not processed yet, opponent not known)
	Executed = 2 # contribution was executed
	Vacated = 3 # contribution could not be made, we retain funds
	AbortedActorQuit = 10 # actor is no longer running for office
	AbortedOverLimitTarget = 11 # user is over their contribution limit to the target candidate
	AbortedOverLimitAll = 12 # user is over their contribution limit to all candidates
	AbortedUnopposed = 13 # we know at the time of executing the pledge that the actor has no opponent

class Contribution(models.Model):
	"""A campaign contribution (possibly pending, aborted, etc.)."""

	pledge_execution = models.ForeignKey(PledgeExecution, on_delete=models.PROTECT, help_text="The PledgeExecution this execution information is about.")
	action = models.ForeignKey(Action, on_delete=models.PROTECT, help_text="The Action (including Actor) this contribution was triggered for.")

	status = EnumField(ContributionStatus, help_text="The status of the contribution: Pending (opponent not known), Executed, Vacated (no opponent exists)")
	execution_time = models.DateTimeField(blank=True, null=True, db_index=True)
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount of the contribution, in dollars.")

	is_opponent = models.BooleanField(default=False, help_text="Is the target the actor (False) or the general election opponent of the actor (True)?")
	recipient = models.ForeignKey(Campaign, on_delete=models.PROTECT, help_text="The Campaign this contribution was sent to.")

	refunded_time = models.DateTimeField(blank=True, null=True, help_text="If the contribution was refunded to the user, the time that happened.")

	extra = JSONField(blank=True, help_text="Additional information about the contribution.")

	class Meta:
		unique_together = [('pledge_execution', 'action')]
