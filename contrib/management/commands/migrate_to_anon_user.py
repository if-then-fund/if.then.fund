from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from itfsite.models import AnonymousUser
from contrib.models import Pledge, CancelledPledge

class Command(BaseCommand):
	args = ''
	help = 'Single-use data migration.'

	def handle(self, *args, **options):
		for p in Pledge.objects.filter(user=None):
			au = AnonymousUser.objects.create(email=p._email)
			p._email = None
			p.anon_user = au
			p.save(update_fields=['_email', 'anon_user'])
		for cp in CancelledPledge.objects.filter(user=None):
			au = AnonymousUser.objects.create(email=p._email)
			cp._email = None
			cp.anon_user = au
			cp.save(update_fields=['_email', 'anon_user'])
