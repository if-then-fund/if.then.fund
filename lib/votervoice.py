# Client library for the VoterVoice.net REST API.

import json
import requests
import urllib.parse
import hashlib
from collections import OrderedDict

from django.core.cache import cache

class VoterVoiceAPIClient(object):

	def __init__(self, api_key):
		self.api_key = api_key

	def __call__(self, http_method, api_method, qsargs, post_data, cache_duration=6):
		cache_key = None
		url = "https://www.votervoice.net/api/" + api_method

		urlopen = getattr(requests, http_method.lower())
		if urlopen == requests.get:
			url += "?" + urllib.parse.urlencode(make_sorted_dict(qsargs)) # sorting is good for caching
			headers = { }
			payload = None

			# Try to load from our local cache. Compute a fast key guaranteed to be a valid cache key.
			cache_key = "votervoice_get_" + hashlib.md5(url.encode("utf8")).hexdigest()
			ret = cache.get(cache_key)
			if ret: return ret # yes cached!
		else:
			headers = {'content-type': "application/json; charset=utf-8"}
			payload = json.dumps(post_data)

		# Set Authorization.
		headers['Authorization'] = self.api_key.encode('ascii')

		# issue request
		r = urlopen(
			url,
			data=payload,
			headers=headers,
			timeout=20,
			verify=True, # check SSL cert (is default, actually)
			)

		# raise exception on anything but 200 OK
		r.raise_for_status()

		# The PUT requests have no response. A 200 response is success.
		if urlopen == requests.put:
			return None

		# All other responses are JSON.
		ret = r.json()

		# Cache response.
		if cache_key and cache_duration > 0:
			cache.set(cache_key, ret, 60*cache_duration) # minutes => seconds

		# Return.
		return ret

def make_sorted_dict(kv):
	return OrderedDict(sorted(kv.items()))
