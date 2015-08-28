import enum
import urllib.parse

from django.db import models, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required

from django.conf import settings

from enum3field import EnumField, django_enum
from itfsite.utils import JSONField

# Bring the symbols into this module.
from itfsite.betteruser import UserBase, UserManagerBase, DirectLoginBackend

@django_enum
class NotificationsFrequency(enum.Enum):
	NoNotifications = 0
	DailyNotifications = 1
	WeeklyNotifications = 2

# Override the User model with one that adds additional user profile fields.
class UserManager(UserManagerBase):
	def _get_user_class(self):
		return User
class User(UserBase):
	objects = UserManager() # override with derived class
	notifs_freq  = EnumField(NotificationsFrequency, default=NotificationsFrequency.DailyNotifications, help_text="Now often the user wants to get non-obligatory notifications.")

	def twostream_data(self):
		from itfsite.models import Notification
		notifs = Notification.objects.filter(user=self).order_by('-created')[0:30]
		return {
			"notifications": Notification.render(notifs),
		}

	def get_contributorinfo(self):
		# Get the User's most recent ContributorInfo object which
		# will have their name, address, etc.
		from contrib.models import Pledge
		p = Pledge.objects.filter(user=self).order_by('-created').first()
		return p and p.profile

	def active_timezone(self):
		# Activate the user's timezone.
		from contrib.models import Pledge
		from django.utils import timezone
		import pytz

		# Fall back to US Eastern, where our company is located and
		# legislative activity in Congress occurs.
		tz = "America/New_York"

		# See if we have stored a timezone in a recent, geocoded profile.
		pledge = Pledge.objects.filter(user=self, profile__is_geocoded=True).order_by('-created').first()
		if pledge and pledge.profile.extra['geocode'].get('tz'):
			tz = pledge.profile.extra['geocode']['tz']

		# Activate.
		timezone.activate(pytz.timezone(tz))

class AnonymousUser(models.Model):
	"""A class to which to tie multiple actions by a single anonymous user."""

	email = models.EmailField(max_length=254, blank=True, null=True, db_index=True)

	sentConfirmationEmail = models.BooleanField(default=False, help_text="Have we sent this user an email to confirm their address and activate their account/actions?")
	confirmed_user = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE, help_text="The user that this record became confirmed as.")

	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)

	extra = JSONField(blank=True, help_text="Additional information stored with this object.")

	def __str__(self):
		return self.email + ((" → " + str(self.confirmed_user)) if self.confirmed_user else "")

	def send_email_confirmation(self):
		# What can we say this email is for?
		from contrib.models import Pledge
		pledge = Pledge.objects.filter(anon_user=self).first()
		if pledge:
			template = "contrib/mail/confirm_email"
			profile = pledge.profile
		else:
			raise ValueError("AnonymousUser is not associated with a Pledge.")

		# Use a custom mailer function so we can send through our
		# HTML emailer app.
		def mailer(context):
			from htmlemailer import send_mail
			send_mail(
				template,
				settings.DEFAULT_FROM_EMAIL,
				[context['email']],
				{
					"profile": profile, # used in salutation in email_template
					"confirmation_url": context['confirmation_url'],
					"pledge": pledge,
					"first_try": not self.sentConfirmationEmail,
				})

		from email_confirm_la.models import EmailConfirmation
		if not self.sentConfirmationEmail:
			# Make an EmailConfirmation object.
			ec = EmailConfirmation.create(self)
		else:
			# Get an existing EmailConfirmation object.
			ec = EmailConfirmation.get_for(self)
		ec.send(mailer=mailer)

		self.sentConfirmationEmail = True
		self.save()

	def should_retry_email_confirmation(self):
		from datetime import timedelta
		from django.utils import timezone
		from email_confirm_la.models import EmailConfirmation
		try:
			ec = EmailConfirmation.get_for(self)
		except EmailConfirmation.DoesNotExist as e:
			# The record expired. No need to send again.
			return False
		if ec.send_count >= 3:
			# Already sent three emails, stop.
			return False
		if ec.sent_at < timezone.now() - timedelta(days=1):
			# More than a day has passed since the last email, so send again.
			return True
		return False

	# A user confirms an email address on an anonymous pledge.
	def email_confirmation_confirmed(self, confirmation, request):
		self.email_confirmed(confirmation.email, request)

	@transaction.atomic
	def email_confirmed(self, email, request):
		# Get or create a user account for this person.
		user = User.get_or_create(email)

		# Update this record.
		self.confirmed_user = user
		self.save()

		# Confirm all associated pledges.
		from contrib.models import Pledge
		for pledge in Pledge.objects.filter(anon_user=self):
			pledge.set_confirmed_user(user, request)

		# Confirm all associated letters.
		from letters.models import UserLetter
		for letter in UserLetter.objects.filter(anon_user=self):
			letter.set_confirmed_user(user, request)

		return user

	def email_confirmation_response_view(self, request):
		# The user may be new, so take them to a welcome page.
		from itfsite.accounts import first_time_confirmed_user

		# Redirect to any Pledge created by this user.
		from contrib.models import Pledge
		pledge = Pledge.objects.filter(user=self.confirmed_user).first()

		return first_time_confirmed_user(request, self.confirmed_user,
			pledge.get_absolute_url() if pledge else "/home")

def first_time_confirmed_user(request, user, next, just_get_url=False):
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
		url = "/accounts/welcome?" + urllib.parse.urlencode({ "next": next })
		if just_get_url: return url
		return HttpResponseRedirect(url)
	else:
		if just_get_url: return None # no need to go to welcome page
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
