import enum, decimal, copy

from django.db import models, transaction, IntegrityError
from django.conf import settings
from django.utils import timezone
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from contrib.bizlogic import get_pledge_recipients, create_pledge_donation, void_pledge_transaction, HumanReadableValidationError

from itfsite.utils import JSONField, TextFormat
from enum3field import EnumField, django_enum
from datetime import timedelta

#####################################################################
#
# Utilities / Enums
#
#####################################################################

@django_enum
class ActorParty(enum.Enum):
	Democratic = 1
	Republican = 2
	Independent = 3

	def opposite(self):
		if self == ActorParty.Democratic: return ActorParty.Republican
		if self == ActorParty.Republican: return ActorParty.Democratic
		raise ValueError("%s does not have an opposite party." % str(self))

#####################################################################
#
# Triggers
#
# A future event that triggers pledged contributions.
#
#####################################################################

class TriggerType(models.Model):
	"""A class of triggers, like a House vote."""

	key = models.CharField(max_length=64, blank=True, null=True, db_index=True, unique=True, help_text="An opaque look-up key to quickly locate this object.")
	title = models.CharField(max_length=200, help_text="The title for the trigger.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	strings = JSONField(default={}, help_text="A dictionary of displayable text.")
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def __str__(self):
		return self.key

@django_enum
class TriggerStatus(enum.Enum):
	Draft = 0
	Open = 1
	Paused = 2
	Executed = 3
	Vacated = 4

class Trigger(models.Model):
	"""A future event that triggers a camapaign contribution, such as a roll call vote in Congress."""

	key = models.CharField(max_length=64, blank=True, null=True, db_index=True, unique=True, help_text="An opaque look-up key to quickly locate this object.")

	title = models.CharField(max_length=200, help_text="The title for the trigger.")
	owner = models.ForeignKey('itfsite.Organization', blank=True, null=True, on_delete=models.PROTECT, help_text="The user/organization which created the trigger and can update it. Empty for Triggers created by us.")
	trigger_type = models.ForeignKey(TriggerType, on_delete=models.PROTECT, help_text="The type of the trigger, which determines how it is described in text.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	slug = models.SlugField(max_length=200, help_text="The URL slug for this trigger.")
	subhead = models.TextField(help_text="Short sub-heading text in the format given by description_format.")
	subhead_format = EnumField(TextFormat, help_text="The format of the subhead text.")
	description = models.TextField(help_text="Description text in the format given by description_format.")
	description_format = EnumField(TextFormat, help_text="The format of the description text.")
	execution_note = models.TextField(help_text="Explanatory note about how this Trigger will be executed, in the format given by execution_note_format.")
	execution_note_format = EnumField(TextFormat, help_text="The format of the execution_note text.")
	status = EnumField(TriggerStatus, default=TriggerStatus.Draft, help_text="The current status of the trigger: Open (accepting pledges), Paused (not accepting pledges), Executed (funds distributed), Vacated (existing pledges invalidated).")
	outcomes = JSONField(default=[], help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	pledge_count = models.IntegerField(default=0, help_text="A cached count of the number of pledges made *prior* to trigger execution (excludes Pledges with made_after_trigger_execution).")
	total_pledged = models.DecimalField(max_digits=6, decimal_places=2, default=0, db_index=True, help_text="A cached total amount of pledges made *prior* to trigger execution (excludes Pledges with made_after_trigger_execution).")

	def __str__(self):
		return "%s [%d]" % (self.key, self.id)

	@property
	def verb(self):
		if self.status != TriggerStatus.Executed:
			# If the trigger has not yet been executed, then use the future tense.
			return self.trigger_type.strings['action_vb_inf']
		else:
			# If the trigger has been executed, then use the past tense.
			return self.trigger_type.strings['action_vb_past']

	def outcome_strings(self):
		# "overridden" by TriggerCustomizations
		return self.outcomes

	def get_minimum_pledge(self):
		alg = Pledge.current_algorithm()
		m1 = alg['min_contrib']
		m2 = 0
		if 'max_split' in self.extra:
			# The minimum pledge is one cent to all possible recipients, plus fees.
			m2 = decimal.Decimal('0.01') * self.extra['max_split'] * (1 + alg['fees_percent']) + alg['fees_fixed']
			m2 = m2.quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_UP)
		return max(m1, m2)

	# Execute.
	@transaction.atomic
	def execute(self, action_time, actor_outcomes, description, description_format, extra):
		# Executes the trigger.

		# Lock the trigger to prevent race conditions and make sure the Trigger
		# is either Open or Paused.
		trigger = Trigger.objects.select_for_update().filter(id=self.id).first()
		if trigger.status not in (TriggerStatus.Open, TriggerStatus.Paused):
			raise ValueError("Trigger is in state %s." % str(trigger.status))

		# Create TriggerExecution object.
		te = TriggerExecution()
		te.trigger = trigger
		te.cycle = settings.CURRENT_ELECTION_CYCLE
		te.action_time = action_time
		te.description = description
		te.description_format = description_format
		te.extra = extra
		te.save()

		# Create Action objects which represent what each Actor did.
		# actor_outcomes is a dict mapping Actors to outcome indexes
		# or None if the Actor didn't properly participate or a string
		# meaning the Actor didn't participate and the string gives
		# the reason_for_no_outcome value.
		for actor, outcome in actor_outcomes.items():
			# If an Actor has an inactive_reason set, then we ignore
			# any outcome supplied to us and replace it with that.
			# Probably 'Not running for reelection.'.
			if actor.inactive_reason:
				outcome = actor.inactive_reason

			ac = Action.create(te, actor, outcome)

		# Mark as executed.
		trigger.status = TriggerStatus.Executed
		trigger.save()

	# Vacate, meaning we do not expect the action to ever occur.
	@transaction.atomic
	def vacate(self):
		trigger = Trigger.objects.select_for_update().filter(id=self.id).first()
		if trigger.status not in (TriggerStatus.Open, TriggerStatus.Paused):
			raise ValueError("Trigger is in state %s." % str(trigger.status))

		# Mark as vacated.
		trigger.status = TriggerStatus.Vacated
		trigger.save()

		# Mark all pledges as vacated.
		pledges = trigger.pledges.select_for_update()
		for p in pledges:
			if p.status != PledgeStatus.Open:
				raise ValueError("Pledge %s is in state %s." % (repr(p), str(p.status)))
			p.status = PledgeStatus.Vacated
			p.save()

	def clone_as_announced_positions_on(self):
		t = Trigger()
		t.status = TriggerStatus.Open # so we can execute it
		t.key = self.key + ":announced"
		t.title = "Announced Positions on " + self.title
		t.owner = self.owner
		t.trigger_type = TriggerType.objects.get_or_create(
			key = "announced-positions",
			defaults = {
				"strings": {
					"actor": 'member of Congress',
					"actors": 'members of Congress',
					"action_vb_inf": "announce they would vote",
					"action_vb_pres_s": "announces they would vote",
					"action_vb_past": "announced they would vote",
			}})[0]
		t.slug = self.slug + "-announced"
		t.subhead = "n/a"
		t.subhead_format = TextFormat.HTML
		t.description = "n/a"
		t.description_format = TextFormat.HTML
		t.execution_note = "n/a"
		t.execution_note_format = TextFormat.HTML
		t.outcomes = self.outcomes
		t.extra = self.extra
		t.save()

		# Execute with no actor information.
		t.execute(t.created, { }, "Empty.", TextFormat.HTML, { })

		return t

class TriggerStatusUpdate(models.Model):
	"""A status update about the Trigger providing further information to users looking at the Trigger that was not known when the Trigger was created."""

	trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, help_text="The Trigger that this update is about.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)
	text = models.TextField(help_text="Status update text in the format given by text_format.")
	text_format = EnumField(TextFormat, help_text="The format of the text.")

class TriggerRecommendation(models.Model):
	trigger1 = models.ForeignKey(Trigger, related_name="recommends", on_delete=models.CASCADE, help_text="If a user has taken action on this Trigger, then we send them a notification.")
	trigger2 = models.ForeignKey(Trigger, related_name="recommended_by", on_delete=models.CASCADE, help_text="This is the trigger that we recommend the user take action on.")
	symmetric = models.BooleanField(default=False, help_text="If true, the recommendation goes both ways.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	notifications_created = models.BooleanField(default=False, db_index=True, help_text="Set to true once notifications have been generated for users for any past actions the users took before this recommendation was added.")

	def __str__(self):
		return " ".join([
			str(self.trigger1),
			"=>" if not self.symmetric else "<=>",
			str(self.trigger2),
		])

	def save(self, *args, override_immutable_check=False, **kwargs):
		# Prevent the instance from being modified. Then save.
		if not override_immutable_check and self.id: raise Exception("This model is immutable.")
		super(TriggerRecommendation, self).save(*args, **kwargs)

	@staticmethod
	def create_notifications(user, trigger):
		from itfsite.models import Notification, NotificationType

		ct = ContentType.objects.get_for_model(TriggerRecommendation)

		# The user just took action on trigger. Create relevant further
		# suggestions as notifications by looking at the trigger2 of
		# TriggerRecommendation instances where trigger1 is the trigger,
		# and conversely for symmetric TriggerRecommendations.
		recs = \
		    [(rec, rec.trigger2, False) for rec in TriggerRecommendation.objects.filter(trigger1=trigger)] \
		  + [(rec, rec.trigger1, True) for rec in TriggerRecommendation.objects.filter(symmetric=True, trigger2=trigger)]

		# Filter out triggers that the user has already taken action on.
		t_acted = Trigger.objects.filter(
			id__in=set(r[1].id for r in recs),
			pledges__user=user) 

		for rec, t, converse in recs:
			# Skip if the user already took this action.
			if t in t_acted: continue

			# Create Notification. See create_initial_notifications for another
			# version of this.
			rec.create_notification(user.id, converse, ct)

		# Also delete any pre-existing unseen notifications for the trigger
		# the user just took action on. No need to notify the user about this
		# anymore.
		recs = TriggerRecommendation.objects.filter(trigger2=trigger) \
		  | TriggerRecommendation.objects.filter(symmetric=True, trigger1=trigger)
		Notification.objects.filter(
			user=user,
			notif_type=NotificationType.TriggerRecommendation,
			source_content_type=ct,
			source_object_id__in=set(rec.id for rec in recs),
			dismissed_at=None,
			mailed_at=None).delete()

	@transaction.atomic
	def create_initial_notifications(self):
		if self.notifications_created: raise ValueError("Notifications were already created.")

		ct = ContentType.objects.get_for_model(TriggerRecommendation)

		# Wrapper function to do the hard work.
		def go(t1, t2, converse):
			# Get users who have taken action on t1 but not on t2.
			users1 = set(Pledge.objects.filter(trigger=t1).exclude(user=None).values_list('user', flat=True))
			users2 = set(Pledge.objects.filter(trigger=t2).exclude(user=None).values_list('user', flat=True))
			users = users1 - users2

			# Create notifications to take action on t2.
			for u in users:
				self.create_notification(u, converse, ct)

		# Create the notifications.
		go(self.trigger1, self.trigger2, False)
		if self.symmetric:
			go(self.trigger2, self.trigger1, True)

		# Mark this as having now created the initial notifications.
		self.notifications_created = True
		self.save(update_fields=['notifications_created'], override_immutable_check=True)

	def create_notification(self, user_id, converse, ct):
		from itfsite.models import Notification, NotificationType
		Notification.objects.get_or_create(
			user_id=user_id,
			notif_type=NotificationType.TriggerRecommendation,
			source_content_type=ct,
			source_object_id=self.id,
			extra={
				"converse": converse,
			})

	def get_source_target(self, notification):
		if not notification.extra['converse']:
			return self.trigger1, self.trigger2
		else:
			return self.trigger2, self.trigger1

	@staticmethod
	def render_notifications(notifications):
		# Split up the notifications by the target bill. Map
		# each target bill to a list of notifications recommending it.
		# Skip triggers whose current status does not allow for
		# users to take action --- maybe this should be done
		# at the time of adding notifications? (but then how to
		# handle the status of a trigger changing?)
		alerts = { }
		for n in notifications:
			t1, t2 = n.source.get_source_target(n)
			if t2.status in (TriggerStatus.Open, TriggerStatus.Executed):
				alerts.setdefault(t2, []).append(n)

		return []

		# Render each target bill separately.
		from urllib.parse import quote
		alerts = [{
				"title": target.title, # short title / may go in email subject
				"body_html": "We have a recommendation for you! <a href='{{link}}'>{{title}}</a> is a new {{noun}} you might be interested in.",
				"body_text": "We have a recommendation for you! {{title}} ({{link}}) is a new {{noun}} you might be interested in.",
				"body_context": {
					"title": target.title,
					"link": settings.SITE_ROOT_URL + target.get_absolute_url() \
						+ "?utm_campaign=" + quote('itf-tr'),
					"noun": target.trigger_type.strings['action_noun'],
				},
				"notifications": notificationlist,
			} for target, notificationlist in alerts.items()]

		return alerts

class TriggerCustomization(models.Model):
	"""The specialization of a trigger for an Organization."""

	owner = models.ForeignKey('itfsite.Organization', related_name="triggers", on_delete=models.CASCADE, help_text="The user/organization which created the TriggerCustomization.")
	trigger = models.ForeignKey(Trigger, related_name="customizations", on_delete=models.CASCADE, help_text="The Trigger that this TriggerCustomization customizes.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	outcome = models.IntegerField(blank=True, null=True, help_text="Restrict Pledges to this outcome index.")
	incumb_challgr = models.FloatField(blank=True, null=True, help_text="Restrict Pledges to this incumb_challgr value.")
	filter_party = EnumField(ActorParty, blank=True, null=True, help_text="Restrict Pledges to this party.")
	filter_competitive = models.NullBooleanField(default=False, help_text="Restrict Pledges to this filter_competitive value.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	class Meta:
		unique_together = ('trigger', 'owner')

	def __str__(self):
		return "%s / %s" % (self.owner, self.trigger)

	def has_fixed_outcome(self):
		return self.outcome is not None

	def outcome_strings(self):
		if self.extra and self.extra.get('outcome_strings'):
			return self.extra['outcome_strings']
		else:
			return self.trigger.outcome_strings()

	def get_outcome(self):
		if self.outcome is None: raise ValueError()
		return self.outcome_strings()[self.outcome]

class TriggerExecution(models.Model):
	"""How a Trigger was executed."""

	trigger = models.OneToOneField(Trigger, related_name='execution', on_delete=models.PROTECT, help_text="The Trigger this execution information is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)
	action_time = models.DateTimeField(help_text="The date & time the action actually ocurred in the real world.")

	cycle = models.IntegerField(help_text="The election cycle (year) that the trigger was executed in.")

	description = models.TextField(help_text="Once a trigger is executed, additional text added to explain how funds were distributed.")
	description_format = EnumField(TextFormat, help_text="The format of the description text.")

	pledge_count = models.IntegerField(default=0, help_text="A cached count of the number of pledges executed. This counts pledges from anonymous users that do not result in contributions. Used to check when a Trigger is done executing.")
	pledge_count_with_contribs = models.IntegerField(default=0, help_text="A cached count of the number of pledges executed with actual contributions made.")
	num_contributions = models.IntegerField(default=0, db_index=True, help_text="A cached total number of campaign contributions executed.")
	total_contributions = models.DecimalField(max_digits=6, decimal_places=2, default=0, db_index=True, help_text="A cached total amount of campaign contributions executed, excluding fees.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def __str__(self):
		return "%s [exec %s]" % (self.trigger, self.created.strftime("%x"))

	def delete(self, *args, **kwargs):
		# After deleting a TriggerExecution, reset the status of the trigger
		# to Paused. Leaving it as Executed would leave it in an inconsistent
		# state and makes debugging harder.
		super(TriggerExecution, self).delete(*args, **kwargs)
		self.trigger.status = TriggerStatus.Paused
		self.trigger.save(update_fields=['status'])

	def get_outcomes(self, via_campaign=None):
		# Get the contribution aggregates by outcome
		# and sort by total amount of contributions.
		outcomes = copy.deepcopy(self.trigger.outcomes)
		for i in range(len(outcomes)):
			outcomes[i]['index'] = i
			outcomes[i]['contribs'] = 0
		for rec in ContributionAggregate.get_slices('outcome', trigger_execution=self, via_campaign=via_campaign):
			outcomes[rec['outcome']]['contribs'] = rec['total']
		outcomes.sort(key = lambda x : x['contribs'], reverse=True)
		return outcomes

	def most_recent_pledge_execution(self):
		return self.pledges.order_by('-created').first()

#####################################################################
#
# Actors
#
# Elected officials and their official acts.
#
#####################################################################

class Actor(models.Model):
	"""A public figure, e.g. elected official with an election campaign, who might take an action."""

	govtrack_id = models.IntegerField(unique=True, help_text="GovTrack's ID for this person.")
	votervoice_id = models.IntegerField(blank=True, null=True, unique=True, help_text="VoterVoice's target ID for this person.")

	office = models.CharField(max_length=7, blank=True, null=True, unique=True, help_text="A code specifying the office currently held by the Actor, in the same format as Recipient.office_sought.")

	name_long = models.CharField(max_length=128, help_text="The long form of the person's current name, meant for a page title.")
	name_short = models.CharField(max_length=128, help_text="The short form of the person's current name, usually a last name, meant for in-page second references.")
	name_sort = models.CharField(max_length=128, help_text="The sorted list form of the person's current name.")
	party = EnumField(ActorParty, help_text="The current party of the Actor. For Members of Congress, this is based on how the Member caucuses to avoid Independent as much as possible.")
	title = models.CharField(max_length=200, help_text="Descriptive text for the office held by this actor.")
	
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	challenger = models.OneToOneField('Recipient', unique=True, null=True, blank=True, related_name="challenger_to", help_text="The *current* Recipient that contributions to this Actor's challenger go to. Independents don't have challengers because they have no opposing party.")
	inactive_reason = models.CharField(blank=True, null=True, max_length=200, help_text="If the Actor is still a public official (i.e. generates Actions) but should not get contributions, the reason why. If not None, serves as a flag. E.g. 'Not running for reelection.'.")

	def __str__(self):
		return self.name_sort

class Action(models.Model):
	"""The outcome of an actor taking an act described by a trigger."""

	execution = models.ForeignKey(TriggerExecution, related_name="actions", on_delete=models.CASCADE, help_text="The TriggerExecution that created this object.")
	action_time = models.DateTimeField(db_index=True, help_text="The date & time the action actually ocurred in the real world.")
	actor = models.ForeignKey(Actor, on_delete=models.PROTECT, help_text="The Actor who took this action.")
	outcome = models.IntegerField(blank=True, null=True, help_text="The outcome index that was taken. May be null if the Actor should have participated but didn't (we want to record to avoid counterintuitive missing data).")

	name_long = models.CharField(max_length=128, help_text="The long form of the person's name at the time of the action, meant for a page title.")
	name_short = models.CharField(max_length=128, help_text="The short form of the person's name at the time of the action, usually a last name, meant for in-page second references.")
	name_sort = models.CharField(max_length=128, help_text="The sorted list form of the person's name at the time of the action.")
	party = EnumField(ActorParty, help_text="The party of the Actor at the time of the action.")
	title = models.CharField(max_length=200, help_text="Descriptive text for the office held by this actor at the time of the action.")
	office = models.CharField(max_length=7, blank=True, null=True, unique=True, help_text="A code specifying the office held by the Actor at the time the Action was created, in the same format as Recipient.office_sought.")
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	challenger = models.ForeignKey('Recipient', null=True, blank=True, help_text="The Recipient that contributions to this Actor's challenger go to, at the time of the Action. Independents don't have challengers because they have no opposing party.")

	total_contributions_for = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="A cached total amount of campaign contributions executed with the actor as the recipient (excluding fees).")
	total_contributions_against = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="A cached total amount of campaign contributions executed with an opponent of the actor as the recipient (excluding fees).")

	reason_for_no_outcome = models.CharField(blank=True, null=True, max_length=200, help_text="If outcome is null, why. E.g. 'Did not vote.'.")

	class Meta:
		unique_together = [('execution', 'actor')]

	def __str__(self):
		return "%s is %s | %s" % (
			self.actor,
			self.outcome_label(),
			self.execution)

	def has_outcome(self):
		return self.outcome is not None

	def outcome_label(self):
		if self.outcome is not None:
			return self.execution.trigger.outcomes[self.outcome]['label']
		if self.reason_for_no_outcome:
			return self.reason_for_no_outcome
		return "N/A"

	@staticmethod
	def create(execution, actor, outcome):
		# outcome can be an integer giving the Trigger's outcome index
		# that the Actor did . . .
		if isinstance(outcome, int):
			outcome_index = outcome
			reason_for_no_outcome = None

		# Or it can be None or a string giving an explanation for why
		# the Action has no outcome.
		else:
			outcome_index = None
			reason_for_no_outcome = outcome

		# Create the Action instance.
		a = Action()
		a.execution = execution
		a.actor = actor
		a.outcome = outcome_index
		a.action_time = execution.action_time
		a.reason_for_no_outcome = reason_for_no_outcome

		# Copy fields that may change on the Actor but that we want to know what they were
		# at the time this Action ocurred.
		for f in ('name_long', 'name_short', 'name_sort', 'party', 'title', 'office', 'extra', 'challenger'):
			setattr(a, f, getattr(actor, f))

		# Save.
		a.save()
		return a


#####################################################################
#
# Pledges
#
# A pledged campaign contribution by a user.
#
#####################################################################

class ContributorInfo(models.Model):
	"""Contributor and billing information used for a Pledge. Stored schema-less in the extra field. May be shared across Pledges of the same user. Instances are immutable."""

	created = models.DateTimeField(auto_now_add=True, db_index=True)

	cclastfour = models.CharField(max_length=4, blank=True, null=True, db_index=True, help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a pledge from a credit card number.")
	is_geocoded = models.BooleanField(default=False, db_index=True, help_text="Whether this record has been geocoded.")

	extra = JSONField(blank=True, help_text="Schemaless data stored with this object.")

	def __str__(self):
		return "[%d] %s %s" % (self.id, self.name, self.address)

	def save(self, *args, override_immutable_check=False, **kwargs):
		if self.id and not override_immutable_check:
			raise Exception("This model is immutable.")
		super(ContributorInfo, self).save(*args, **kwargs)

	def can_delete(self):
		return not self.pledges.exists() and not self.tips.exists()

	@property
	def name(self):
		return ' '.join(self.extra['contributor'][k] for k in ('contribNameFirst', 'contribNameLast'))

	@property
	def address(self):
		return ', '.join(self.extra['contributor'][k] for k in ('contribCity', 'contribState'))

	def set_from(self, data):
		# Initialize from a dictionary.

		# Store the last four digits of the credit card number so we can
		# quickly locate a Pledge by CC number (approximately).
		self.cclastfour = data['billing']['cc_num'][-4:]

		# Store a hashed version of the credit card number so we can
		# do a verification if the user wants to look up a Pledge by CC
		# info. Use Django's built-in password hashing functionality to
		# handle this. Then clear the cc_num field.
		from django.contrib.auth.hashers import make_password
		data['billing']['cc_num_hashed'] = make_password(data['billing']['cc_num'])
		del data['billing']['cc_num']

		# Store the rest in extra.
		self.extra = data

	def same_as(self, other):
		import json
		def normalize(data): return json.dumps(data, sort_keys=True)
		return (self.cclastfour == other.cclastfour) and (normalize(self.extra) == normalize(other.extra))

	def open_pledge_count(self):
		return self.pledges.filter(status=PledgeStatus.Open).count()

	def geocode(self):
		# Updates this record with geocoder information, especially congressional district
		# and timezone.
		from contrib.legislative import geocode
		info = geocode([
			self.extra['contributor']['contribAddress'],
			self.extra['contributor']['contribCity'],
			self.extra['contributor']['contribState'],
			self.extra['contributor']['contribZip']])
		self.extra['geocode'] = info
		self.is_geocoded = True
		self.save(update_fields=['is_geocoded', 'extra'], override_immutable_check=True)

	@staticmethod
	def find_from_cc(cc_number):
		# Returns an interator that yields matchinig Pledge instances.
		# Must be in parallel to how the view function creates the pledge.
		from django.contrib.auth.hashers import check_password
		cc_number = cc_number.replace(' ', '')
		for p in ContributorInfo.objects.filter(cclastfour=cc_number[-4:]):
			if check_password(cc_number, p.extra['billing']['cc_num_hashed']):
				yield p

	@staticmethod
	def createRandom():
		# For testing!
		import random
		return ContributorInfo.objects.create(extra={
			"contributor": {
				"contribNameFirst": random.choice(["Jeanie", "Lucrecia", "Marvin", "Jasper", "Carlo", "Millicent", "Zack", "Raul", "Johnny", "Margarette"]),
				"contribNameLast": random.choice(["Ramm", "Berns", "Wannamaker", "McCarroll", "Bumbrey", "Caudle", "Bridwell", "Pacelli", "Crowley", "Montejano"]),
				"contribAddress": "%d %s %s" % (random.randint(10, 200), random.choice(["Fir", "Maple", "Cedar", "Dogwood", "Persimmon", "Beech"]), random.choice([ "St", "Ave", "Ct"])),
				"contribCity": random.choice(["Rudy", "Hookerton", "La Ward", "Marenisco", "Nara Visa"]),
				"contribState": random.choice(["NQ", "BL", "PS"]),
				"contribZip": random.randint(10000, 88888),
				"contribEmployer": "self",
				"contribOccupation": "unspecified",
			},
			"billing": {
				"de_cc_token": "_made_up_%d" % random.randint(1, 100000),
			},
		})

@django_enum
class PledgeStatus(enum.Enum):
	Open = 1
	Executed = 2
	Vacated = 10 # trigger was vacated, pledge is considered vacated

class NoMassDeleteManager(models.Manager):
	class CustomQuerySet(models.QuerySet):
		def delete(self):
			# Can't do a mass delete because it would not update Trigger.total_pledged,
			# in the case of the Pledge model.
			#
			# Instead call delete() on each instance, which handles the constraint.
			for obj in self:
				obj.delete()
	def get_queryset(self):
		return NoMassDeleteManager.CustomQuerySet(self.model, using=self._db)

class Pledge(models.Model):
	"""A user's pledge of a contribution."""

	user = models.ForeignKey('itfsite.User', blank=True, null=True, on_delete=models.PROTECT, help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored in an AnonymousUser object referenced in anon_user, and the pledge should be considered unconfirmed/provisional and will not be executed.")
	anon_user = models.ForeignKey('itfsite.AnonymousUser', blank=True, null=True, on_delete=models.CASCADE, help_text="When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.")
	_email = models.EmailField(max_length=254, blank=True, null=True, help_text="to be removed.")
	profile = models.ForeignKey(ContributorInfo, related_name="pledges", on_delete=models.PROTECT, help_text="The contributor information (name, address, etc.) and billing information used for this Pledge. Immutable and cannot be changed after execution.")

	trigger = models.ForeignKey(Trigger, related_name="pledges", on_delete=models.PROTECT, help_text="The Trigger that this Pledge is for.")
	via_campaign = models.ForeignKey('itfsite.Campaign', blank=True, null=True, related_name="pledges", on_delete=models.PROTECT, help_text="The Campaign that this Pledge was made via.")

	ref_code = models.CharField(max_length=24, blank=True, null=True, db_index=True, help_text="An optional referral code that lead the user to take this action.")

	# When a Pledge is cancelled, the object is deleted. The trigger/via_campaign/user/anon_user fields
	# are archived, plus the fields listed in this list. The fields below must
	# be JSON-serializable.
	cancel_archive_fields = (
		'created', 'updated', 'ref_code',
		'algorithm', 'desired_outcome', 'amount',
		)

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)
	algorithm = models.IntegerField(default=0, help_text="In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.")
	status = EnumField(PledgeStatus, default=PledgeStatus.Open, help_text="The current status of the pledge.")
	made_after_trigger_execution = models.BooleanField(default=False, help_text="Whether this Pledge was created after the Trigger was executed (i.e. outcomes known).")

	desired_outcome = models.IntegerField(help_text="The outcome index that the user desires.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The pledge amount in dollars (including fees). The credit card charge may be less in the event that we have to round to the nearest penny-donation.")
	incumb_challgr = models.FloatField(help_text="A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)")
	filter_party = EnumField(ActorParty, blank=True, null=True, help_text="Contributions only go to candidates whose party matches this party. Independent is not an allowed value here.")
	filter_competitive = models.BooleanField(default=False, help_text="Whether to filter contributions to competitive races.")

	tip_to_campaign_owner = models.DecimalField(max_digits=6, decimal_places=2, default=decimal.Decimal(0), help_text="The amount in dollars that the user desires to send to the owner of via_campaign, zero if there is no one to tip or the user desires not to tip.")

	cclastfour = models.CharField(max_length=4, blank=True, null=True, db_index=True, help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a pledge from a credit card number.")

	email_confirmed_at = models.DateTimeField(blank=True, null=True, help_text="The date and time that the email address of the pledge became confirmed, if the pledge was originally based on an unconfirmed email address.")
	pre_execution_email_sent_at = models.DateTimeField(blank=True, null=True, help_text="The date and time when the user was sent an email letting them know that their pledge is about to be executed.")
	post_execution_email_sent_at = models.DateTimeField(blank=True, null=True, help_text="The date and time when the user was sent an email letting them know that their pledge was executed.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	class Meta:
		unique_together = [('trigger', 'user'), ('trigger', 'anon_user')]
		index_together = [('trigger', 'via_campaign')]

	objects = NoMassDeleteManager()

	ENFORCE_EXECUTION_EMAIL_DELAY = True # can disable for testing

	@transaction.atomic
	def save(self, *args, **kwargs):
		# Override .save() so on the INSERT of a new Pledge we increment
		# counters on the Trigger.
		is_new = (not self.id) # if the pk evaluates to false, Django does an INSERT

		# Actually save().
		super(Pledge, self).save(*args, **kwargs)

		# For a new object, increment the trigger's pledge_count and total_pledged
		# fields (atomically) if this Pledge was made prior to trigger execution.
		if is_new and not self.made_after_trigger_execution:
			from django.db import models
			self.trigger.pledge_count = models.F('pledge_count') + 1
			self.trigger.total_pledged = models.F('total_pledged') + self.amount
			self.trigger.save(update_fields=['pledge_count', 'total_pledged'])

	@transaction.atomic
	def delete(self):
		if self.status != PledgeStatus.Open:
			raise ValueError("Cannot cancel a Pledge with status %s." % self.status)

		# Decrement the Trigger's pledge_count and total_pledged if the Pledge
		# was made prior to trigger execution.
		if not self.made_after_trigger_execution:
			self.trigger.pledge_count = models.F('pledge_count') - 1
			self.trigger.total_pledged = models.F('total_pledged') - self.amount
			self.trigger.save(update_fields=['pledge_count', 'total_pledged'])

		# Archive as a cancelled pledge.
		cp = CancelledPledge.from_pledge(self)

		# Remove record. Will raise an exception and abort the transaction if
		# the pledge has been executed and a PledgeExecution object refers to this.
		super(Pledge, self).delete()	

	def get_absolute_url(self):
		return self.via_campaign.get_absolute_url()

	@staticmethod
	def current_algorithm():
		return {
			"id": 1, # a sequence number so we can track changes to our fee structure, etc.
			"min_contrib": 1, # dollars
			"max_contrib": 500, # dollars
			"fees_fixed": decimal.Decimal("0.20"), # 20 cents, convert from string so it is exact
			"fees_percent": decimal.Decimal("0.09"), # 0.09 means 9%, convert from string so it is exact
			"pre_execution_warn_time": (timedelta(days=1), "this time tomorrow"),
		}

	def __str__(self):
		return self.get_email() + " => " + str(self.trigger)

	def get_email(self):
		if self.user:
			return self.user.email
		else:
			return self.anon_user.email

	@property
	def get_nice_status(self):
		if self.status != PledgeStatus.Executed:
			return self.status.name
		elif self.execution.problem == PledgeExecutionProblem.NoProblem:
			return "Finished"
		else:
			return "Failed"

	@property
	def targets_summary(self):
		# This is mirrored in pledge_form.html.

		def outcome_label(outcome):
			x = self.trigger.outcomes[outcome]
			return x.get("object", x["label"])
		desired_outcome_label = outcome_label(self.desired_outcome)
		if len(self.trigger.outcomes) != 2:
			raise ValueError("Trigger has more than two options.")
		antidesired_outcome_label = outcome_label(1 - self.desired_outcome)

		party_filter = ""
		if self.filter_party is not None:
			party_filter = self.filter_party.name + " "

		noun = self.trigger.trigger_type.strings['actors']
		verb = self.trigger.verb

		if self.incumb_challgr == 1:
			# "keep em in"
			return "%s%s who %s %s" \
				% (party_filter, noun, verb, desired_outcome_label)
		elif self.incumb_challgr == -1:
			# "throw em out"
			return "the opponents in the next general election of %s who %s %s%s" \
				% (noun, verb, antidesired_outcome_label, ((" if the opponent is in the %sparty" % party_filter) if party_filter else ""))
		elif party_filter == "":
			# goes to incumbents and challengers, no party filter
			if self.status != PledgeStatus.Executed:
				count = "up to %d" % self.trigger.extra['max_split']
			else:
				count = str(self.execution.contributions.count())
			return "%s %s, each getting a part of your contribution if they %s %s, but if they %s %s their part of your contribution will go to their next general election opponent" \
				% (count, noun, verb, desired_outcome_label,
				   verb, antidesired_outcome_label)
		else:
			# goes to incumbents and challengers, with a party filter
			return "%s%s who %s %s and the opponents in the next general election of %s who %s %s%s" \
				% (party_filter, noun, verb, desired_outcome_label,
				                 noun, verb, antidesired_outcome_label, ((" if the opponent is in the %sparty" % party_filter) if party_filter else ""))


	def set_confirmed_user(self, user, request):
		# The user may have anonymously created a second Pledge for the same
		# trigger. We can't tell them before they confirm their email that
		# they already made a pledge. We can't confirm both --- warn the user
		# and go on.

		from django.contrib import messages

		if self.trigger.pledges.filter(user=user).exists():
			messages.add_message(request, messages.ERROR, 'You had a previous contribution already scheduled for the same thing. Your more recent contribution will be ignored.')
			self.delete() # else we will try to confirm the email address indefinitely, but the AnonymousUser for this is already confirmed, so it would be an error
			return

		# Move this anonymous pledge to the user's account.
		self.user = user
		self.anon_user = None
		self.email_confirmed_at = timezone.now()
		self.save(update_fields=['user', 'anon_user', 'email_confirmed_at'])

		# Let the user know what happened.
		messages.add_message(request, messages.SUCCESS, 'Your contribution regarding %s has been confirmed.'
			% self.trigger.title)

		# And run the steps that happen once a user is confirmed. This is
		# separate since some Pledges are born confirmed.
		self.run_post_confirm_steps()

	def run_post_confirm_steps(self):
		# Create new notifications for this user based on any recommendations
		# for further action that the user may now take. Also clear any
		# pre-existing notifications for the trigger the user just took action on.
		TriggerRecommendation.create_notifications(self.user, self.trigger)

	def needs_pre_execution_email(self):
		# If the user confirmed their email address after the trigger
		# was executed, then the pre-execution emails already went out
		# and this user probably did not get one because those are only
		# sent if the email address is confirmed. We don't want to cause
		# a delay for everyone else, so these users just don't get a
		# confirmation.
		trigger_execution = self.trigger.execution
		if self.email_confirmed_at and self.email_confirmed_at >= trigger_execution.created:
			return False

		# If the pledge itself was created after the trigger was executed,
		# then we don't send the pre-execution email so we can execute as
		# quickly as possible.
		if self.made_after_trigger_execution:
			return False

		return True

	@transaction.atomic
	def execute(self, ca_updater=None):
		# Lock the Pledge and the Trigger to prevent race conditions.
		pledge = Pledge.objects.select_for_update().filter(id=self.id).first()
		trigger = Trigger.objects.select_for_update().filter(id=pledge.trigger.id).first()
		trigger_execution = trigger.execution

		# Validate state.
		if pledge.status != PledgeStatus.Open:
			raise ValueError("Pledge cannot be executed in status %s." % pledge.status)
		if trigger.status != TriggerStatus.Executed:
			raise ValueError("Pledge cannot be executed when trigger is in status %s." % trigger.status)
		if pledge.algorithm != Pledge.current_algorithm()['id']:
			raise ValueError("Pledge has an invalid algorithm.")

		# Default values.
		problem = PledgeExecutionProblem.NoProblem
		exception = None
		recip_contribs = []
		fees = 0
		total_charge = 0
		de_don = None

		# Buffer updates to the ContributionAggregate table.
		ca_updater_sync_at_end = False
		if ca_updater is None:
			ca_updater = ContributionAggregate.Updater()
			ca_updater_sync_at_end = True

		if pledge.user is None:
			# We do not make contributions for pledges from unconfirmed email
			# addresses, since we can't let them know that we're about to
			# execute the pledge. But we execute it so that our data model
			# is consistent: All Pledges associated with an executed Trigger
			# are executed.
			problem = PledgeExecutionProblem.EmailUnconfirmed

		else:
			# Get the actual recipients of the pledge, as a list of tuples of
			# (Recipient, Action). The pledge filters may result in there being
			# no actual recipients.
			recipients = get_pledge_recipients(trigger, pledge)

			if len(recipients) == 0:
				# If there are no matching recipients, we don't make a credit card chage.
				problem = PledgeExecutionProblem.FiltersExcludedAll

			else:
				# Additional checks that don't apply to failed executions for reasons above.
				if pledge.pre_execution_email_sent_at is None:
					if pledge.needs_pre_execution_email():
						# Not all pledges require the pre-exeuction email (see that function
						# for details, but it's users who confirm their email address too late).
						raise ValueError("User %s has not yet been sent the pre-execution email." % pledge.user)
				elif (timezone.now() - pledge.pre_execution_email_sent_at) < Pledge.current_algorithm()['pre_execution_warn_time'][0] \
						and not settings.DEBUG and Pledge.ENFORCE_EXECUTION_EMAIL_DELAY:
					raise ValueError("User %s has not yet been given enough time to cancel the pledge." % pledge.user)

				# Make the donation (an authorization, since Democracy Engine does a capture later).
				#
				# (The transaction records created by the donation are not immediately
				# available, so we know success but can't get further details.)
				try:
					recip_contribs, fees, total_charge, de_don = \
						create_pledge_donation(pledge, recipients)

				# Catch typical exceptions and log them in the PledgeExecutionObject.
				except HumanReadableValidationError as e:
					problem = PledgeExecutionProblem.TransactionFailed
					exception = str(e)

		# From here on, if there is a problem then we need to print DE API donation
		# information before we lose track of it, since nothing will be written to
		# the database on an error.
		try:
			# Sanity check.
			if len(recip_contribs) == 0 and problem == PledgeExecutionProblem.NoProblem:
				raise Exception("Pledge executing with no recipients but no problem.")

			# Create PledgeExecution object.
			pe = PledgeExecution()
			pe.pledge = pledge
			pe.trigger_execution = trigger_execution
			pe.problem = problem
			pe.charged = total_charge
			pe.fees = fees
			pe.extra = {
				"donation": de_don, # donation record, which refers to transactions
				"exception": exception, 
			}
			pe.save()

			# Create Contribution objects.
			for recipient, action, amount in recip_contribs:
				c = Contribution()
				c.pledge_execution = pe
				c.action = action
				c.recipient = recipient
				c.amount = amount
				c.de_id = recipient.de_id
				c.save()

				# Increment the TriggerExecution and Action's total_contributions.
				c.update_aggregates(updater=ca_updater)

			# Mark pledge as executed.
			pledge.status = PledgeStatus.Executed
			pledge.save()

			# Increment TriggerExecution's pledge_count so that we know how many pledges
			# have been or have not yet been executed.
			trigger_execution.pledge_count = models.F('pledge_count') + 1
			if len(recip_contribs) > 0:
				trigger_execution.pledge_count_with_contribs = models.F('pledge_count_with_contribs') + 1
			trigger_execution.save(update_fields=['pledge_count', 'pledge_count_with_contribs'])

			# If the ContributionAggregate updater is local to this call, sync changes now.
			if ca_updater_sync_at_end:
				ca_updater.sync()

		except Exception as e:
			# If a DE transaction was made, include its info in any exception that was raised.
			if de_don:
				try:
					import rtyaml
					x = rtyaml.dump(de_don)
				except:
					x = repr(de_don)
				raise Exception("Something went wrong saving a pledge execution to the database (%s). The database transaction is about to be rolled back. But the DE transaction was already made.\n\n%s" % (str(e), x))
			else:
				raise



class CancelledPledge(models.Model):
	"""Records when a user cancels a Pledge."""

	created = models.DateTimeField(auto_now_add=True, db_index=True)

	trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, help_text="The Trigger that the pledge was for.")
	via_campaign = models.ForeignKey('itfsite.Campaign', blank=True, null=True, on_delete=models.CASCADE, help_text="The Campaign that this Pledge was made via.")
	user = models.ForeignKey('itfsite.User', blank=True, null=True, on_delete=models.CASCADE, help_text="The user who made the pledge, if not anonymous.")
	_email = models.EmailField(max_length=254, blank=True, null=True, help_text="to be deleted")
	anon_user = models.ForeignKey('itfsite.AnonymousUser', blank=True, null=True, on_delete=models.CASCADE, help_text="When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.")

	pledge = JSONField(blank=True, help_text="The original Pledge information.")

	@staticmethod
	def from_pledge(pledge):
		cp = CancelledPledge()
		cp.trigger = pledge.trigger
		cp.via_campaign = pledge.via_campaign
		cp.user = pledge.user
		cp.anon_user = pledge.anon_user
		cp.pledge = { k: getattr(pledge, k) for k in Pledge.cancel_archive_fields }
		cp.pledge['amount'] = float(cp.pledge['amount']) # can't JSON-serialize a Decimal
		cp.pledge['created'] = cp.pledge['created'].isoformat() # can't JSON-serialize a DateTime
		cp.pledge['updated'] = cp.pledge['updated'].isoformat() # can't JSON-serialize a DateTime
		cp.pledge.update(pledge.profile.extra)
		cp.save()

class IncompletePledge(models.Model):
	"""Records email addresses users enter. Deleted when they finish a Pledge."""
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, help_text="The Trigger that the pledge was for.")
	via_campaign = models.ForeignKey('itfsite.Campaign', blank=True, null=True, on_delete=models.CASCADE, help_text="The Campaign that this Pledge was made via.")
	email = models.EmailField(max_length=254, db_index=True, help_text="An email address.")
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")
	sent_followup_at = models.DateTimeField(blank=True, null=True, db_index=True, help_text="If we've sent a follow-up email, the date and time we sent it.")
	completed_pledge = models.ForeignKey(Pledge, blank=True, null=True, on_delete=models.CASCADE, help_text="If the user came back and finished a Pledge, that pledge.")

	def get_utm_campaign_string(self):
		# What campaign string do we attach to the URL?
		campaign = 'itf_ip_%d' % self.id
		if self.extra.get('ref_code'):
			campaign += ',' + self.extra.get('ref_code')
		return campaign

	def get_return_url(self):
		# Construct URL of the trigger with the utm_campaign query string argument.
		import urllib.parse
		return self.via_campaign.get_absolute_url() \
			+ "?" + urllib.parse.urlencode({ "utm_campaign": self.get_utm_campaign_string() })

@django_enum
class PledgeExecutionProblem(enum.Enum):
	NoProblem = 0
	EmailUnconfirmed = 1 # email address on the pledge was not confirmed
	FiltersExcludedAll = 2 # no recipient matched filters
	TransactionFailed = 3 # problems making the donation in the DE api
	Voided = 4 # after a successful transaction, user asked us to void it

class PledgeExecution(models.Model):
	"""How a user's pledge was executed. Each pledge has a single PledgeExecution when the Trigger is executed, and immediately many Contribution objects are created."""

	pledge = models.OneToOneField(Pledge, related_name="execution", on_delete=models.PROTECT, help_text="The Pledge this execution information is about.")
	trigger_execution = models.ForeignKey(TriggerExecution, related_name="pledges", on_delete=models.PROTECT, help_text="The TriggerExecution this execution information is about.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)

	problem = EnumField(PledgeExecutionProblem, default=PledgeExecutionProblem.NoProblem, help_text="A problem code associated with a failure to make any contributions for the pledge.")
	charged = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount the user's account was actually charged, in dollars and including fees. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates.")
	fees = models.DecimalField(max_digits=6, decimal_places=2, help_text="The fees the user was charged, in dollars.")
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	district = models.CharField(max_length=4, blank=True, null=True, db_index=True, help_text="The congressional district of the user (at the time of the pledge), in the form of XX00.")

	objects = NoMassDeleteManager()

	def __str__(self):
		return str(self.pledge)

	@transaction.atomic
	def delete(self, really=False, with_void=True):
		# We don't delete PledgeExecutions because they are transactional
		# records. And open Pledges will get executed again automatically,
		# so we can't simply void an execution by deleting this record.
		if not really:
			raise ValueError("Can't delete a PledgeExecution. (Set the 'really' flag internally.)")

		# But maybe in debugging/testing we want to be able to delete
		# a pledge execution, so....

		# Void this PledgeExecution, if needed.
		if self.problem == PledgeExecutionProblem.NoProblem:
			self.void(with_void=with_void)

		# Return the Pledge to the open state so we can try to execute again.
		self.pledge.status = PledgeStatus.Open
		self.pledge.save()

		# Decrement the TriggerExecution's pledge_count.
		te = self.pledge.trigger.execution
		te.pledge_count = models.F('pledge_count') - 1
		te.save(update_fields=['pledge_count'])

		# Delete record.
		super(PledgeExecution, self).delete()	

	def show_txn(self):
		import rtyaml
		from contrib.bizlogic import DemocracyEngineAPI
		txns = set(item['transaction_guid'] for item in self.extra['donation']['line_items'])
		for txn in txns:
			print(rtyaml.dump(DemocracyEngineAPI.get_transaction(txn)))

	@property
	def problem_text(self):
		if self.problem == PledgeExecutionProblem.EmailUnconfirmed:
			return "Your contribution was not made because you did not confirm your email address prior to the %s." \
				% self.pledge.trigger.trigger_type.strings['action_noun']
		if self.problem == PledgeExecutionProblem.TransactionFailed:
			return "There was a problem charging your credit card and making the contribution: %s. Your contribution could not be made." \
				% self.pledge.execution.extra['exception']
		if self.problem == PledgeExecutionProblem.FiltersExcludedAll:
			return "Your contribution was not made because there were no %s that met your criteria of %s." \
				% (self.pledge.trigger.trigger_type.strings['actors'], self.pledge.targets_summary)
		if self.problem == PledgeExecutionProblem.Voided:
			return "We cancelled your contribution per your request."

	@transaction.atomic
	def void(self, with_void=True):
		# A user has asked us to void a transaction.

		# Is there anything to void?
		if self.problem != PledgeExecutionProblem.NoProblem:
			raise ValueError("Can't void a pledge in state %s." % str(self.problem))
		if not self.extra["donation"]: # sanity check
			raise ValueError("Can't void a pledge that doesn't have an actual donation.")
		
		# Take care of database things first. Let any of these
		# things fail before we call out to DE.

		# Delete the contributions explicitly so that .delete() gets called (by our manager).
		self.contributions.all().delete()

		# Decrement the TriggerExecution's count of successful pledge executions
		# (incremented only for NoProblem executions).
		te = self.pledge.trigger.execution
		te.pledge_count_with_contribs = models.F('pledge_count_with_contribs') - 1
		te.save(update_fields=['pledge_count_with_contribs'])

		# Change the status of this PledgeExecution.
		de_don = self.extra['donation']
		self.extra['voided_donation'] = self.extra['donation']
		del self.extra['donation']
		self.problem = PledgeExecutionProblem.Voided
		self.save()

		# In debugging, we don't bother calling Democracy Engine to void
		# the transaction. It might fail if the record is very old.
		if not with_void:
			return

		# Void or refund the transaction. There should be only one, but
		# just in case get a list of all mentioned transactions for the
		# donation. Do this last so that if the void succeeds no other
		# error can follow.
		void = []
		txns = set(item['transaction_guid'] for item in de_don['line_items'])
		for txn in txns:
			# Raises an exception on failure.
			ret = void_pledge_transaction(txn, allow_credit=True)
			void.append(ret)

		# Store void result.
		self.extra['void'] = void
		self.save()

		return void

	@transaction.atomic
	def update_district(self, district, other):
		# lock so we don't overwrite
		self = PledgeExecution.objects.filter(id=self.id).select_for_update().get()

		# temporarily decrement all of the contributions from the aggregates
		for c in self.contributions.all():
			c.update_aggregates(factor=-1)

		self.district = district
		self.extra['geocode'] = other
		self.save(update_fields=['district', 'extra'])

		# re-increment now that the district is set
		for c in self.contributions.all():
			c.update_aggregates(factor=1)

class Tip(models.Model):
	"""A tip to an Organization made while making a Pledge."""

	user = models.ForeignKey('itfsite.User', blank=True, null=True, on_delete=models.PROTECT, help_text="The user making the Tip.")
	profile = models.ForeignKey(ContributorInfo, related_name="tips", on_delete=models.PROTECT, help_text="The contributor information (name, address, etc.) and billing information used for this Tip.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount of the tip, in dollars.")
	recipient = models.ForeignKey('itfsite.Organization', on_delete=models.PROTECT, help_text="The recipient of the tip.")

	de_recip_id = models.CharField(max_length=64, blank=True, null=True, db_index=True, help_text="The recipient ID on Democracy Engine that received the tip.")

	via_campaign = models.ForeignKey('itfsite.Campaign', blank=True, null=True, related_name="tips", on_delete=models.PROTECT, help_text="The Campaign that this Tip was made via.")
	via_pledge = models.OneToOneField(Pledge, blank=True, null=True, related_name="tip", on_delete=models.PROTECT, help_text="The executed Pledge that this Tip was made via.")
	ref_code = models.CharField(max_length=24, blank=True, null=True, db_index=True, help_text="An optional referral code that lead the user to take this action.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def save(self, *args, override_immutable_check=False, **kwargs):
		if self.id and not override_immutable_check:
			raise Exception("This model is immutable.")
		super().save(*args, **kwargs)

	@staticmethod
	def execute_from_pledge(pledge):
		# Validate.
		if not pledge.user: raise ValueError("Pledge was made by an unconfirmed user.")
		if pledge.tip_to_campaign_owner == 0: raise ValueError("Pledge does not specify a tip.")
		if not pledge.via_campaign.owner: raise ValueError("Campaign has no owner.")
		if not pledge.via_campaign.owner.de_recip_id: raise ValueError("Campaign owner has no recipient id.")

		# Create instance.
		tip = Tip()

		tip.user = pledge.user
		tip.profile = pledge.profile

		tip.amount = pledge.tip_to_campaign_owner

		tip.via_pledge = pledge
		tip.via_campaign = pledge.via_campaign
		tip.recipient = pledge.via_campaign.owner
		tip.de_recip_id = pledge.via_campaign.owner.de_recip_id

		tip.extra = {
			"donation": None,
			"exception": "Not yet executed.",
		}

		tip.execute() # also saves

		return tip

	def execute(self):
		import rtyaml
		from contrib.bizlogic import create_de_donation_basic_dict, DemocracyEngineAPI

		# Prepare the donation record for authorization & capture.
		de_don_req = create_de_donation_basic_dict(self.via_pledge)
		de_don_req.update({
			# billing info
			"token": self.profile.extra['billing']['de_cc_token'],

			# line items
			"line_items": [{
				"recipient_id": self.de_recip_id,
				"amount": DemocracyEngineAPI.format_decimal(self.amount),
				}],

			# reported to the recipient
			"source_code": self.via_campaign.get_short_url(),
			"ref_code": "",

			# tracking info for internal use
			"aux_data": rtyaml.dump({ # DE will gives this back to us encoded as YAML, but the dict encoding is ruby-ish so to be sure we can parse it, we'll encode it first
				"via": self.via_campaign.id,
				"pledge": self.via_pledge.id,
				"user": self.user.id,
				"email": self.user.email,
				"pledge_created": self.via_pledge.created,
				})
			})

		# Create the 'donation', which creates a transaction and performs cc authorization.
		try:
			don = DemocracyEngineAPI.create_donation(de_don_req)
			self.extra["donation"] = don
			self.extra["exception"] = None
		except HumanReadableValidationError as e:
			self.extra["exception"] = str(e)

		self.save()

#####################################################################
#
# Recipients and Contributions
#
# Actual campaign contributions made.
#
#####################################################################

class Recipient(models.Model):
	"""A contribution recipient, with the current Democracy Engine recipient ID, which is either an Actor (an incumbent) or a logically specified general election candidate by office sought and party."""

	de_id = models.CharField(max_length=64, unique=True, help_text="The Democracy Engine ID that we have assigned to this recipient.")
	active = models.BooleanField(default=True, help_text="Whether this Recipient can currently receive funds.")

	actor = models.OneToOneField(Actor, blank=True, null=True, help_text="The Actor that this recipient corresponds to (i.e. this Recipient is an incumbent).")

	office_sought = models.CharField(max_length=7, blank=True, null=True, db_index=True, help_text="For challengers, a code specifying the office sought in the form of 'S-NY-I' (New York class 1 senate seat) or 'H-TX-30' (Texas 30th congressional district). Unique with party.")
	party = EnumField(ActorParty, blank=True, null=True, help_text="The party of the challenger, or null if this Recipient is for an incumbent. Unique with office_sought.")

	class Meta:
		unique_together = [('office_sought', 'party')]

	def __str__(self):
		if self.actor:
			# is an incumbent
			return str(self.actor)
		else:
			try:
				# is a currently challenger of someone
				return self.party.name + " Challenger to " + str(self.challenger_to) + " (" + self.office_sought + ")"
			except:
				# is not a current challenger of someone, so just use office/party designation
				return self.office_sought + ":" + str(self.party)

	@property
	def is_challenger(self):
		return self.actor is None

class Contribution(models.Model):
	"""A fully executed campaign contribution."""

	pledge_execution = models.ForeignKey(PledgeExecution, related_name="contributions", on_delete=models.PROTECT, help_text="The PledgeExecution this execution information is about.")
	action = models.ForeignKey(Action, on_delete=models.PROTECT, help_text="The Action this contribution was made in reaction to.")
	recipient = models.ForeignKey(Recipient, related_name="contributions", on_delete=models.PROTECT, help_text="The Recipient this contribution was sent to.")
	amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The amount of the contribution, in dollars.")
	refunded_time = models.DateTimeField(blank=True, null=True, help_text="If the contribution was refunded to the user, the time that happened.")

	de_id = models.CharField(max_length=64, help_text="The Democracy Engine ID that the contribution was assigned to.")

	extra = JSONField(blank=True, help_text="Additional information about the contribution.")

	objects = NoMassDeleteManager()

	class Meta:
		unique_together = [('pledge_execution', 'action'), ('pledge_execution', 'recipient')]

	def __str__(self):
		return "$%0.2f to %s for %s" % (self.amount, self.recipient, self.pledge_execution)

	def name_long(self):
		if not self.recipient.is_challenger:
			# is an incumbent
			return self.action.name_long
		else:
			# is a challenger, but who it was a challenger to may be different
			# from who the recipient is a challenger to now, so use the action
			# to get the name of the incumbent.
			return self.recipient.party.name + " Challenger to " + self.action.name_long

	@transaction.atomic
	def delete(self):
		# Delete this object. You almost certainly do NOT want to do this
		# since the transaction line item will remain on the Democracy
		# Engine side.

		# Decrement the TriggerExecution and Action's total_pledged fields.
		self.update_aggregates(factor=-1)

		# Remove record.
		super(Contribution, self).delete()	

	def update_aggregates(self, factor=1, updater=None):
		# Increment the totals on the Action instance. This excludes fees because
		# this is based on transaction line items.
		if not self.recipient.is_challenger:
			# Contribution was to the Actor.
			field = 'total_contributions_for'
		else:
			# Contribution was to the Actor's opponent.
			field = 'total_contributions_against'
		setattr(self.action, field, models.F(field) + self.amount*factor)
		self.action.save(update_fields=[field])

		# Increment the TriggerExecution's total_contributions. Likewise, it
		# excludes fees.
		self.action.execution.total_contributions = models.F('total_contributions') + self.amount*factor
		self.action.execution.num_contributions = models.F('num_contributions') + 1*factor
		self.action.execution.save(update_fields=['total_contributions', 'num_contributions'])

		# Increment the cached ContributionAggregates that this Contribution
		# gets aggregated in.
		self.update_contributionaggregates(factor=factor, updater=updater)

	def update_contributionaggregates(self, factor=1, updater=None):
		# Increment the cached ContributionAggregates that this Contribution
		# gets aggregated in, in the order of the CONTRIBUTION_AGGREGATE_FIELDS array.
		if updater is None: updater = ContributionAggregate.Updater(buffered=False)

		def update(**fields):
			d = tuple([ fields.get(k) for k in CONTRIBUTION_AGGREGATE_FIELDS ])
			updater.add(d, 1*factor, self.amount*factor)

		for kw in [
			{},
			{ "trigger_execution": self.action.execution },
			{ "trigger_execution": self.action.execution, "via_campaign": self.pledge_execution.pledge.via_campaign },
		]:
			update(**kw)
			if "trigger_execution" in kw:
				update(outcome=self.pledge_execution.pledge.desired_outcome, **kw)
			update(actor=self.action.actor, incumbent=not self.recipient.is_challenger, **kw)
			update(incumbent=not self.recipient.is_challenger, **kw)
			update(party=self.action.party if not self.recipient.is_challenger else self.recipient.party, **kw)



CONTRIBUTION_AGGREGATE_FIELDS = (
	'trigger_execution',
	'via_campaign',
	'outcome',
	'actor',
	'incumbent',
	'party',
	'district',
	)
class ContributionAggregate(models.Model):
	"""Aggregate totals for various slices of contributions."""

	updated = models.DateTimeField(auto_now=True, db_index=True)

	trigger_execution = models.ForeignKey(TriggerExecution, blank=True, null=True, related_name='contribution_aggregates', on_delete=models.CASCADE, help_text="The TriggerExecution that these cached statistics are about.")
	via_campaign = models.ForeignKey('itfsite.Campaign', blank=True, null=True, on_delete=models.CASCADE, help_text="The Campaign that the Pledges were made via.")
	outcome = models.IntegerField(blank=True, null=True, help_text="The outcome index that was taken. Null if the slice encompasses all outcomes.")
	actor = models.ForeignKey(Actor, blank=True, null=True, on_delete=models.CASCADE, help_text="The Actor who caused the Action that the contribution was made about. The contribution may have gone to an opponent.")
	incumbent = models.NullBooleanField(blank=True, null=True, help_text="Whether the contribution was to the Actor (True) or the Actor's challenger (False).")
	party = EnumField(ActorParty, blank=True, null=True, help_text="The party of the Recipient.")
	district = models.CharField(max_length=4, blank=True, null=True, help_text="The congressional district of the user (at the time of the pledge), in the form of XX00. Null if the slice encompasses all district.")

	count = models.IntegerField(default=0, help_text="A cached total count of campaign contributions executed in this slice.")
	total = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="A cached total dollar amount of campaign contributions executed in this slice, excluding fees.")

	class Meta:
		unique_together = [CONTRIBUTION_AGGREGATE_FIELDS]

	def __str__(self):
		return "%d | %s %s %s %s %s %s" % (self.trigger_execution_id, self.via_campaign, self.outcome, self.actor_id, self.incumbent, self.party, self.district)

	class Updater(object):
		def __init__(self, buffered=True):
			self.buffered = buffered
			self.buffer = { }
		def add(self, fields, count, total):
			if fields not in self.buffer:
				self.buffer[fields] = { 'count': 0, 'total': decimal.Decimal(0) }
			self.buffer[fields]['count'] += count
			self.buffer[fields]['total'] += total
			if not self.buffered or len(self.buffer) > 10000:
				self.sync()
		def sync(self):
			for fields, values in self.buffer.items():
				self.sync_item(fields, values['count'], values['total'])
			self.buffer.clear()
		def sync_item(self, fields, count, total):
			agg, is_new = ContributionAggregate.objects.get_or_create(
				defaults={ 'count': count, 'total': total },
				**dict(zip(CONTRIBUTION_AGGREGATE_FIELDS, fields)))
			if not is_new:
				agg.count = models.F('count') + count
				agg.total = models.F('total') + total
				agg.save(update_fields=['count', 'total'])

	@staticmethod
	def get_slice(**slce):
		# Returns a single slice. Whatever fields the caller
		# hasn't specifically requested get filled in with
		# None, which represents the aggregate across all
		# values. Otherwise we'd be requesting multiple
		# ContributionAggregate instances.
		#
		# Return a dict { "count": __, "total": __ } to match
		# how get_slices returns a list of dicts via .values().
		for f in slce:
			if f not in CONTRIBUTION_AGGREGATE_FIELDS:
				raise ValueError(f)
		slce = dict(slce)
		for field in CONTRIBUTION_AGGREGATE_FIELDS:
			if field not in slce:
				slce[field] = None
		try:
			ca = ContributionAggregate.objects.get(**slce)
			return { "count": ca.count, "total": ca.total }
		except ContributionAggregate.DoesNotExist:
			return { "count": 0, "total": 0 }

	@staticmethod
	def get_slices(*across, **slce):
		# Returns a list of ContributionAggregates that match the
		# slce values. For any field not mentioned in slce or
		# across, fill it in with None so we get aggregates
		# across those values. The fields in across are the ones
		# the caller wants particular aggregates for, and for
		# those we must *exclude* None because that represents
		# the aggregate for all of those values.

		# sanity check
		if len(across) == 0: raise ValueError("Must specify at least one 'across' column.")
		for f in list(slce) + list(across):
			if f not in CONTRIBUTION_AGGREGATE_FIELDS:
				raise ValueError(f)

		# build the filters
		slce = dict(slce)
		for field in CONTRIBUTION_AGGREGATE_FIELDS:
			if field not in slce and field not in across:
				slce[field] = None
		c = ContributionAggregate.objects.filter(**slce)
		for f in across: # must use separate 'exclude' calls
			c = c.exclude(**{f: None})

		# sort descending by total
		c = c.order_by('-total')

		# fetch all
		ret = list(c.values('count', 'total', *across))

		# if actors were requested, pre-fetch objects
		actors = Actor.objects.in_bulk(rec['actor'] for rec in ret if 'actor' in rec)

		# if actors were requested add Action instances
		actions = { }
		if slce.get('trigger_execution') and len(actors) > 0:
			actions = Action.objects.filter(execution=slce['trigger_execution']).select_related('execution__trigger')
			actions = { action.actor_id: action for action in actions }

		# if outcome was requested, add outcome labels
		if 'outcome' in across and slce.get('trigger_execution'):
			outcome_strings = slce['trigger_execution'].trigger.outcome_strings()
			if slce.get('via_campaign'):
				# Get outcome strings from any TriggerCustomization, if there is one.
				tcust = TriggerCustomization.objects.filter(owner=slce['via_campaign'].owner, trigger=slce['trigger_execution'].trigger).first()
				if tcust:
					outcome_strings = tcust.outcome_strings()

		# turn integers from .values() back into objects
		for rec in ret:
			if 'actor' in rec:
				rec['actor'] = actors[rec['actor']]
				if slce.get('trigger_execution'):
					rec['action'] = actions[rec['actor'].id]

			if 'party' in rec:
				rec['party'] = ActorParty(rec['party'])
			if 'outcome' in rec and slce.get('trigger_execution'):
				rec['label'] = outcome_strings[rec['outcome']]['label']
		
		return ret

	@staticmethod
	@transaction.atomic
	def rebuild():
		# import tqdm if we have it for a nice console progress bar
		try:
			from tqdm import tqdm
		except:
			tqdm = lambda x : x

		# utility function to page through objects
		def iterate(qs, chunksize=5000):
			import gc
			pk = 0
			last_pk = qs.order_by('-pk')[0].pk
			qs = qs.order_by('pk')
			while pk < last_pk:
				for row in qs.filter(pk__gt=pk)[:chunksize].iterator():
					pk = row.pk
					yield row
				gc.collect()

		# Delete all ContributionAggregate objects.
		ContributionAggregate.objects.all().delete()

		# Start incrementing new ones.
		updater = ContributionAggregate.Updater()

		iter = Contribution.objects.all().select_related('action__execution', 'pledge_execution__pledge__via_campaign', 'pledge_execution__pledge', 'action', 'action__actor', 'recipient', 'pledge_execution')
		for c in tqdm(iterate(iter), total=Contribution.objects.count()):
			c.update_contributionaggregates(updater=updater)

		updater.sync()

