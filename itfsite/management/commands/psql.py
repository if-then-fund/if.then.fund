# Start psql with database settings.
# ----------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import os

class Command(BaseCommand):
	args = ''
	help = 'Start psql with database settings.'

	def handle(self, *args, **options):
		d = settings.DATABASES['default']

		# write password so we don't have to enter it manually
		with open('/home/ubuntu/.pgpass', 'w') as f:
			f.write(':'.join([d['HOST'], d['PORT'], d['NAME'], d['USER'], d['PASSWORD']]))
		os.chmod('/home/ubuntu/.pgpass', 0o600)

		# args
		psqlargs = [
			'psql',
			'-h', d['HOST'],
			'-p', d['PORT'],
			d['NAME'],
			d['USER'],
			]
		if len(args) > 0:
			psqlargs.append('-c')
			psqlargs.append(" ".join(args))
		
		# replace this process with psql
		os.execv('/usr/bin/psql', psqlargs)

