# Start psql with database settings.
# ----------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import os
from urllib.parse import urlencode

class Command(BaseCommand):
	args = ''
	help = 'Start psql with database settings.'

	def handle(self, *args, **options):
		d = settings.DATABASES['default']

		# build a connection string so that we can specify sslmode
		conn = "postgresql://%s:%s@%s:%s/%s" % (
			d['USER'], d['PASSWORD'], d['HOST'], d['PORT'], d['NAME'])
		if d.get('OPTIONS', {}):
			conn += "?" + urlencode(d['OPTIONS'])

		# args
		psqlargs = ['psql', conn]
		if len(args) > 0:
			psqlargs.append('-c')
			psqlargs.append(" ".join(args))
		
		# replace this process with psql
		print(" ".join(psqlargs))
		os.execv('/usr/bin/psql', psqlargs)

