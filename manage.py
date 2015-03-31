#!.env/bin/python
import os
import sys

if __name__ == "__main__":
	sys.path.insert(0, "lib")
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "itfsite.settings")

	from django.core.management import execute_from_command_line

	if sys.stderr.isatty():
		# When management commands are run from an interactive shell,
		# run the function directly.
		execute_from_command_line(sys.argv)
	else:
		# We're running from a cron job or other script. Mail exceptions
		# to the administrator in the same way that live exceptions on
		# the site get mailed to admins.

		from django.utils.log import AdminEmailHandler
		import logging
		logger = logging.getLogger('django_management_command')
		logger.addHandler(AdminEmailHandler())

		try:
			execute_from_command_line(sys.argv)

		except Exception as e:
			# email admins
			logger.error('Admin Command Error: %s', ' '.join(sys.argv), exc_info=sys.exc_info())

			# also write to stderr & exit
			raise
