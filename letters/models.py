from django.db import models
from django.utils import timezone
from django.conf import settings

import enum
from enum3field import EnumField, django_enum
from itfsite.models import Organization
from itfsite.utils import JSONField
from contrib.models import TextFormat, NoMassDeleteManager

@django_enum
class CampaignStatus(enum.Enum):
	Draft = 0
	Open = 1
	Paused = 2
	Closed = 3

class LettersCampaign(models.Model):
	"""A letter writing campaign."""

	# Metadata
	title = models.CharField(max_length=200, help_text="The title for the campaign.")
	status = EnumField(CampaignStatus, default=CampaignStatus.Draft, help_text="The current status of the campaign.")
	owner = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.PROTECT, related_name="letters_campaigns", help_text="The user/organization which owns the campaign. Null if the campaign is created by us.")

	# Content.
	message_subject = models.CharField(max_length=100, help_text="The subject of the message. Used in message delivery.")
	message_body = models.TextField(help_text="The body of the message sent to legislators. Rendered as if Markdown when previewing for users.")

	# Who gets the letters?
	target_senators = models.BooleanField(default=True, help_text="Target letters to senators.")
	target_representatives = models.BooleanField(default=True, help_text="Target letters to representatives.")

	# Body depends on an Actor's position on an issue.
	body_toggles_on = models.ForeignKey('contrib.Trigger', blank=True, null=True, on_delete=models.PROTECT, help_text="Use alternate body text if the target has a known position on this issue, based on a TriggerExecution.")
	message_subject0 = models.CharField(max_length=100, blank=True, null=True, help_text="The subject of the message, as in message_subject, for when the target has outcome 0 in the body_toggles_on trigger.")
	message_body0 = models.TextField(blank=True, null=True, help_text="The body of the message, as in message_body, for when the target has outcome 0 in the body_toggles_on trigger.")
	message_subject1 = models.CharField(max_length=100, blank=True, null=True, help_text="The subject of the message, as in message_subject, for when the target has outcome 1 in the body_toggles_on trigger.")
	message_body1 = models.TextField(blank=True, null=True, help_text="The body of the message, as in message_body, for when the target has outcome 1 in the body_toggles_on trigger.")

	# Additional data.
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	# METHODS

	def __str__(self):
		return "LettersCampaign(%d, %s)" % (self.id, repr(self.title))

	def sample_honorific(self):
		if self.target_representatives:
			return "representative"
		else:
			return "senator"

@django_enum
class VoterRegistrationStatus(enum.Enum):
	# This is persisted using the name as a string key. The
	# value is used for display.
	Registered = "I am registered to vote."
	Registering = "I will register to vote soon."
	NotRegistered = "I am not registered to vote."
	TooYoung = "I am too young to register to vote."

	# When modifying the names here, be sure to update
	# get_extended_target_info.

class ConstituentInfo(models.Model):
	"""Information about a user used for letter delivery. Stored schema-less in the extra field. May be shared across UserLetters of the same user. Instances are immutable."""

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	is_geocoded = models.BooleanField(default=False, db_index=True, help_text="Whether this record has been geocoded.")
	extra = JSONField(blank=True, help_text="Schemaless data stored with this object.")

	def __str__(self):
		return "[%d] %s %s" % (self.id, self.name, self.address)

	def save(self, *args, override_immutable_check=False, **kwargs):
		if self.id and not override_immutable_check:
			raise Exception("This model is immutable.")
		super(ConstituentInfo, self).save(*args, **kwargs)

	@property
	def name(self):
		return ' '.join(self.extra['name'][k] for k in ('nameFirst', 'nameLast'))

	@property
	def address(self):
		return ', '.join(self.extra['address'][k] for k in ('addrCity', 'addrState'))

	def same_as(self, other):
		import json
		def normalize(data): return json.dumps(data, sort_keys=True)
		return (normalize(self.extra) == normalize(other.extra))

class UserLetter(models.Model):
	"""A letter written by a user."""

	# User.
	user = models.ForeignKey('itfsite.User', blank=True, null=True, on_delete=models.PROTECT, help_text="The user writing the letter. When an anonymous user writes a letter, this is null, the user's email address is stored instead.")
	anon_user = models.ForeignKey('itfsite.AnonymousUser', blank=True, null=True, on_delete=models.CASCADE, help_text="When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.")
	profile = models.ForeignKey(ConstituentInfo, related_name="letters", on_delete=models.PROTECT, help_text="The user's information (name, address, etc.).")

	# Source.
	letterscampaign = models.ForeignKey(LettersCampaign, related_name="letters", on_delete=models.PROTECT, help_text="The LettersCampaign that this UserLetter was written for.")
	via_campaign = models.ForeignKey('itfsite.Campaign', blank=True, null=True, related_name="userletters", on_delete=models.PROTECT, help_text="The Campaign that this UserLetter was made via.")
	ref_code = models.CharField(max_length=24, blank=True, null=True, db_index=True, help_text="An optional referral code that lead the user to take this action.")

	# Delivery.
	congressional_district = models.CharField(max_length=4, help_text="The user's congressional district in the form of XX##, e.g. AK00, at the time of submitting the letter, which determines who should receive the letter.")
	pending = models.IntegerField(default=0, help_text="The number of messages pending submission.")
	delivered = models.IntegerField(default=0, help_text="The number of messages that have been submitted for delivery.")

	# Additional data.
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = [('letterscampaign', 'user'), ('letterscampaign', 'anon_user')]

	objects = NoMassDeleteManager()

	def delete(self):
		if self.delivered > 0:
			raise ValueError("Cannot delete a UserLetter once any of its messages have been submitted for delivery.")
		super(UserLetter, self).delete()	

	def get_absolute_url(self):
		return self.via_campaign.get_absolute_url()

	def get_email(self):
		if self.user:
			return self.user.email
		else:
			return self.anon_user.email

	@property
	def submission_status(self):
		if self.pending == 0:
			return "has been sent"
		else:
			return "will be sent"

	@property
	def submission_status_short(self):
		if self.pending == 0:
			return "Sent"
		else:
			return "Pending"

	@property
	def indented_recipients(self):
		def nice_list(items):
			if len(items) <= 1:
				return "".join(items)
			elif len(items) == 2:
				return items[0] + " and " + items[1]
			else:
				return ", ".join(items[0:-1]) + " and " + items[-1]

		recips = [ m["target_name"] for m in self.extra.get("messages", []) ]
		return nice_list(recips)

	def set_confirmed_user(self, user, request):
		from django.contrib import messages
		if self.letterscampaign.letters.filter(user=user).exists():
			messages.add_message(request, messages.ERROR, 'You already wrote a letter on this subject.')
			self.delete() # else we will try to confirm the email address indefinitely, but the AnonymousUser for this is already confirmed, so it would be an error
			return

		# Move this anonymous action to the user's account.
		self.user = user
		self.anon_user = None
		self.save(update_fields=['user', 'anon_user'])

		# Let the user know what happened.
		messages.add_message(request, messages.SUCCESS, 'Your letter regarding %s %s.'
			% (self.letterscampaign.title, self.submission_status))


	def submit_for_delivery(self):
		from .views import votervoice
		import requests

		if self.delivered > 0:
			raise Exception("Some of the messages have already been delivered.")

		now = timezone.now().isoformat()
		postdata = {
			"association": settings.VOTERVOICE_ASSOCIATION,
			"userId": self.profile.extra['votervoice']['user']['userId'],
			"messages": [m["votervoice_response"] for m in self.extra["messages"]],
			"signature": self.profile.name,
			"defaultAddressType": "H"
		}

		try:
			ret = votervoice("POST", "advocacy/responses", {
					"user": self.profile.extra['votervoice']['user']['userToken'],
				},
				postdata)
		except requests.HTTPError as e:
			# Error in submission.
			self.extra.setdefault("delivery_status", []).append({
				"when": now,
				"error": e.response.text,
				"postdata": postdata,
			})
			self.save()
			return

		# Submission succeeded.
		self.extra.setdefault("delivery_status", []).append({
			"when": now,
			"success": ret,
			"postdata": postdata,
		})
		self.pending = 0
		self.delivered = len(self.extra["messages"])
		self.save()
