from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from itfsite.models import AnonymousUser
from contrib.models import Pledge, CancelledPledge
from email_confirm_la.models import EmailConfirmation

class Command(BaseCommand):
	args = ''
	help = 'Single-use data migration.'

	@transaction.atomic
	def handle(self, *args, **options):
		for p in Pledge.objects.filter(user=None):
			au = AnonymousUser.objects.create(email=p._email)
			p._email = None
			p.anon_user = au
			p.save(update_fields=['_email', 'anon_user'])

		for p in Pledge.objects.exclude(user=None):
			try:
				ec = EmailConfirmation.get_for(p)
				au = AnonymousUser.objects.create(email=p.user.email)
				ec.content_object = au
				ec.save()
				p.anon_user = au
				p.save()
			except EmailConfirmation.DoesNotExist as e:
				pass

		for cp in CancelledPledge.objects.filter(user=None):
			au = AnonymousUser.objects.create(email=p._email)
			cp._email = None
			cp.anon_user = au
			cp.save(update_fields=['_email', 'anon_user'])
