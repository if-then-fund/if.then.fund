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
		if len(qsargs.items()) > 0:
			# JSONify any dicts. Sort the keys to make sure URLs are stable for cachine.
			for k in qsargs:
				if isinstance(qsargs[k], dict):
					qsargs[k] = json.dumps(qsargs[k], sort_keys=True)
			url += "?" + urllib.parse.urlencode(make_sorted_dict(qsargs)) # sorting is good for caching

		urlopen = getattr(requests, http_method.lower())
		if urlopen == requests.get:
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

class VoterVoiceDummyAPIClient:
	def __init__(self):
		self.known_users = { }
		self.emailownershipverifications = { }

	def __call__(self, http_method, api_method, qsargs, post_data, cache_duration=6):
		# Construct a "url" to show in error messages for debugging.
		url = "/api/" + api_method
		if len(qsargs.items()) > 0:
			url += "?" + urllib.parse.urlencode(make_sorted_dict(qsargs))

		if (http_method, api_method) == ("GET", "addresses"):
			assert qsargs.get("address1")
			assert qsargs.get("city")
			assert qsargs.get("state")
			assert qsargs.get("zipcode")
			assert qsargs.get("country") == "US"
			if "invalid" in qsargs["address1"]:
				return { "message": "That's an invalid address." }
			return {
				"addresses": [{
					"dummy": "foobar",
					"state": qsargs["state"],
				}]
			}

		elif (http_method, api_method) == ("GET", "districts"):
			assert qsargs.get("association")
			assert qsargs.get("address")
			assert qsargs["address"].get("dummy") == "foobar"
			return [
				{
					"electedBody": "US House",
					"delegateGovernment": { "uri": ".../" + qsargs["address"]["state"] },
					"districtId": "01",
				}
			]

		elif (http_method, api_method) == ("GET", "advocacy/matchedtargets"):
			assert qsargs.get("association")
			assert qsargs.get("home")
			assert qsargs["home"].get("dummy") == "foobar"
			return [
				{
					"groupId": "US Representative",
					"messageId": "???",
					"matches": [{
						"canSend": True,
						"type": "E",
						"id": "1234",
						"name": "Rep. John Doe",
					}]
				}
			]

		elif (http_method, api_method) == ("GET", "advocacy/messagedeliveryoptions"):
			assert qsargs.get("association")
			assert qsargs.get("targettype")
			assert qsargs.get("targetid") == "1234"
			return [{
				"deliveryMethod": "webform",
				"requiredUserFields": ["address"],
				"requiredQuestions": [{
					"question": "What is the purpose of life?",
					"validAnswers": ["To code", "To live"],
				}],
				"sharedQuestionIds": ["CommonHonorific", "SQID"],
			}]

		elif http_method == "GET" and api_method.startswith("advocacy/sharedquestions/"):
			sqid = api_method.split("/")[-1]
			if sqid == "CommonHonorific":
				return { "question": "!!!", "validAnswers": ["Mr.", "Ms."] }
			return { "question": "Pick a letter!", "validAnswers": ["A", "B"] }

		elif (http_method, api_method) == ("POST", "users"):
			assert qsargs.get("association")
			assert post_data.get("emailAddress")
			assert post_data.get("honorific")
			assert post_data.get("givenNames")
			assert post_data.get("surname")
			assert post_data.get("homeAddress")

			if "invalid" in post_data["surname"]:
				self.make_error(400, "Simulated validation error.")

			elif post_data["emailAddress"] not in self.known_users \
				or self.known_users[post_data.get("emailAddress")] == post_data["surname"]:
				# New user, or existing user but no significant change.
				self.known_users[post_data.get("emailAddress")] = post_data["surname"]
				return { "userId": 100, "userToken": "ABCDEFGHIJKL" }

			else:
				# Existing user with significant change.
				self.make_error(409, "Simulated conflict error.")

		elif (http_method, api_method) == ("POST", "emailownershipverifications"):
			assert qsargs.get("association")
			assert post_data.get("emailAddress")
			key = str(len(self.emailownershipverifications))
			self.emailownershipverifications[key] = key
			self.LAST_EMAIL_VERIF_CODE = key
			return { "verificationId": key }

		elif http_method == "POST" and api_method.startswith("emailownershipverifications/"):
			key = api_method.split('/')[-2]
			assert post_data.get("code")
			if key not in self.emailownershipverifications:
				self.make_error(400, "Invalid verification ID.")
			elif self.emailownershipverifications[key] != post_data.get("code"):
				self.make_error(400, "Incorrect code.")
			else:
				return { "proof": "123PROOF456" }

		elif (http_method, api_method) == ("GET", "users/identities"):
			assert qsargs.get("email")
			assert qsargs.get("ownershipProof") == "123PROOF456"
			return [{
				"id": 101,
				"token": "XYZABC",
			}]

		elif (http_method, api_method) == ("PUT", "users/XYZABC"):
			assert qsargs.get("association")
			assert post_data.get("emailAddress")
			assert post_data.get("honorific")
			assert post_data.get("givenNames")
			assert post_data.get("surname")
			assert post_data.get("homeAddress")
			return ""

		elif (http_method, api_method) == ("POST", "advocacy/responses"):
			assert qsargs.get("user")
			assert post_data.get("userId")
			return {
				"deliveredMessages": [
					{
						"targetedId": 1111,
						"deliveredId": 123456
					}
					]
				}

		else:
			raise Exception("Invalid call to VoterVoice: %s %s" % (http_method, url))

	def make_error(self, code, message):
		import requests
		r = requests.Response()
		r.status_code = code
		r._content = message
		raise requests.HTTPError(response=r)

