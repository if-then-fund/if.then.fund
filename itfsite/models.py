from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.template import Template, Context

from itfsite.accounts import User, NotificationsFrequency
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
	C4 = 2 # a 501c4
	Company = 3 # a corporation/LLC

	def slug(self):
		if self == OrganizationType.User: return "user"
		if self == OrganizationType.C4: return "org"
		if self == OrganizationType.Company: return "org"
		raise ValueError()

	def display(self):
		if self == OrganizationType.User: return "User"
		if self == OrganizationType.C4: return "Nonprofit Organization"
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

	banner_image = models.ImageField(upload_to='org-banner-image', blank=True, null=True, help_text="A raw image to display for this organization's banner image.")

	website_url = models.URLField(max_length=256, blank=True, null=True, help_text="The URL to this organization's website.")
	facebook_url = models.URLField(max_length=256, blank=True, null=True, help_text="The URL to this organization's Facebook Page.")
	twitter_handle = models.CharField(max_length=64, blank=True, null=True, help_text="The organization's Twitter handle (omit the @-sign).")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def __str__(self):
		return "%s [%d]" % (self.name, self.id)

	def get_absolute_url(self):
		return "/%s/%d/%s" % (self.orgtype.slug(), self.id, self.slug)

	def banner_image_url(self):
		try:
			return self.banner_image.url
		except ValueError:
			# FieldFields raise a ValueError if the field isn't associated with a file
			return self.get_absolute_url() + '/_banner'

@django_enum
class NotificationType(enum.Enum):
	TriggerRecommendation = 1

class Notification(models.Model):
	"""A notification that we want to show to a user."""

	user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE, help_text="The user the notification is sent to.")
	notif_type = EnumField(NotificationType, help_text="The type of the notiication.")
	source_content_type = models.ForeignKey(ContentType, help_text="The content type of the object generating the notiication.")
	source_object_id = models.PositiveIntegerField(help_text="The primary key of the object generating the notiication.")
	source = GenericForeignKey('source_content_type', 'source_object_id')

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	dismissed_at = models.DateTimeField(blank=True, null=True, help_text="Whether and when the notification was dismissed by the user by.")
	mailed_at = models.DateTimeField(blank=True, null=True, help_text="Whether and when the notification was sent to the user by email.")
	clicked_at = models.DateTimeField(blank=True, null=True, help_text="Whether and when the notification was clicked on by the user to see more information.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	class Meta:
		unique_together = [('user', 'notif_type', 'source_content_type', 'source_object_id')]
		index_together = [('user', 'created')]

	def __str__(self):
		return ", ".join([self.created.isoformat(), str(self.user), self.notif_type.name, str(self.source)])

	def dismiss(self):
		self.dismissed_at = timezone.now()
		self.save()

	@staticmethod
	def render(qs, for_client=True):
		# Get JSON-able data so the client can render the user's notifications.
		notifications = list(qs)

		# Get a unique set of classes that manage these notifications.
		classes = set(n.source_content_type.model_class() for n in notifications)

		# Ask each class to render the notifications it is responsible for
		# into one or more alerts.
		alerts = sum([c.render_notifications(set(n for n in notifications if n.source_content_type.model_class() == c))
			for c in classes], [])

		for alert in alerts:
			# Render the alert content.
			alert["body_html"] = Template(alert["body_html"]).render(Context(alert["body_context"]))
			alert["body_text"] = Template(alert["body_text"]).render(Context(alert["body_context"]))

			# Add common properties derived from the notifications that underlie the alerts.
			alert["date"] = max(n.created for n in alert['notifications']) # most recent notification
			if for_client: alert["date"] = alert["date"].isoformat()
			alert["ids"] = [n.id for n in alert['notifications']]
			alert["new"] = any(n.dismissed_at is None for n in alert['notifications'])
			if for_client: del alert["notifications"] # not JSON-serializable

		# Sort the alerts.
		alerts.sort(key = lambda a : a['date'], reverse=True)

		# Return.
		return alerts
