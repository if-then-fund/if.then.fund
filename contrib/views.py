from django.shortcuts import render, redirect, get_object_or_404

from twostream.decorators import anonymous_view

from contrib.models import Trigger

@anonymous_view
def trigger(request, id, slug):
	# get the object
	trigger = get_object_or_404(Trigger, id=id)

	# redirect to canonical URL if slug does not match
	if trigger.slug != slug:
		return redirect(trigger.get_absolute_url())

	return render(request, "contrib/trigger.html", {
		"trigger": trigger,
	})