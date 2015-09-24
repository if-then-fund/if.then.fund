# Send AnonymousUsers a follow-up email confirmation.
# ---------------------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from itfsite.models import AnonymousUser

import sys
import tqdm
from datetime import timedelta
from htmlemailer import send_mail

class Command(BaseCommand):
	args = ''
	help = 'Sends follow-up confirmation emails for AnonymousUsers.'

	def handle(self, *args, **options):
		# Loop through AnonymousUsers that haven't been confirmed
		# and whose EmailConfirmation object isn't close to expiring
		# (make sure they have 30 hours before the record is expunged).

		for au in AnonymousUser.objects.filter(
			confirmed_user=None,
			created__gt=timezone.now()-timedelta(seconds=
				settings.EMAIL_CONFIRM_LA_CONFIRM_EXPIRE_SEC
					- 60*60*30)):

			if au.should_retry_email_confirmation():
				try:
					au.send_email_confirmation()
				except ValueError as e:
					# Some sort of invalid call.
					print(au, e)
