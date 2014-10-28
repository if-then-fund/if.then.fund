from django.shortcuts import render, redirect, get_object_or_404

from pledge.models import Trigger

def trigger(request, id, slug):
	# get the object
	trigger = get_object_or_404(Trigger, id=id)

	# redirect to canonical URL if slug does not match
	if trigger.slug != slug:
		return redirect(trigger.get_absolute_url())

	return render(request, "pledge/trigger.html", {
		"trigger": trigger,
	})