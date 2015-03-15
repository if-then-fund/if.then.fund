import urllib.parse

from django.http import HttpResponseRedirect
from django.shortcuts import render

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required

from django.conf import settings

# Bring the symbols into this module.
from itfsite.betteruser import User, DirectLoginBackend

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
