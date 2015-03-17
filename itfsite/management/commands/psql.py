# Start psql with database settings.
# ----------------------------------

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from optparse import make_option

import os
from urllib.parse import urlencode

class Command(BaseCommand):
	args = ''
	help = 'Start psql with database settings.'

	option_list = BaseCommand.option_list + (
		make_option('--pg_dump',
			action='store_true',
			dest='pg_dump',
			default=False,
			help='Run pg_dump instead of psql.'),
		)

	def handle(self, *args, **options):
		d = settings.DATABASES['default']
		if d['ENGINE'] != 'django.db.backends.postgresql_psycopg2':
			print("The default database is not a PostgreSQL database..")
			return

		# build a connection string so that we can specify sslmode
		conn = "postgresql://%s:%s@%s:%s/%s" % (
			d['USER'], d['PASSWORD'], d['HOST'], d['PORT'], d['NAME'])
		if d.get('OPTIONS', {}):
			conn += "?" + urlencode(d['OPTIONS'])

		# binary & args
		if not options['pg_dump']:
			binary = 'psql'
			psqlargs = [binary, conn]
			if len(args) > 0:
				psqlargs.append('-c')
				psqlargs.append(" ".join(args))
		else:
			binary = 'pg_dump'
			psqlargs = [binary, conn] + list(args)
		
		# replace this process with psql
		print(" ".join(psqlargs))
		os.execv('/usr/bin/' + binary, psqlargs)

