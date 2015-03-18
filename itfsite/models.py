from django.db import models

from itfsite.accounts import User
from contrib.models import TextFormat

import enum
from enum3field import EnumField, django_enum

from jsonfield import JSONField as _JSONField
class JSONField(_JSONField):
	# turns on sort_keys
    def __init__(self, *args, **kwargs):
        super(_JSONField, self).__init__(*args, dump_kwargs={"sort_keys": True}, **kwargs)

@django_enum
class OrganizationType(enum.Enum):
	User = 1 # any user can create an 'organization'
	C3 = 2 # a 501c3
	Company = 3 # a corporation/LLC

	def slug(self):
		if self == OrganizationType.User: return "user"
		if self == OrganizationType.C3: return "org"
		if self == OrganizationType.Company: return "org"
		raise ValueError()

	def display(self):
		if self == OrganizationType.User: return "User"
		if self == OrganizationType.C3: return "Nonprofit Organization"
		if self == OrganizationType.Company: return "Company"
		raise ValueError()

class Organization(models.Model):
	"""An organization can be the owner of Triggers and TriggerCustomizations."""

	name = models.CharField(max_length=200, help_text="The name of the Organization.")
	slug = models.SlugField(max_length=200, help_text="The unique URL slug for this Organization.")
	orgtype = EnumField(OrganizationType, help_text="The type of the organization.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	description = models.TextField(help_text="Description text in the format given by description_format.")
	description_format = EnumField(TextFormat, help_text="The format of the description text.")

	website_url = models.URLField(max_length=256, blank=True, null=True, help_text="The URL to this organization's website.")
	facebook_url = models.URLField(max_length=256, blank=True, null=True, help_text="The URL to this organization's Facebook Page.")
	twitter_handle = models.CharField(max_length=64, blank=True, null=True, help_text="The organization's Twitter handle (omit the @-sign).")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def __str__(self):
		return "%s [%d]" % (self.name, self.id)

	def get_absolute_url(self):
		return "/%s/%d/%s" % (self.orgtype.slug(), self.id, self.slug)

