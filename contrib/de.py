import decimal
import json
import requests
from requests.auth import HTTPDigestAuth

class HumanReadableValidationError(Exception):
	pass

class DemocracyEngineAPIClient(object):
	de_meta_info = None

	def __init__(self, api_baseurl, account_number, username, password, fees_recipient_id):
		self.api_baseurl = api_baseurl
		self.account_number = account_number
		self.username = username
		self.password = password
		self.fees_recipient_id = fees_recipient_id
		self.debug = False

	def __call__(self, method, post_data=None, argument=None, live_request=False, http_method=None):

		# Cache meta info. If method is None, don't infinite recurse.
		if (self.de_meta_info == None) and (method is not None):
			self.de_meta_info = self(None, None, live_request=live_request)

		if method is None:
			# This is an internal call to get the meta subscriber info.
			url = self.api_baseurl + ('/subscribers/%s.json' % self.account_number)
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

		# Log requests. Definitely don't do this in production since we'll
		# have sensitive data here!
		if self.debug:
			print(urlopen.__name__.upper(), url)
			if payload:
				print(json.dumps(json.loads(payload), indent=True))
			print()

		# issue request
		r = urlopen(
			url,
			auth=HTTPDigestAuth(self.username, self.password),
			data=payload,
			headers=headers,
			timeout=30 if not live_request else 20,
			verify=True, # check SSL cert (is default, actually)
			)

		# raises exception on anything but 200 OK
		try:
			r.raise_for_status()
		except:
			try:
				exc = r.json()
				if isinstance(exc, list) and len(exc) > 0 and exc[0][0] == "base":
					# Not sure what 'base' means, but we get things like
					# "Card number is not a valid credit card number".
					raise HumanReadableValidationError(exc[0][1])
				if isinstance(exc, dict) and isinstance(exc.get('base'), list):
					# Not sure what 'base' means, but we get things like
					# "Card number is not a valid credit card number".
					raise HumanReadableValidationError(exc.get('base')[0])
			except HumanReadableValidationError:
				raise # pass through/up
			except:
				pass # fall through to next

			import sys
			print(urlopen.__name__.upper(), url)
			if payload: print(payload)
			print()
			print(r.content, file=sys.stderr)
			raise IOError("DemocrayEngine API failed: %d %s" % (r.status_code, url))

		# The PUT requests have no response. A 200 response is success.
		if http_method == "put":
			return None

		# all other responses are JSON
		return r.json()

	def recipients(self, live_request=False):
		return self(method="recipients", live_request=live_request)

	def get_recipient(self, id, live_request=False, http_method=None):
		return self(method="recipient", argument=('recipient_id', id), http_method=http_method, live_request=live_request)

	def transactions(self, live_request=False):
		return self(method="transactions", live_request=live_request)

	def get_transaction(self, id, live_request=False):
		return self(method="transaction", argument=('transaction_id', id), live_request=live_request)

	def void_transaction(self, id):
		return self(method="transaction_void", argument=('transaction_id', id), http_method="put")

	def credit_transaction(self, id):
		return self(method="transaction_credit", argument=('transaction_id', id), http_method="put")

	def create_donation(self, info):
		return self(
			method="donation_process",
			post_data=
				{ "donation": info },
			)

	@staticmethod
	def format_decimal(value):
		# Dollar amounts passed to Democracy Engine must be formatted
		# exactly as $####.##, with exactly two decimal places. This
		# is a helper function to format Decimal instances this way.
		try:
			sign, digits, exp = value.quantize(decimal.Decimal('0.01')).as_tuple()
		except decimal.InvalidOperation:
			raise ValueError("Rounding issue with %s." % value)
		if sign != 0:
			raise ValueError("Rounding issue with %s (sign=%d)." % (value, sign))
		if exp != -2:
			raise ValueError("Rounding issue with %s (^%d)." % (value, exp))

		# Format with dollar sign, decimal point, and at least enough
		# zeroes to have a zero before the decimal point (and of course
		# two after).
		digits = [str(d) for d in digits]
		while len(digits) < 3: digits.insert(0, '0')
		return "$%s.%s" % (''.join(digits[:-2]), ''.join(digits[-2:]))


class DummyDemocracyEngineAPIClient(object):
	"""A stand-in for the DE API for unit tests."""

	fees_recipient_id = "DUMMY_RECIP_ID"

	issued_tokens = set()

	def create_donation(self, info):
		if info.get('token_request'):
			import random, hashlib
			token = hashlib.md5(str(random.random()).encode('ascii')).hexdigest()
			self.issued_tokens.add(token)
			return {
				"dummy_response": True,
				"token": token,
			}
		else:
			if not info['token'].startswith('_made_up_') and info['token'] not in self.issued_tokens:
				raise Exception("Charge on an invalid token.")
			return {
				"dummy_response": True,
			}

	@staticmethod
	def format_decimal(value):
		return DemocracyEngineAPIClient.format_decimal(value)
		

