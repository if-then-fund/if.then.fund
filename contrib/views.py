from django.shortcuts import render, redirect, get_object_or_404

from twostream.decorators import anonymous_view

from contrib.models import Trigger, Pledge

@anonymous_view
def trigger(request, id, slug):
	# get the object
	trigger = get_object_or_404(Trigger, id=id)

	# redirect to canonical URL if slug does not match
	if trigger.slug != slug:
		return redirect(trigger.get_absolute_url())

	return render(request, "contrib/trigger.html", {
		"trigger": trigger,
		"fees_percent": Pledge.current_fees()*100.0, # e.g. 0.10 => 10 meaning 10 percent
	})