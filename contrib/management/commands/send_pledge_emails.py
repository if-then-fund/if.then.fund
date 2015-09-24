# Send pre- and post- pledge execution emails
# -------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from datetime import timedelta

from contrib.models import Pledge, TriggerStatus, PledgeStatus, IncompletePledge
from contrib.bizlogic import get_pledge_recipients, compute_charge
from itfsite.middleware import get_branding

from htmlemailer import send_mail

class Command(BaseCommand):
	args = ''
	help = 'Sends pre- and post- pledge execution emails and incomplete pledge emails.'

	def handle(self, *args, **options):
		self.send_pledge_emails('pre')
		self.send_pledge_emails('post')
		self.send_incomplete_pledge_emails()

	def send_pledge_emails(self, pre_or_post):
		if pre_or_post == "pre":
			# Pledges on executed triggers that have not yet been
			# executed, are confirmed (have a user account), and
			# have not yet had their pre-executionemail sent.
			pledges = Pledge.objects.filter(
				status=PledgeStatus.Open,
				trigger__status=TriggerStatus.Executed,
				pre_execution_email_sent_at=None
				).exclude(user=None)
			pledge_filter = lambda p : p.needs_pre_execution_email()

		elif pre_or_post == "post":
			# Executed pledges that were confirmed and have not yet
			# been sent their post-execution email.
			pledges = Pledge.objects.filter(
				status=PledgeStatus.Executed,
				post_execution_email_sent_at=None
				).exclude(user=None)
			pledge_filter = lambda p : True

		else:
			raise ValueError()

		# Send email for each.
		pledges = pledges.select_related("user")
		for pledge in pledges:
			# Apply a post-db-query filter.
			if not pledge_filter(pledge):
				continue

			# Send email.
			self.send_pledge_email(pre_or_post, pledge)

	def send_pledge_email(self, pre_or_post, pledge):
		# What will happen when the pledge is executed?
		recipients = get_pledge_recipients(pledge.trigger, pledge)
		if len(recipients) == 0:
			# This pledge will result in nothing happening. There is
			# no need to email.
			return
		recip_contribs, fees, total_charge = compute_charge(pledge, recipients)

		context = { }
		context.update(get_branding(pledge.via_campaign.brand))
		context.update({
			"profile": pledge.profile, # used in salutation in email_template
			"pledge": pledge,
			"until": Pledge.current_algorithm()['pre_execution_warn_time'][1],
			"total_charge": total_charge,
		})

		# Send email.
		send_mail(
			"contrib/mail/%s_execution" % pre_or_post,
			context["MAIL_FROM_EMAIL"],
			[pledge.user.email],
			context)

		# Record that it was sent.
		field_name = "%s_execution_email_sent_at" % pre_or_post
		setattr(pledge, field_name, timezone.now())
		pledge.save(update_fields=[field_name])

	def send_incomplete_pledge_emails(self):
		# For every IncompletePledge instance that has not yet been
		# sent a reminder email, send one. Wait at least some hours
		# after the user left the page.
		before = timezone.now() - timedelta(hours=3)
		for ip in IncompletePledge.objects.filter(created__lt=before, sent_followup_at=None):
			context = { }
			context.update(get_branding(ip.via_campaign.brand))
			context.update({
				"incomplete_pledge": ip,
				"url": settings.SITE_ROOT_URL + ip.get_return_url(),
				"trigger": ip.trigger,
			})

			# Send email.
			send_mail(
				"contrib/mail/incomplete_pledge",
				get_branding(ip.via_campaign.brand)["MAIL_FROM_EMAIL"],
				[ip.email],
				context,
				headers={
					"Reply-To": get_branding(ip.via_campaign.brand)["CONTACT_EMAIL"],
				})

			# Record that it was sent.
			ip.sent_followup_at = timezone.now()
			ip.save()
