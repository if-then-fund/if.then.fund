# Send users emails of new notifications.
# ---------------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from itfsite.models import User, Notification, NotificationsFrequency

import sys
import tqdm
from datetime import timedelta
from htmlemailer import send_mail

class Command(BaseCommand):
	args = 'daily|weekly'
	help = 'Sends users emails with new notifications.'

	def handle(self, *args, **options):
		if len(args) == 0:
			print("Specify daily or weekly.")
			return

		freq = {
			"daily": NotificationsFrequency.DailyNotifications,
			"weekly": NotificationsFrequency.WeeklyNotifications,
		}[args[0]]

		# What users do we plausibly have notifications to send to?
		users = self.get_notifications_qs()\
			.filter(user__notifs_freq=freq)\
			.values_list('user', flat=True)\
			.distinct()

		# Nice progress meter when debugging.
		if sys.stdout.isatty():
			users = tqdm.tqdm(users)

		# Loop through users.
		for user in users:
			try:
				self.send_notifications_email(user)
			except OSError as e:
				print(user, e)

	def get_notifications_qs(self):
		return Notification.objects.filter(
			created__gt=timezone.now() - timedelta(days=7), # don't send really old stuff
			dismissed_at=None, # don't send stuff the user has already seen
			mailed_at=None, # don't send stuff we have already mailed
			)

	def send_notifications_email(self, user_id):
		# Get the user.
		user = User.objects.get(id=user_id)

		# Get the notifications to email.
		notifs = self.get_notifications_qs().filter(user=user)

		# Don't send any notifications that were generated prior to the
		# most recently emailed notification.
		most_recent_emailed = Notification.objects.filter(user=user)\
			.exclude(mailed_at=None).order_by('-mailed_at').first()
		if most_recent_emailed:
			notifs = notifs.filter(created__gte=most_recent_emailed.mailed_at)

		# Nothing to send after all?
		if notifs.count() == 0:
			return

		# Only send up to the 50 most recent.
		notifs = notifs.order_by('-created')[0:50]

		# Prune any Notification objects whose generic object 'source'
		# is dangling (source object has since been deleted).
		def filter_and_delete(n):
			if n.source is None:
				n.delete()
				return False
			return True
		notifs = list(filter(filter_and_delete, notifs))

		# Render.
		alerts = Notification.render(notifs, for_client=False)
		if len(alerts) == 0: # Nothing to send after all?
			return

		# Get the user's most recent pledge ContributorInfo object
		# to generate the salutation from. (May be null.)
		profile = user.get_contributorinfo()

		# Activate the user's preferred timezone? Not needed since 
		# we aren't displaying notification times in the email, but
		# maybe we will?
		#user.active_timezone()

		# Send email.
		send_mail(
			"itfsite/mail/notifications",
			settings.DEFAULT_FROM_EMAIL,
			[user.email],
			{
				"user": user,
				"profile": profile,
				"notifs": alerts,
				"subject": alerts[0]['title'],
				"count": len(alerts),
			})

		# Record that these notifications were sent.
		# Weird because of 'Cannot update a query once a slice has been taken.'.
		notifs = Notification.objects.filter(id__in=[n.id for n in notifs])
		notifs.update(mailed_at=timezone.now())
