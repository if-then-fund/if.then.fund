# Send pre- and post- pledge execution emails
# -------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from contrib.models import Pledge, TriggerStatus, PledgeStatus
from contrib.bizlogic import get_pledge_recipients, compute_charge

from htmlemailer import send_mail

class Command(BaseCommand):
	args = ''
	help = 'Sends pre- and post- pledge execution emails and email confirmation emails.'

	def handle(self, *args, **options):
		self.send_pledge_emails('pre')
		self.send_pledge_emails('post')
		self.send_pledge_emails('emailconfirm')

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

		elif pre_or_post == "post":
			# Executed pledges that were confirmed and have not yet
			# been sent their post-execution email.
			pledges = Pledge.objects.filter(
				status=PledgeStatus.Executed,
				post_execution_email_sent_at=None
				).exclude(user=None)

		elif pre_or_post == "emailconfirm":
			pledges = Pledge.objects.filter(
				status=PledgeStatus.Open,
				user=None
				)

		else:
			raise ValueError()

		# Send email for each.
		pledges = pledges.select_related("user")
		for pledge in pledges:

			if pre_or_post in ("pre", "post"):
				self.send_pledge_email(pre_or_post, pledge)

			elif pre_or_post == "emailconfirm":
				if pledge.should_retry_email_confirmation():
					pledge.send_email_confirmation(first_try=False)
	
	def send_pledge_email(self, pre_or_post, pledge):
		# What will happen when the pledge is executed?
		recipients = get_pledge_recipients(pledge.trigger, pledge)
		if len(recipients) == 0:
			# This pledge will result in nothing happening. There is
			# no need to email.
			return
		recip_contribs, fees, total_charge = compute_charge(pledge, recipients)

		# Send email.
		send_mail(
			"contrib/mail/%s_execution" % pre_or_post,
			settings.DEFAULT_FROM_EMAIL,
			[pledge.user.email],
			{
				"pledge": pledge,
				"until": Pledge.current_algorithm()['pre_execution_warn_time'][1],
				"total_charge": total_charge,
			})

		# Record that it was sent.
		field_name = "%s_execution_email_sent_at" % pre_or_post
		setattr(pledge, field_name, timezone.now())
		pledge.save(update_fields=[field_name])
