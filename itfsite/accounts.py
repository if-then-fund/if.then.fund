import enum
import urllib.parse

from django.db import models
from django.http import HttpResponseRedirect
from django.shortcuts import render

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required

from django.conf import settings

from enum3field import EnumField, django_enum

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
