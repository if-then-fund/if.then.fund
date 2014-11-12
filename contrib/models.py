import enum

from django.db import models, transaction, IntegrityError
from itfsite.models import User

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
	owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.PROTECT, help_text="The user which created the trigger and can update it.")

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

	def __str__(self):
		return "[%d %s] %s" % (self.id, self.key, self.title)

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

	total_contributions = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="A cached total amount of campaign contributions executed.")

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

@django_enum
class PledgeStatus(enum.Enum):
	Open = 1
	Executed = 2
	Cancelled = 3 # user canceled prior to pledge execution
	Vacated = 4 # trigger was vacated

class Pledge(models.Model):
	"""A user's pledge of a contribution."""

	user = models.ForeignKey(User, blank=True, null=True, on_delete=models.PROTECT, help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored, and the pledge should be considered unconfirmed/provisional and will not be executed.")
	email = models.EmailField(max_length=254, blank=True, null=True, help_text="When an anonymous user makes a pledge, their email address is stored here and we send a confirmation email.")
	trigger = models.ForeignKey(Trigger, on_delete=models.PROTECT, help_text="The Trigger that this update is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)
	algorithm = models.IntegerField(default=0, help_text="In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.")
	status = EnumField(PledgeStatus, default=PledgeStatus.Open, help_text="The current status of the pledge.")

	desired_outcome = models.IntegerField(help_text="The outcome index that the user desires.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The pledge amount in dollars (including fees). The credit card charge may be less in the event that we have to round to the nearest penny-donation.")
	incumb_challgr = models.FloatField(help_text="A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)")
	filter_party = models.CharField(max_length=3, help_text="A string containing one or more of the characters 'D' 'R' and 'I' that filters contributions to only candidates whose party matches on of the included characters.")
	filter_competitive = models.BooleanField(default=False, help_text="Whether to filter contributions to competitive races.")

	district = models.CharField(max_length=64, blank=True, null=True, db_index=True, help_text="The congressional district of the user (at the time of the pledge), if their address is in a congressional district.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	class Meta:
		unique_together = [('trigger', 'user')]

	@staticmethod
	def current_algorithm():
		return {
			"id": 1, # a sequence number so we can track changes to our fee structure, etc.
			"min_contrib": 1, # dollars
			"max_contrib": 500, # dollars
		}

	def __str__(self):
		return self.get_email() + " => " + str(self.trigger)

	def get_absolute_url(self):
		return "/contrib/%d" % self.id

	def get_email(self):
		if self.user:
			return self.user.email
		else:
			return self.email

	@property
	def desired_outcome_label(self):
		return self.trigger.outcomes[self.desired_outcome]["label"]

	@property
	def targets_summary(self):
		def ucfirst(s):
			return s[0].upper() + s[1:]

		party_filter = ""
		if len(self.filter_party) < 3:
			party_map = { "R": "Republican", "D": "Democratic", "I": "3rd Party" }
			party_filter = \
				" or ".join(party_map[p] for p in self.filter_party) \
				+ " "

		actors = self.trigger.strings['actors']
		if party_filter == "":
			actors = ucfirst(actors)

		if self.incumb_challgr == -1:
			actors = "challengers of " + actors
		elif self.incumb_challgr == 0:
			actors += " and challengers"

		return party_filter + actors

	def send_email_verification(self):
		# Tries to confirm an anonymous-user-created pledge. Might
		# raise an IOError if the email could not be sent, which leaves
		# the EmailConfirmation object created but with send_at null.
		from email_confirm_la.models import EmailConfirmation
		ec = EmailConfirmation.objects.set_email_for_object(
			email=self.email,
			content_object=self,
		)
		if not ec.send_at:
			# EmailConfirmation object exists but sending failed last
			# time, so try again.
			ec.send(None)

	@transaction.atomic
	def confirm_email(self, user):
		# Can't confirm twice, but this might be called twice. In order
		# to prevent a race condition, use select_for_update which locks
		# the row until the transaction ends.
		pledge = Pledge.objects.select_for_update().filter(id=self.id).first()
		if pledge.user: return False

		# Move the anonymous pledge to the user's account.
		pledge.user = user
		pledge.email = None
		pledge.save()

		# Update state now that pledge is confirmed.
		pledge.is_confirmed()
		return True

	def is_confirmed(self):
		# Update the trigger's pledge total atomically.
		Trigger.objects.filter(id=self.trigger.id)\
			.update(total_pledged=models.F('total_pledged') + self.amount)

class PledgeExecution(models.Model):
	"""How a user's pledge was executed. Each pledge has a single PledgeExecution when the Trigger is executed, and immediately many Contribution objects are created."""

	pledge = models.OneToOneField(Pledge, on_delete=models.PROTECT, help_text="The Pledge this execution information is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)

	charged = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount the user's account was actually charged, in dollars and including fees. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates.")
	fees = models.DecimalField(max_digits=6, decimal_places=2, help_text="The fees the user was charged, in dollars.")

class Recipient(models.Model):
	"""A contribution recipient, such as a candidate's campaign committee. Whereas an Actor represents a person who takes an action, a Recipient represents a FEC-recognized entity who can be the recipient of a campaign contribution. A Recipient also exists for any logically-specified challenger. An Actor may be linked with multiple Recipients but has one 'current' recipient."""

	current = models.BooleanField(default=True, help_text="Whether this record is a current Recipient for an Actor.")

	actor = models.ForeignKey(Actor, blank=True, null=True, help_text="The Actor associated with the Recipient. The Recipient may be the Actor's challenger.")
	party = models.CharField(max_length=1, choices=[('R', 'Republican'), ('D', 'Democratic'), ('I', '3rd-Party')], help_text="The party of the Recipient, R/D/I.")
	is_opponent = models.BooleanField(default=False, help_text="If True, the Recipient is a general election challenger of the Actor.")

	cycle = models.IntegerField(help_text="The election cycle (year) of the campaign.")
	name = models.CharField(max_length=255, help_text="The name of the Recipient, typically for internal/debugging use only.")

	de_id = models.CharField(max_length=64, help_text="The Democracy Engine ID that we have assigned to this recipient.")
	fec_id = models.CharField(max_length=64, blank=True, null=True, help_text="The FEC ID of the campaign.")

class Contribution(models.Model):
	"""A fully executed campaign contribution."""

	pledge_execution = models.ForeignKey(PledgeExecution, on_delete=models.PROTECT, help_text="The PledgeExecution this execution information is about.")
	recipient = models.ForeignKey(Recipient, on_delete=models.PROTECT, help_text="The Recipient this contribution was sent to.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount of the contribution, in dollars.")
	refunded_time = models.DateTimeField(blank=True, null=True, help_text="If the contribution was refunded to the user, the time that happened.")

	extra = JSONField(blank=True, help_text="Additional information about the contribution.")

	class Meta:
		unique_together = [('pledge_execution', 'recipient')]
