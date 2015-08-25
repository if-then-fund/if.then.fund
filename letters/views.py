from django.shortcuts import render
from django.http import Http404, HttpResponse
from django.conf import settings
from django.utils import timezone
from django.core import serializers

import json

from .models import LettersCampaign, ConstituentInfo
from contrib.utils import json_response
from votervoice import VoterVoiceAPIClient

# VoterVoice API client.
votervoice = VoterVoiceAPIClient(settings.VOTERVOICE_API_KEY)

# All states with representation in Congress, for validating addresses.
state_abbrs = ['AK', 'AL', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'GU', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VI', 'VT', 'WA', 'WI', 'WV', 'WY']

# States with an at-large representative.
state_at_large = ['AK', 'DE', 'MT', 'ND', 'SD', 'VT', 'WY']

# Territories with an at-large non-voting delegate and no senators.
state_no_senators = ['AS', 'DC', 'GU', 'MP', 'PR', 'VI']

def sort_honorific_options(options):
	# VoterVoice gives us the the answers. But we don't like the male-normative and marriage-normative ordering.
	# Sort according to our order for known values. Put other known values at the end, in the original order.
	# (There are no unknown values currently, but this could change.)
	sort_order = { "Ms.": 0, "Mrs.": 1, "Mr.": 2 }
	if options is None: options = sort_order.keys()
	return sorted(options, key = lambda x : sort_order.get(x, 999))

@json_response
def find_reps(request):
	# BASIC VALIDATION
	if request.method != "POST": raise Http404()
	try:
		# Which campaign is this?
		campaign = LettersCampaign.objects.get(id=request.POST.get('campaign'))
	except:
		raise Http404()

	# Validate the address and get district information.
	try:
		constit_info = validate_address(request, campaign, for_ui=True)
	except ValidationError as e:
		return e.response

	# Get info on who represents this district, using our own
	# data because we will later link this up with any known
	# position of the Actor on an issue.
	from contrib.models import Actor
	ret = constit_info.extra
	ret['mocs'] = []
	def add_actor(obj):
		if obj is None: return
		ret['mocs'].append({
			"id": obj.id,
			"name": obj.name_long,
		})
	if campaign.target_representatives:
		add_actor(Actor.objects.filter(office='H-%s-%02d' % (constit_info.extra['address']['addrState'], constit_info.extra['congressional_district']['district'])).first())
	if campaign.target_senators:
		for senate_class in (1, 2, 3):
			add_actor(Actor.objects.filter(office='S-%s-%02d' % (constit_info.extra['address']['addrState'], senate_class)).first())

	if len(ret["mocs"]) == 0:
		if not campaign.target_senators:
			# Just representatives. One office. Singular.
			raise {
				"error": "Your congressional office is currently vacant, so we cannot submit a letter on your behalf at this time.",
			}
		else:
			# Senators (or senators and representative). Multiple offices - plural.
			raise {
				"error": "Your congressional offices are currently vacant, so we cannot submit a letter on your behalf at this time.",
			}

	return ret

class ValidationError(Exception):
	def __init__(self, response):
		self.response = response

def validate_address(request, campaign, for_ui):
	info = ConstituentInfo()
	info.extra = {
		"address": { },
	}

	#################################################################
	# VALIDATE ADDRESS FIELDS
	for field in ('addrAddress', 'addrCity', 'addrState', 'addrZip'):
		value = request.POST.get(field, '').strip()
		if not value:
			raise ValidationError({
				"error": "Please fill out the form completely.",
				"field": field,
			})
		info.extra["address"][field] = value

	# Additional validation for the state field. Is it a state with a
	# congressional district? (This is a <select> in the UI, so message
	# does not matter.)
	if info.extra["address"]['addrState'] not in state_abbrs:
		raise ValidationError({
			"error": "That's not a valid USPS state abbreviation.",
			"field": "state",
		})
	#################################################################

	#################################################################
	# GEOCODE THE ADDRESS
	# Use the VoterVoice API to get an Address record that
	# we pass to other VoterVoice calls. Cache this for a
	# very short time so that if the user gets to the next
	# step quickly, we don't have to re-check this.
	addressinfo = votervoice("GET", "addresses", {
		"address1": info.extra["address"]['addrAddress'],
		"city": info.extra["address"]['addrCity'],
		"state": info.extra["address"]['addrState'],
		"zipcode": info.extra["address"]['addrZip'],
		"country": 'US',
	}, {}, cache_duration=2)
	if addressinfo.get("message"):
		raise ValidationError({
			"error": addressinfo["message"],
		})
	if len(addressinfo.get("addresses", [])) == 0:
		raise ValidationError({
			"error": "We could not find your address. Please check it for errors.",
		})

	addressinfo = addressinfo["addresses"][0]

	if addressinfo['state'] != info.extra["address"]['addrState']:
		# The address could come back with information corrected. If
		# the state is corrected to something else, it'll be out of
		# sync with info.extra["address"]['addrState'], and that would
		# be bad.
		raise ValidationError({
				"error": "We could not find your address. Please check it for errors.",
			})
	#################################################################

	#################################################################
	# If this campaign is targetting senators only and the user lives in a district/territory
	# without senators, then we cannot proceed.
	if not campaign.target_representatives and info.extra["address"]['addrState'] in state_no_senators:
		return {
			"error": "We're only writing letters to senators, and unfortunately you do not have any senators.",
		}
	#################################################################

	#################################################################
	# DISTRICT LOOKUP
	# Use the VoterVoice API to get the user's congressional district
	# from their address.
	districtinfo = votervoice("GET", "districts", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"address": json.dumps(addressinfo, sort_keys=True), # sort the keys so that the request URL is stable so it can be cached
	}, {})
	for di in districtinfo:
		if di['electedBody'] == "US House":
			state = di.get('delegateGovernment', {}).get('uri', '...').split('/')[-1]
			if state != info.extra["address"]['addrState']: continue # sanity check
			district = int(di['districtId'])

			# District 1 is used for at-large districts, unlike my typical convention
			# of using 0. Fix that.
			if state in (state_at_large+state_no_senators) and district == 1:
				district = 0

			info.extra['congressional_district'] = { "congress": 114, "district": district }
			districtinfo = di
			break
	else:
		raise ValidationError({
			"error": "Your address does not appear to be within a United States congressional district.",
		})
	#################################################################

	#################################################################
	# GET MESSAGE TARGETS AND THEIR REQUIRED FORM FIELDS

	# Who are we sending to?
	groupIds = set()
	if campaign.target_senators: groupIds.add("US Senators")
	if campaign.target_representatives: groupIds.add("US Representative")

	# Get the targets for the letter. Pull out only representatives and senators.
	# I'm not sure if this is needed, but filter out anyone with canSend == False.
	target_groups = votervoice("GET", "advocacy/matchedtargets", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"home": json.dumps(addressinfo, sort_keys=True), # sort the keys so that the request URL is stable so it can be cached
	}, {})
	targets = []
	for target_group in target_groups:
		if target_group['groupId'] not in groupIds:
			# not sending to this sort of target (representative vs senator)
			continue
		for target in target_group['matches']:
			if not target['canSend']:
				# ever False?
				continue

			# remember these? useful?
			target['groupId'] = target_group['groupId']
			target['messageId'] = target_group['messageId']

			# get message delivery options for this target
			mdo = votervoice("GET", "advocacy/messagedeliveryoptions", {
				"association": settings.VOTERVOICE_ASSOCIATION,
				"targettype": target["type"],
				"targetid": target["id"],
				}, {})

			# is there a delivery method? is this ever a problem?
			if len(mdo) == 0:
				continue
			target["mdo"] = mdo[0]

			# Assign stable identifiers for required questions so we can match
			# up the responses to the form.
			import hashlib
			for rq in mdo[0].get('requiredQuestions', []):
				rq['id'] = hashlib.sha1((str(target['id']) + "," + rq['question']).encode("utf8")).hexdigest()

			# keep this target
			targets.append(target)
	#################################################################

	#################################################################
	# Is there anyone to send a letter to?
	if len(targets) == 0:
		# There are several reasons the list of targets might be empty: An error
		# in matching from the address, we're sending to senators only and this
		# person is in a U.S. district/territory, or the offices are all vacant.
		return {
			"error": "We cannot send your letter at this time. Your congressional office(s) may be vacant.",
		}
	#################################################################

	#################################################################
	# What fields are required to submit this message? Pool all of
	# options across targets since we have one form for all targets.
	requiredUserFields = set()
	sharedQuestions = set()
	requiredQuestions = []
	for target in targets:
		requiredUserFields |= set(target["mdo"].get("requiredUserFields", []))
		sharedQuestions |= set(target["mdo"].get("sharedQuestionIds", []))
		requiredQuestions.extend(target["mdo"].get("requiredQuestions", []))

	# Map sharedQuestion IDs to their full info. Put an 'id' field on the
	# result so we still have it.
	def get_shared_question_details(question_id):
		ret = votervoice("GET", "advocacy/sharedquestions/" + question_id, {}, {})
		ret["id"] = question_id
		return ret
	sharedQuestions = list(map(lambda id : get_shared_question_details(id), sharedQuestions))
	#################################################################

	#################################################################
	# Collapse CommonHonorific and CommunicatingWithCongressHonorific.
	prefix_options = None
	if for_ui:
		for q in list(sharedQuestions): # clone
			if q["id"] in ('CommonHonorific', 'CommunicatingWithCongressHonorific'):
				if prefix_options is None:
					prefix_options = set(q['validAnswers'])
				else:
					# Take intersection of options.
					prefix_options &= set(q['validAnswers'])
				sharedQuestions.remove(q)
	prefix_options = list(sort_honorific_options(prefix_options))
	#################################################################


	# Store VoterVoice API results.
	info.extra['votervoice'] = {
		"querytime": timezone.now().isoformat(),
		"addressinfo": addressinfo,
		"district": districtinfo,
		"targets": targets,
		"fields": {
			"requiredUserFields": list(requiredUserFields),
			"sharedQuestions": sharedQuestions,
			"requiredQuestions": requiredQuestions,
			"prefix_options": prefix_options,
		}
	}

	return info

@json_response
def write_letter(request):
	#################################################################
	# BASIC VALIDATION
	if request.method != "POST": raise Http404()
	try:
		# Which campaign is this?
		campaign = LettersCampaign.objects.get(id=request.POST.get('campaign'))
	except:
		raise Http404()
	#################################################################


	#################################################################
	# EMAIL VALIDATION
	# Get and validate email address. This is nice to do ahead of
	# validate_address because it is cheaper and will detect when
	# the form hasn't been filled out yet.
	from email_validator import validate_email, EmailNotValidError
	try:
		email = request.POST.get('email', '').strip()
		if not email: raise EmailNotValidError("Enter an email address.")
		email = validate_email(email)
	except EmailNotValidError as e:
		return {
			"error": str(e),
			"field": "email",
		}
	#################################################################

	#################################################################
	# ADDRESS VALIDATION/GET TARGETS
	# Validate the address and get district information, message targets,
	# and required form fields for those targets. The user has already
	# done this part once, so it should go through OK.
	try:
		constit_info = validate_address(request, campaign, for_ui=False)
	except ValidationError as e:
		return { "error": e.response }
	#################################################################

	#################################################################
	# NAME VALIDATION
	# Validate the name fields that we get from all users.
	constit_info.extra['name'] = { }
	for field in ('namePrefix', 'nameFirst', 'nameLast', 'phone'):
		value = request.POST.get(field, '').strip()
		if not value and field != 'phone':
			# phone is often optional, so we won't validate it here
			return {
				"error": "Please fill out the form completely.",
				"field": field,
			}
		constit_info.extra['name'][field] = value
	#################################################################


	#################################################################
	# BUILD MESSAGES.
	# Build up the messages and validate dynamic fields.
	messages = []
	for target in constit_info.extra['votervoice']['targets']:
		# Build the response data structure. Since we may have a
		# different message per target, build a complete UserAdvocacyMessage
		# for each TargetDeliveryContract.
		response = {
			"subject": "this is the subject",
		    "body": "this is the message body",
		    "complimentaryClose": "Sincerely,",
		    "modified": False, # did user edit the message?

			"targets": [{
			"type": "H",
			"id": target["id"],
			"deliveryMethod": target["mdo"]["deliveryMethod"],
			"questionnaire": [],
			}]
		}
		messages.append(response)

		# Validate that we have all of the required user fields.
		for f in target["mdo"].get("requiredUserFields", []):
			if f == "phone":
				# The phone number goes into the user information. We
				# validate it here but don't include it in the message
				# data.
				if not constit_info['name']['phone']:
					return {
						"error": "Please fill out the form completely.",
						"field": "phone",
					}
			elif f in ("email", "address"):
				# We got these.
				pass
			else:
				# Don't know how to collect this.
				return {
					"error": "Error #3: %d/%s." % (target['id'], f),
				}

		# Validate that we have all of the shared questions.

		def get_extra_field_value(question_type, question_id, target):
			qid = 0
			while True:
				if not request.POST.get('extra-%d-type' % qid):
					# no more extra fields
					break
				if request.POST.get('extra-%d-type' % qid) == question_type \
					and request.POST.get('extra-%d-id' % qid) == question_id:
					value = request.POST.get('extra-%d-value' % qid, '')
					if not value:
						return {
							"error": "Please fill out the form completely.",
							"field": 'extra-%d-value' % qid,
						}
					return value
				qid += 1
			return {
				"error": "Error #4: %d/%s." % (target['id'], question_id),
			}

		for sqid in target["mdo"].get("sharedQuestionIds", []):
			if sqid in ("CommonHonorific", "CommunicatingWithCongressHonorific"):
				# These are handled by our prefix field, which we treat as
				# always required.
				value = request.POST.get('namePrefix', '').strip()
			else:
				value = get_extra_field_value("shared", sqid, target)
				if isinstance(value, dict):
					# Validation failed.
					return value
			response['targets'][0]["questionnaire"].append({
				"question": sqid,
				"answer": value,
			})

		# Validate that we have all of the required questions.

		for rq in target["mdo"].get("requiredQuestions", []):
			value = get_extra_field_value("required", rq["id"], target)
			if isinstance(value, dict):
				# Validation failed.
				return value
			response['targets'][0]["questionnaire"].append({
				"question": rq["question"],
				"answer": value,
			})
	#################################################################

	#################################################################
	# GET OR CREATE THE VOTERVOICE USER
	# We've now validated all of the user input so that we're able to
	# submit a message for delivery. But we first have to create a User.
	#################################################################

	

	return {
		"status": repr(messages),
	}