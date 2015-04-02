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
		# to the administrator similar to the way that live exceptions on
		# the site get mailed to admins, based on the django.utils.log.AdminEmailHandler.
		# https://docs.djangoproject.com/en/1.8/_modules/django/utils/log/
		import logging
		class AdminEmailHandler(logging.Handler):
			def __init__(self):
				logging.Handler.__init__(self)
			def emit(self, record):
				from shlex import quote
				from django.core.mail import mail_admins
				subject = ("%s: %s" % (" ".join(quote(arg) for arg in sys.argv), record.getMessage()))[:989]
				message = self.format(record)
				mail_admins(subject, message, fail_silently=True)
		logger = logging.getLogger('django_management_command')
		logger.addHandler(AdminEmailHandler())

		try:
			execute_from_command_line(sys.argv)

		except Exception as e:
			# email admins
			logger.error(repr(e), exc_info=sys.exc_info())

			# also write to stderr & exit
			raise
