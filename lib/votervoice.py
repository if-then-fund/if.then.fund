# Client library for the VoterVoice.net REST API.

import json
import requests
import urllib.parse

class VoterVoiceAPIClient(object):

	def __init__(self, api_key):
		self.api_key = api_key

	def __call__(self, http_method, api_method, data):
		url = "https://www.votervoice.net/api/" + api_method

		urlopen = getattr(requests, http_method.lower())
		if urlopen == requests.get:
			url += "?" + urllib.parse.urlencode(data)
			headers = { }
			payload = None
		else:
			headers = {'content-type': "application/json; charset=utf-8"}
			payload = json.dumps(data)

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

		# all other responses are JSON
		return r.json()

	