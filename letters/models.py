from django.db import models
from contrib.models import TextFormat

import enum
from enum3field import EnumField, django_enum
from itfsite.models import Organization
from itfsite.utils import JSONField

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

	# Who gets the letters?
	target_senators = models.BooleanField(default=True, help_text="Target letters to senators.")
	target_representatives = models.BooleanField(default=True, help_text="Target letters to representatives.")

	# Additional data.
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	# METHODS

	def __str__(self):
		return "LettersCampaign(%d, %s)" % (self.id, repr(self.title))

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
		return ' '.join(self.extra[k] for k in ('nameFirst', 'nameLast'))

	@property
	def address(self):
		return ', '.join(self.extra[k] for k in ('addressCity', 'addressState'))

	def same_as(self, other):
		import json
		def normalize(data): return json.dumps(data, sort_keys=True)
		return (normalize(self.extra) == normalize(other.extra))

	def geocode(self):
		# Updates this record with geocoder information, especially congressional district
		# and timezone.
		from contrib.legislative import geocode
		info = geocode([
			self['addressAddress'],
			self['addressCity'],
			self['addressState'],
			self['addressZip']])
		self.extra['geocode'] = info
		self.is_geocoded = True
		self.save(update_fields=['is_geocoded', 'extra'], override_immutable_check=True)

	@staticmethod
	def createRandom():
		# For testing!
		import random
		return ConstituentInfo.objects.create(extra={
			"nameFirst": random.choice(["Jeanie", "Lucrecia", "Marvin", "Jasper", "Carlo", "Millicent", "Zack", "Raul", "Johnny", "Margarette"]),
			"nameLast": random.choice(["Ramm", "Berns", "Wannamaker", "McCarroll", "Bumbrey", "Caudle", "Bridwell", "Pacelli", "Crowley", "Montejano"]),
			"addressAddress": "%d %s %s" % (random.randint(10, 200), random.choice(["Fir", "Maple", "Cedar", "Dogwood", "Persimmon", "Beech"]), random.choice([ "St", "Ave", "Ct"])),
			"addressCity": random.choice(["Rudy", "Hookerton", "La Ward", "Marenisco", "Nara Visa"]),
			"addressState": random.choice(["NQ", "BL", "PS"]),
			"addressZip": random.randint(10000, 88888),
		})

class UserLetter(models.Model):
	"""A letter written by a user."""

	# User.
	user = models.ForeignKey('itfsite.User', blank=True, null=True, on_delete=models.PROTECT, help_text="The user writing the letter. When an anonymous user writes a letter, this is null, the user's email address is stored instead.")
	email = models.EmailField(max_length=254, blank=True, null=True, help_text="When an anonymous user writes a letter, their email address is stored here.")
	profile = models.ForeignKey(ConstituentInfo, related_name="letters", on_delete=models.PROTECT, help_text="The user's information (name, address, etc.).")

	# Source.
	letterscampaign = models.ForeignKey(LettersCampaign, related_name="letters", on_delete=models.PROTECT, help_text="The LettersCampaign that this UserLetter was written for.")
	via_campaign = models.ForeignKey('itfsite.Campaign', blank=True, null=True, related_name="userletters", on_delete=models.PROTECT, help_text="The Campaign that this UserLetter was made via.")
	ref_code = models.CharField(max_length=24, blank=True, null=True, db_index=True, help_text="An optional referral code that lead the user to take this action.")

	# Delivery.
	congressional_district = models.CharField(max_length=4, help_text="The user's congressional district in the form of XX##, e.g. AK00, at the time of submitting the letter, which determines who should receive the letter.")
	submitted = models.BooleanField(default=False, help_text="Whether this letter was submitted to our delivery vendor.")

	# Additional data.
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = [('letterscampaign', 'user'), ('letterscampaign', 'email')]
