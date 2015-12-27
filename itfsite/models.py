from django.db import models, transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.template import Template, Context
from django.conf import settings
from django.http import Http404

from itfsite.accounts import User, NotificationsFrequency, AnonymousUser
from contrib.models import TextFormat

import enum
from enum3field import EnumField, django_enum
from itfsite.utils import JSONField

#####################################################################
#
# Organizations and Campaigns
#
#####################################################################

from .middleware import load_brandings
load_brandings()

@django_enum
class OrganizationType(enum.Enum):
	User = 1 # any user can create an 'organization'
	C4 = 2 # a 501c4
	Company = 3 # a corporation/LLC
	ItfBrand = 4 # us under one of our brands besides if.then.fund

	def slug(self):
		if self == OrganizationType.User: return "user"
		if self == OrganizationType.C4: return "org"
		if self == OrganizationType.Company: return "org"
		if self == OrganizationType.ItfBrand: return "org"
		raise ValueError()

	def display(self):
		if self == OrganizationType.User: return "User"
		if self == OrganizationType.C4: return "Nonprofit Organization"
		if self == OrganizationType.Company: return "Company"
		if self == OrganizationType.ItfBrand: return "Company"
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

	profile_image = models.ImageField(blank=True, null=True, upload_to="campaign-media", help_text="The logo or headshot to display as the profile picture on the organization's page, and the default og:image (for Facebook and Twitter posts) if og_image is not provided. At least 120px x 120px and must be square.")
	og_image = models.ImageField(blank=True, null=True, upload_to="campaign-media", help_text="The og:image (for Facebook and Twitter posts) for the organization's profile page and the default og:image for the organization's campaigns. At least 120px x 120px and must be square.")
	banner_image = models.ImageField(upload_to='org-banner-image', blank=True, null=True, help_text="This organization's banner image. Should be about 1300px wide and at least 500px tall, but the image will be resized and cropped as necessary.")

	website_url = models.URLField(max_length=256, blank=True, null=True, help_text="The URL to this organization's website.")
	facebook_url = models.URLField(max_length=256, blank=True, null=True, help_text="The URL to this organization's Facebook Page.")
	twitter_handle = models.CharField(max_length=64, blank=True, null=True, help_text="The organization's Twitter handle (omit the @-sign).")

	de_recip_id = models.CharField(max_length=64, blank=True, null=True, help_text="The recipient ID on Democracy Engine for taking tips.")

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def __str__(self):
		return "%s [%d]" % (self.name, self.id)

	@property
	def is_real(self):
		return self.orgtype != OrganizationType.ItfBrand

	def get_absolute_url(self):
		return "/%s/%d/%s" % (self.orgtype.slug(), self.id, self.slug)

	def open_campaigns(self):
		return self.campaigns.filter(status=CampaignStatus.Open)

@django_enum
class CampaignStatus(enum.Enum):
	Draft = 0
	Open = 1
	Paused = 2
	Closed = 3

class Campaign(models.Model):
	"""A call to action."""

	# Metadata
	brand = models.IntegerField(default=1, choices=settings.BRAND_CHOICES, help_text="Which multi-brand site does this campaign appear on.")
	title = models.CharField(max_length=200, help_text="The title for the campaign.")
	slug = models.SlugField(max_length=200, help_text="The URL slug for this campaign.")
	subhead = models.TextField(help_text="Short sub-heading text for use in list pages and the meta description tag, in the format given by subhead_format.")
	subhead_format = EnumField(TextFormat, default=TextFormat.Markdown, help_text="The format of the subhead and image_credit text.")
	status = EnumField(CampaignStatus, default=CampaignStatus.Draft, help_text="The current status of the campaign.")
	owner = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.PROTECT, related_name="campaigns", help_text="The user/organization which owns the campaign. Null if the campaign is created by us.")

	# Content
	headline = models.CharField(max_length=256, help_text="Headline text for the page.")
	og_image = models.ImageField(blank=True, null=True, upload_to="campaign-media", help_text="The og:image (for Facebook and Twitter posts) for the campaign. At least 120px x 120px and must be square. If not set and the campaign has an owner, then the owner's og:image is used.")
	splash_image = models.ImageField(blank=True, null=True, upload_to="campaign-media", help_text="The big image to display behind the main call to action. Should be about 1300px wide and at least 500px tall, but the image will be resized and cropped as necessary.")
	image_credit = models.TextField(blank=True, null=True, help_text="Image credit, in the same format as the subhead.")
	body_text = models.TextField(help_text="Body text, in the format given by body_format.")
	body_format = EnumField(TextFormat, default=TextFormat.Markdown, help_text="The format of the body_text field.")

	# Actions.
	contrib_triggers = models.ManyToManyField('contrib.Trigger', blank=True, related_name="campaigns", help_text="Triggers to offer the user to take action on (or to show past actions).")
	letters = models.ManyToManyField('letters.LettersCampaign', blank=True, related_name="campaigns", help_text="LettersCampaigns to offer the user to take action on (or to show past actions).")

	# Additional data.
	extra = JSONField(blank=True, help_text="Additional information stored with this object.")
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	# METHODS

	def __str__(self):
		return "Campaign(%d, %s)" % (self.id, repr(self.title))

	def get_absolute_url(self):
		return "/a/%d/%s%s" % (self.id, (self.owner.slug + "-") if (self.owner and self.owner.is_real) else "", self.slug)

	def get_short_url(self):
		return settings.SITE_ROOT_URL + ("/a/%d" % self.id)

	def get_active_letters_campaign(self):
		from letters.models import CampaignStatus as LettersCampaignStatus
		return self.letters.filter(status=LettersCampaignStatus.Open).order_by('-created').first()

	def contrib_triggers_with_tcust(self):
		return [
			(t, t.customizations.filter(owner=self.owner).first())
			for t in self.contrib_triggers.all()
		]

	def is_sole_trigger(self, trigger):
		return self.contrib_triggers.count() == 1 and self.contrib_triggers.filter(id=trigger.id).exists()

	def get_contrib_totals(self):
		# Get all of the displayable totals for this campaign.

		ret = { }

		from django.db.models import Sum, Count
		from contrib.models import TriggerStatus, TriggerCustomization, Pledge, PledgeExecution, PledgeExecutionProblem

		# What pledges should we show? For consistency across stats, filter out unconfirmed
		# pledges and pledges made after the trigger was executed, which shouldn't be shown
		# as a "pledge" per se --- those will be executed soon.
		pledges_base = Pledge.objects.exclude(user=None).filter(made_after_trigger_execution=False)
		if self.owner:
			# When we're showing a campaign owned by an organization, then we
			# only count pledges to this very campaign.
			pledges = pledges_base.filter(via_campaign=self)
		else:
			# Otherwise, we can count any campaign but only to triggers in this
			# campaign.
			pledges = pledges_base.filter(trigger__in=self.contrib_triggers.all())

		# If no trigger cutomization has a fixed outcome, then we can show
		# plege totals. (We can't show pledge totals when there is a fixed
		# outcome.) In no case do we break this down by desired outcome.
		# There are never TriggerCustomizations when this campaign has no
		# owner.
		tcusts = TriggerCustomization.objects.filter(owner=self.owner, trigger__campaigns=self)
		if not tcusts.exclude(outcome=None).exists():
			ret["pledged_total"] = pledges.aggregate(sum=Sum('amount'))["sum"] or 0
			ret["pledged_user_count"] = pledges.values("user").distinct().aggregate(count=Count('user'))["count"] or 0
		else:
			ret["pledged_site_wide"] = pledges_base.filter(trigger__in=self.contrib_triggers.all()).aggregate(sum=Sum('amount'))["sum"] or 0

		# If any trigger has been executed, then we can show executed totals.
		# In all cases we can show the total amount of contributions across all triggers.
		# Of course, this could be on all sides of an issue, so this isn't usually
		# interesting.
		ret["contrib_total"] = 0
		ret["contrib_user_count"] = 0 # not distinct across triggers

		# Assume all fixed-outcome triggers are about the same issue. Compute the totals
		# across those triggers. Otherwise, we don't know whether outcome X in any trigger
		# corresponds to the same real-world issue as outcome X in any other trigger.
		ret["contrib_fixed_outcome_total"] = 0

		# Report outcomes by trigger, with a breakdown by outcome, and sum across triggers.
		from contrib.views import report_fetch_data
		ret["by_trigger"] = []
		for trigger in self.contrib_triggers.filter(status=TriggerStatus.Executed).order_by('-created'):
			try:
				# Get this trigger's totals.
				agg = report_fetch_data(trigger, via_campaign=self if self.owner else None)
				ret["by_trigger"].append({
					"trigger": trigger,
					"aggregates": agg
				})

				# We sum here and not in an aggregate SQL statement for two reasons:
				# Triggers that haven't had all of their pledges executed should not
				# reveal grossly incomplete information. And our templates assume that
				# if contrib_total > 0, then there is by_trigger information. So we
				# do these two parts together for consistency.
				ret["contrib_total"] += agg["total"]["total"]
				ret["contrib_user_count"] += agg["users"] # not distinct

				# If this trigger has a TriggerCustomization with a fixed outcome,
				# sum the total contributions for that outcome only.
				tcust = TriggerCustomization.objects.filter(owner=self.owner, trigger=trigger).first()
				if tcust and tcust.outcome is not None:
					for outcome in agg["outcomes"]:
						if outcome["outcome"] == tcust.outcome:
							# No easy way to get the total number of unique users.
							ret["contrib_fixed_outcome_total"] += outcome["total"]

			except Http404:
				# This is how report_fetch_data indicates that data
				# is not available. That could be because we haven't
				# yet executed enough pledges to report contribution
				# totals.
				continue

		return ret


#####################################################################
#
# Notifications
#
# Alerts for users.
#
#####################################################################

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
