import enum, re

from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from django.conf import settings

class ValidateEmailResult(enum.Enum):
	Invalid = 1
	Valid = 2
	Deliverable =3
	Error = 4

class LoginResult(enum.Enum):
	Inactive = 1
	Incorrect = 2
	Success = 3

def validate_email(email, simple=False):
	# First check that the email is of a valid form.

	# Based on RFC 2822 and https://github.com/SyrusAkbary/validate_email/blob/master/validate_email.py,
	# these characters are permitted in email addresses.
	ATEXT = r'[\w!#$%&\'\*\+\-/=\?\^`\{\|\}~]' # see 3.2.4

	# per RFC 2822 3.2.4
	DOT_ATOM_TEXT_LOCAL = ATEXT + r'+(?:\.' + ATEXT + r'+)*'
	DOT_ATOM_TEXT_HOST = ATEXT + r'+(?:\.' + ATEXT + r'+)+' # at least one '.'

	# per RFC 2822 3.4.1
	ADDR_SPEC = '^%s@(%s)$' % (DOT_ATOM_TEXT_LOCAL, DOT_ATOM_TEXT_HOST)

	m = re.match(ADDR_SPEC, email)
	if not m:
		return ValidateEmailResult.Invalid

	if simple:
		return ValidateEmailResult.Valid

	domain = m.group(1)
	
	# Check that the domain resolves to MX records, or the A/AAAA fallback.

	import dns.resolver
	resolver = dns.resolver.get_default_resolver()
	try:
		# Try resolving for MX records and get them in sorted priority order.
		response = dns.resolver.query(domain, "MX")
		mtas = sorted([(r.preference, str(r.exchange).rstrip('.')) for r in response])
	except (dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):

		# If there was no MX record, fall back to an A record.
		try:
			response = dns.resolver.query(domain, "A")
			mtas = [(0, str(r)) for r in response]
		except (dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):

			# If there was no A record, fall back to an AAAA record.
			try:
				response = dns.resolver.query(domain, "AAAA")
				mtas = [(0, str(r)) for r in response]
			except (dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
				# If there was any problem resolving the domain name,
				# then the address is not valid.
				return ValidateEmailResult.Invalid
	except:
		# Some unhandled condition should not propagate.
		return ValidateEmailResult.Error


	# Try to deliver. Only try 5 MXs, since otherwise it could
	# take a while. This check requires that we're able to make
	# outbound port 25 connections (problematic in testing from
	# local residential networks).

	if settings.NO_SMTP_CHECK:
		return ValidateEmailResult.Valid

	import smtplib
	for priority, host in mtas[0:3]:
		# Try to open an SMTP connection to the MTA.
		try:
			smtp = smtplib.SMTP(timeout=2)
			smtp.connect(host)
		except (IOError, smtplib.SMTPException):
			# Something didn't work. Try any of the other MXs
			# in the hope that one indicates deliverability.
			continue
		except:
			# Some unhandled condition should not propagate.
			return ValidateEmailResult.Error

		try:
			# Say HELO.
			status, _ = smtp.helo()
			if status != 250:
				# If HELO fails, we really don't know much beyond that
				# the domain has an SMTP server. The address is valid
				# but we don't know about deliverability.
				smtp.quit()
				return ValidateEmailResult.Valid

			# Try to issue a RCPT TO command.
			smtp.mail('')
			status, _ = smtp.rcpt(email)
			smtp.quit()
			if status in (250, 251, 252, 422):
				# Email is probably deliverable to this address. Include
				# 422 (over quota). It may be that the email is not deliverable
				# but the MTA only reports it after receiving a whole message.
				# That's common. But we can err on the side of deliverability
				# here.
				return ValidateEmailResult.Deliverable
			elif status == 450:
				# Although this is a temporary failure code and a nonexistent
				# mailbox is a subset, there would be little reason for the MTA
				# to issue this response if the address were actually deliverable.
				return ValidateEmailResult.Invalid
			else:
				# Other conditions mean we don't know. The address looks reasonably
				# valid but we can't speak to deliverability. There could be other
				# reasons our test is being rejected.
				return ValidateEmailResult.Valid
		except:
			# Some unhandled condition should not propagate.
			return ValidateEmailResult.Error

	# There was no MX that was open to a connection, so the domain
	# is probably not valid.
	return ValidateEmailResult.Invalid

# A view that validates an email (passed in the 'email' POST argument)
# and returns a ValidateEmailResult as text, e.g. "ValidateEmailResult.Deliverable".
@csrf_exempt # for testing via curl
@require_http_methods(["POST"])
def validate_email_view(request):
	return HttpResponse(str(validate_email(request.POST['email'])), content_type="text/plain")

@require_http_methods(["POST"])
def login_view(request):
	# Try to log the user in. Assumes the username on the User object
	# is also the email address.
	from django.contrib.auth import authenticate, login
	from django.contrib.auth.models import User
	email = request.POST['email'].strip()
	password = request.POST['password'].strip()
	user = authenticate(username=email, password=password)
	if user is None:
		# Login failed. Why? If a user with that email exists,
		# return Incorrect.
		if User.objects.filter(email=email).exists():
			ret = LoginResult.Incorrect

		else:
			# If it's because the email address is itself invalid, clue the user to that.
			# But only do a simple regex check.
			if validate_email(email, simple=True) == ValidateEmailResult.Invalid:
				return ValidateEmailResult.Invalid
			else:
				# The email address is reasonable, but not in our system. Don't
				# reveal whether the email address is registered or not. Just
				# say the login is incorrect.
				ret = LoginResult.Incorrect
	else:
		if user.is_active:
			# Login succeeded.
			login(request, user)
			ret = LoginResult.Success
		else:
			# Account is disabled.
			ret = LoginResult.Inactive
	return HttpResponse(str(ret), content_type="text/plain")
