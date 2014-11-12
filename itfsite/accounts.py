import enum, re, urllib.parse

from django.db import models
from django.utils import timezone

from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.decorators import login_required

from django.conf import settings

# Custom user model and login backends

class UserManager(models.Manager):
	# The only purpose of this class is to support the createsuperuser management command.
	def create_superuser(self, email, password, **extra_fields):
		user = User(email=email)
		user.is_staff = True
		user.is_superuser = True
		user.set_password(password)
		user.save()
		return user

class User(AbstractBaseUser, PermissionsMixin):
	"""Our user model, where the primary identifier is an email address."""
	# https://github.com/django/django/blob/master/django/contrib/auth/models.py#L395
	email = models.EmailField(unique=True)
	is_staff = models.BooleanField(default=False, help_text='Whether the user can log into this admin.')
	is_active = models.BooleanField(default=True, help_text='Unselect this instead of deleting accounts.')
	date_joined = models.DateTimeField(default=timezone.now)

	# custom user model requirements
	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = ['is_staff', 'is_active', 'date_joined']
	def get_full_name(self): return self.email
	def get_short_name(self): return self.email
	class Meta:
		verbose_name = 'user'
		verbose_name_plural = 'users'
	objects = UserManager()

	@staticmethod
	def get_or_create(email):
		# Get or create a new User for the email address. The User table
		# is not locked, so handle concurrency optimistically. The rest is
		# based on Django's default create_user.
		try:
			# Does the user exist?
			return User.objects.get(email=email)
		except User.DoesNotExist:
			try:
				# Try to create it.
				user = User(email=email)
				user.set_unusable_password()
				user.save()
				return user
			except IntegrityError:
				# Creation failed (unique key violation on username),
				# so try to get it again. If this fails, something
				# weird happened --- just raise an exception then.
				return User.objects.get(email=email)

class EmailPasswordLoginBackend(ModelBackend):
	# Registered in settings.py.
	supports_object_permissions = False
	supports_anonymous_user = False
	def authenticate(self, email=None, password=None, username=None):
		# The Django default login form (e.g. used by the admin) passes
		# the email in the 'username' field.
		if username: email = username

		try:
			user = User.objects.get(email=email)
			if user.check_password(password):
				return user
		except User.DoesNotExist:
			# Says Django sources: Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (#20760).
			User.set_password(password)
		return None

class DirectLoginBackend(ModelBackend):
	# Django can't log a user in without their password. Before they create
	# a password, we use this to log them in. Registered in settings.py.
	supports_object_permissions = False
	supports_anonymous_user = False
	def authenticate(self, user_object=None):
		return user_object

# Validation

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

def try_login(request):
	# Do the authentication part of logging the user in, and returns the
	# User object on success or a LoginResult or ValidateEmailResult on
	# failure.
	email = request.POST['email'].strip()
	password = request.POST['password'].strip()
	user = authenticate(email=email, password=password)
	if user is not None:
		if not user.is_active:
			# Account is disabled.
			return LoginResult.Inactive
		else:
			return user
	else:
		# Login failed. Why? If a user with that email exists,
		# return Incorrect.
		if User.objects.filter(email=email).exists():
			return LoginResult.Incorrect

		else:
			# If it's because the email address is itself invalid, clue the user to that.
			# But only do a simple regex check.
			if validate_email(email, simple=True) == ValidateEmailResult.Invalid:
				return ValidateEmailResult.Invalid
			else:
				# The email address is reasonable, but not in our system. Don't
				# reveal whether the email address is registered or not. Just
				# say the login is incorrect.
				return LoginResult.Incorrect

def first_time_confirmed_user(request, user, next):
	# The user has just confirmed their email address. Log them in.
	# If they don't have a password set on their account, welcome them
	# and ask for a password. Otherwise, send them on their way to the
	# next page.

	# Log in.
	user = authenticate(user_object=user)
	if user is None: raise ValueError("Could not authenticate.")
	if not user.is_active: raise ValueError("Account is disabled.")
	login(request, user)

	if not user.has_usable_password():
		return HttpResponseRedirect("/accounts/welcome?" +
			urllib.parse.urlencode({ "next": next }))
	else:
		return HttpResponseRedirect(next)

@login_required
def welcome(request):
	# A welcome page for after an email confirmation to get the user to set a password.
	error = None
	if request.method == "POST":
		p1 = request.POST.get('p1', '')
		p2 = request.POST.get('p2', '')
		if len(p1) < 4 or p1 != p2:
			error = "Validation failed."
		else:
			u = request.user
			try:
				u.set_password(p1)
				u.save()

				# because of SessionAuthenticationMiddleware, the user gets logged
				# out immediately --- log them back in
				u = authenticate(user_object=u)
				login(request, u)

				return HttpResponseRedirect(request.GET.get('next', '/'))
			except:
				error = "Something went wrong, sorry."

	return render(request, "itfsite/welcome.html", {
		"error": error
	})
