from django.http import HttpResponse, HttpResponseServerError
from django.conf import settings

from functools import wraps
import json, datetime

def query_json_api(base_url, params={}, raw=False):
	import urllib.request, urllib.parse, json
	
	url = base_url
	if len(params) > 0: url += "?" + urllib.parse.urlencode(params)
	
	if not getattr(settings, 'LOAD_REMOTE_DATA_FROM_FIXTURES', False):
		# Execute a web request.
		req = urllib.request.urlopen(url)
	
	else:
		# For off-line testing, load JSON from fixtures path.
		import os.path
		urlparts = urllib.parse.urlparse(url)
		fn = "fixtures/" + (
			          urlparts.hostname.replace("www.", "")
			 + "--" + urlparts.path
			 + ("--" if urlparts.query else "")
			 + "-".join(k+"="+v[0] for (k, v) in sorted(urllib.parse.parse_qs(urlparts.query).items()))
			 ).replace("/", "-")
		if not raw and not fn.endswith(".json"): fn += ".json"
		if not os.path.exists(fn):
			# This is probably the first time we're accessing this resource.
			# Fetch and store the remote content.
			print("%s => %s" % (url, fn))
			remote_content = urllib.request.urlopen(url).read()
			with open(fn, 'wb') as f:
				f.write(remote_content)

		req = open(fn, 'rb')
	
	if raw: return req.read()
	
	return json.loads(req.read().decode("utf-8"))

def build_json_httpresponse(obj):
	import decimal
	class MyEncoder(json.JSONEncoder):
		def default(self, o):
			if isinstance(o, decimal.Decimal):
				return float(o)
			if isinstance(o, datetime.datetime):
				return o.isoformat()
			return super(MyEncoder, self).default(o)
	ret = json.dumps(obj, cls=MyEncoder, sort_keys=True, indent=2)
	resp = HttpResponse(ret, content_type="application/json")
	resp["Content-Length"] = len(ret)
	return resp

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
			return build_json_httpresponse(ret)

		# Catch simple errors.
		except ValueError as e:
			print(e)
			return HttpResponse(json.dumps({ "status": "fail", "msg": str(e) }),
				content_type="application/json")

	return g

