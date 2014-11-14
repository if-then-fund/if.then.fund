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

class DemocracyEngineAPI(object):
	de_meta_info = None

	def __call__(self, method, post_data=None, argument=None, live_request=False, http_method=None):
		import json
		import requests
		from requests.auth import HTTPDigestAuth

		# Cache meta info. If method is None, don't infinite recurse.
		if (self.de_meta_info == None) and (method is not None):
			self.de_meta_info = self(None, None, live_request=live_request)

		if method is None:
			# This is an internal call to get the meta subscriber info.
			url = settings.DE_API['api_baseurl'] + ('/subscribers/%s.json' % settings.DE_API['account_number'])
		elif method == "META":
			# This is a real call to get the meta info, which is always cached.
			return self.de_meta_info
		else:
			# Get the correct URL from the meta info, and do argument substitution
			# if necessary.
			url = self.de_meta_info[method + "_uri"]
			if argument:
				import urllib.parse
				url = url.replace(":"+argument[0], urllib.parse.quote(argument[1]))

		# GET or POST?
		if post_data == None:
			payload = None
			headers = None
			urlopen = requests.get
		else:
			payload = json.dumps(post_data)
			headers = {'content-type': 'application/json'}
			urlopen = requests.post

		# Override HTTP method.
		if http_method:
			urlopen = getattr(requests, http_method)

		# issue request
		r = urlopen(
			url,
			auth=HTTPDigestAuth(settings.DE_API['username'], settings.DE_API['password']),
			data=payload,
			headers=headers,
			timeout=30 if not live_request else 20,
			verify=True, # check SSL cert (is default, actually)
			)

		# raises exception on anything but 200 OK
		try:
			r.raise_for_status()
		except:
			raise IOError("DemocrayEngine API failed: %d %s" % (r.status_code, url))

		# all responses are JSON
		return r.json()

	def recipients(self, live_request=False):
		return self(method="recipients", live_request=live_request)

	def get_recipient(self, id, live_request=False, http_method=None):
		return self(method="recipient", argument=('recipient_id', id), http_method=http_method, live_request=live_request)

	def create_recipient(self, info):
		return self(
			method="recipients",
			post_data=
				{ "recipient":
					{
						"remote_recipient_id": info["id"],
						"name": info["committee_name"],
						"registered_id": info["committee_id"],
						"recipient_type": "federal_candidate",
						#"contact": { "first_name", "last_name", "phone", "address1", "city", "state", "zip" },
						"user": {
							"first_name": "Generic",
							"last_name": "User",
							"login": "c%d" % info["id"],
							"initial_password": info["user_password"],
							"email": "de.user@civicresponsibilityllc.com"
						},
						"recipient_tags": {
							"party": info["party"], # e.g. "Democrat"
							"state": info["state"], # USPS
							"office": info["office"], # senator, representative
							"district": info["district"], # integer
							"cycle": info["cycle"] # year, integer
						}
					}
				})

# Replace with a singleton instance.
DemocracyEngineAPI = DemocracyEngineAPI()

