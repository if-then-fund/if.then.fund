import enum

from django.db import models, transaction, IntegrityError
from itfsite.models import User

from jsonfield import JSONField
from enum3field import EnumField, django_enum

#####################################################################
#
# Triggers
#
# A future event that triggers pledged contributions.
#
#####################################################################

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

#####################################################################
#
# Actors
#
# Elected officials and their official acts.
#
#####################################################################

@django_enum
class ActorParty(enum.Enum):
	Democratic = 1
	Republican = 2
	Independent = 3

class Actor(models.Model):
	"""A public figure, e.g. elected official with an election campaign, who might take an action."""

	govtrack_id = models.IntegerField(unique=True, help_text="GovTrack's ID for this person.")

	name_long = models.CharField(max_length=128, help_text="The long form of the person's current name, meant for a page title.")
	name_short = models.CharField(max_length=128, help_text="The short form of the person's current name, usually a last name, meant for in-page second references.")
	name_sort = models.CharField(max_length=128, help_text="The sorted list form of the person's current name.")
	party = EnumField(ActorParty, help_text="The current party of the Actor. For Members of Congress, this is based on how the Member caucuses to avoid Independent as much as possible.")
	title = models.CharField(max_length=200, help_text="Descriptive text for the office held by this actor.")
	
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def __str__(self):
		return self.name_sort

class Action(models.Model):
	"""The outcome of an actor taking an act described by a trigger."""

	execution = models.ForeignKey(TriggerExecution, on_delete=models.PROTECT, help_text="The TriggerExecution that created this object.")
	actor = models.ForeignKey(Actor, on_delete=models.PROTECT, help_text="The Actor who took this action.")
	outcome = models.IntegerField(help_text="The outcome index that was taken.")

	name_long = models.CharField(max_length=128, help_text="The long form of the person's name at the time of the action, meant for a page title.")
	name_short = models.CharField(max_length=128, help_text="The short form of the person's name at the time of the action, usually a last name, meant for in-page second references.")
	name_sort = models.CharField(max_length=128, help_text="The sorted list form of the person's name at the time of the action.")
	party = EnumField(ActorParty, help_text="The party of the Actor at the time of the action.")
	title = models.CharField(max_length=200, help_text="Descriptive text for the office held by this actor at the time of the action.")
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	class Meta:
		unique_together = [('execution', 'actor')]

#####################################################################
#
# Pledges
#
# A pledged campaign contribution by a user.
#
#####################################################################

@django_enum
class PledgeStatus(enum.Enum):
	Open = 1
	Executed = 2
	Unconfirmed = 3 # pledge was not confirmed before Trigger execution, is no longer valid
	Vacated = 4 # trigger was vacated

class PledgeManager(models.Manager):
	class CustomQuerySet(models.QuerySet):
		def delete(self):
			# Can't do a mass delete because it would not update Trigger.total_pledged.
			# Instead call delete() on each instance, which handles the constraint.
			for obj in self:
				obj.delete()
	def get_queryset(self):
		return PledgeManager.CustomQuerySet(self.model, using=self._db)

class Pledge(models.Model):
	"""A user's pledge of a contribution."""

	user = models.ForeignKey(User, blank=True, null=True, on_delete=models.PROTECT, help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored, and the pledge should be considered unconfirmed/provisional and will not be executed.")
	email = models.EmailField(max_length=254, blank=True, null=True, help_text="When an anonymous user makes a pledge, their email address is stored here and we send a confirmation email.")
	trigger = models.ForeignKey(Trigger, on_delete=models.PROTECT, help_text="The Trigger that this Pledge is for.")

	# When a Pledge is cancelled, the object is deleted. The three fields above
	# are archived, plus the fields listed in this list:
	cancel_archive_fields = ('created', 'updated', 'algorithm', 'desired_outcome', 'amount', 'cclastfour')

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)
	algorithm = models.IntegerField(default=0, help_text="In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.")
	status = EnumField(PledgeStatus, default=PledgeStatus.Open, help_text="The current status of the pledge.")

	desired_outcome = models.IntegerField(help_text="The outcome index that the user desires.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The pledge amount in dollars (including fees). The credit card charge may be less in the event that we have to round to the nearest penny-donation.")
	incumb_challgr = models.FloatField(help_text="A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)")
	filter_party = EnumField(ActorParty, blank=True, null=True, help_text="Contributions only go to candidates whose party matches this party. Independent is not an allowed value here.")
	filter_competitive = models.BooleanField(default=False, help_text="Whether to filter contributions to competitive races.")

	cclastfour = models.CharField(max_length=4, blank=True, null=True, db_index=True, help_text="The last four digits of the user's credit card number, stored for fast look-up in case we need to find a pledge from a credit card number.")
	district = models.CharField(max_length=4, blank=True, null=True, db_index=True, help_text="The congressional district of the user (at the time of the pledge), in the form of XX00.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	class Meta:
		unique_together = [('trigger', 'user'), ('trigger', 'email')]

	objects = PledgeManager()

	@transaction.atomic
	def delete(self):
		if self.status != PledgeStatus.Open:
			raise ValueError("Cannot cancel a Pledge with status %s." % self.status)

		# Decrement the Trigger's total_pledged.
		Trigger.objects.filter(id=self.trigger.id)\
			.update(total_pledged=models.F('total_pledged') - self.amount)

		# Archive as a cancelled pledge.
		cp = CancelledPledge.from_pledge(self)

		# Remove record. Will raise an exception and abort the transaction if
		# the pledge has been executed and a PledgeExecution object refers to this.
		super(Pledge, self).delete()	

	@staticmethod
	def current_algorithm():
		return {
			"id": 1, # a sequence number so we can track changes to our fee structure, etc.
			"min_contrib": 1, # dollars
			"max_contrib": 500, # dollars
		}

	def __str__(self):
		return self.get_email() + " => " + str(self.trigger)

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
		if self.filter_party is not None:
			party_filter = self.filter_party.name + " "

		actors = self.trigger.strings['actors']
		if party_filter == "":
			actors = ucfirst(actors)

		if self.incumb_challgr == -1:
			actors = "challengers of " + actors
		elif self.incumb_challgr == 0:
			actors += " and challengers"

		if self.filter_competitive:
			actors += " in competitive races"

		return party_filter + actors

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

		return True

	@staticmethod
	def find_from_billing(cc_number, cc_exp_month, cc_exp_year, cc_cvc):
		# Returns an interator that yields matchinig Pledge instances.
		# Must be in parallel to how the view function creates the pledge.
		cc_key = ','.join([cc_number, cc_exp_month, cc_exp_year, cc_cvc])
		cc_key = cc_key.replace(' ', '')
		from django.contrib.auth.hashers import check_password
		for p in Pledge.objects.filter(cclastfour=cc_number[-4:]):
			if check_password(cc_key, p.extra['billingInfoHashed']):
				yield p

class CancelledPledge(models.Model):
	"""Records when a user cancels a Pledge."""

	created = models.DateTimeField(auto_now_add=True, db_index=True)

	trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, help_text="The Trigger that the pledge was for.")
	user = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE, help_text="The user who made the pledge, if not anonymous.")
	email = models.EmailField(max_length=254, blank=True, null=True, help_text="The email address of an unconfirmed pledge.")

	pledge = JSONField(blank=True, help_text="The original Pledge information.")

	@staticmethod
	def from_pledge(pledge):
		cp = CancelledPledge()
		cp.trigger = pledge.trigger
		cp.user = pledge.user
		cp.email = pledge.email
		cp.pledge = { k: getattr(pledge, k) for k in Pledge.cancel_archive_fields }
		cp.save()

class PledgeExecution(models.Model):
	"""How a user's pledge was executed. Each pledge has a single PledgeExecution when the Trigger is executed, and immediately many Contribution objects are created."""

	pledge = models.OneToOneField(Pledge, on_delete=models.PROTECT, help_text="The Pledge this execution information is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)

	charged = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount the user's account was actually charged, in dollars and including fees. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates.")
	fees = models.DecimalField(max_digits=6, decimal_places=2, help_text="The fees the user was charged, in dollars.")

#####################################################################
#
# Recipients and Contributions
#
# Actual campaign contributions made.
#
#####################################################################

class Recipient(models.Model):
	"""A contribution recipient, either an Actor or any logically-specified challenger to an Actor, with the current Democracy Engine recipient ID."""

	actor = models.ForeignKey(Actor, blank=True, null=True, help_text="The Actor associated with the Recipient. The Recipient may be the Actor's challenger.")
	challenger = EnumField(ActorParty, blank=True, null=True, help_text="The party of the challenger (R or D, only), or null if this Recipient is for the incumbent.")

	name = models.CharField(max_length=255, help_text="The name of the Recipient, typically for internal/debugging use only.")

	de_id = models.CharField(max_length=64, help_text="The Democracy Engine ID that we have assigned to this recipient.")
	fec_id = models.CharField(max_length=64, blank=True, null=True, help_text="The FEC ID of the campaign.")

	class Meta:
		unique_together = [('actor', 'challenger')]

	def __str__(self):
		return "[%s%s] %s" % (self.actor.name_short, ':' + self.challenger.name if self.challenger else "", self.name)

	@staticmethod
	def create_for(actor):
		# Ensure a recipient exists for the Actor and any potential challengers of a different party.

		# The None party is the Actor (incumbent). Party values represent challengers.
		for party in (None, ActorParty.Democratic, ActorParty.Republican):
			# Don't create a challenger of the same party as the Actor (incumbent).
			if party == actor.party:
				continue

			# Get or create.
			recipient, is_new = Recipient.objects.get_or_create(
				actor=actor,
				challenger=party,
				)

			# Update name.
			old_name = recipient.name
			if not party:
				recipient.name = actor.name_long
			else:
				recipient.name = "General Election %s Challenger to %s" % (party.name, actor.name_long)

			# Update record.
			if  old_name != recipient.name:
				if not is_new:
					print(recipient, '\t', old_name, '=>', recipient.name)
				recipient.save(update_fields=['name'])


	@transaction.atomic
	def create_de_record(self):
		# Creates/updates a Democracy Engine recipient.
		pass


class Contribution(models.Model):
	"""A fully executed campaign contribution."""

	pledge_execution = models.ForeignKey(PledgeExecution, on_delete=models.PROTECT, help_text="The PledgeExecution this execution information is about.")
	action = models.ForeignKey(Action, on_delete=models.PROTECT, help_text="The Action this contribution was made in reaction to.")
	recipient = models.ForeignKey(Recipient, on_delete=models.PROTECT, help_text="The Recipient this contribution was sent to.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount of the contribution, in dollars.")
	refunded_time = models.DateTimeField(blank=True, null=True, help_text="If the contribution was refunded to the user, the time that happened.")

	de_id = models.CharField(max_length=64, help_text="The Democracy Engine ID that the contribution was assigned to.")

	extra = JSONField(blank=True, help_text="Additional information about the contribution.")

	class Meta:
		unique_together = [('pledge_execution', 'action'), ('pledge_execution', 'recipient')]
