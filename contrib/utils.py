from django.http import HttpResponse, HttpResponseServerError
from django.conf import settings

from functools import wraps
import json

def query_json_api(base_url, params):
	import urllib.request, urllib.parse, json
	url = base_url + "?" + urllib.parse.urlencode(params)
	req = urllib.request.urlopen(url)
	return json.loads(req.read().decode("utf-8"))

def json_response(f):
	"""A decorator for views that turns JSON-serializable output into a JSON response."""

	@wraps(f)
	def g(*args, **kwargs):
		try:
			# Call the wrapped view.
			ret = f(*args, **kwargs)

			# If it returns a HttpResponse, pass it through unchanged.
			if isinstance(ret, HttpResponse):
				return ret

			# Return a JSON response.
			ret = json.dumps(ret)
			resp = HttpResponse(ret, content_type="application/json")
			resp["Content-Length"] = len(ret)
			return resp

		# Catch simple errors.
		except ValueError as e:
			return HttpResponse(json.dumps({ "status": "fail", "msg": str(e) }),
				content_type="application/json")

	return g

