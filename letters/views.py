from django.shortcuts import render
from django.http import Http404, HttpResponse
from django.conf import settings
from django.core.cache import cache
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

def vv_get_shared_question(question_id):
	key = "votervoice_sharedquestion_" + question_id
	ret = cache.get(key)
	if not ret:
		ret = votervoice("GET", "advocacy/sharedquestions/" + question_id, {})
		cache.set(key, ret, 60*15) # 15 minutes
	return ret

def get_honorific_options():
	# VoterVoice gives us the the answers. But we don't like the male-normative and marriage-normative ordering.
	# Sort according to our order for known values. Put other known values at the end, in the original order.
	# (There are no unknown values currently, but this could change.)
	sort_order = { "Ms.": 0, "Mrs.": 1, "Mr.": 2 }
	options = vv_get_shared_question("CommonHonorific")["validAnswers"]
	options.sort(key = lambda x : sort_order.get(x, 999))
	return options

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
		constit_info = validate_address(request, campaign)
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
		add_actor(Actor.objects.filter(office='H-%s-%02d' % (constit_info.extra['addrState'], constit_info.extra['congressional_district']['district'])).first())
	if campaign.target_senators:
		for senate_class in (1, 2, 3):
			add_actor(Actor.objects.filter(office='S-%s-%02d' % (constit_info.extra['addrState'], senate_class)).first())

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

def validate_address(request, campaign):
	info = ConstituentInfo()
	info.extra = { }

	# Get and validate string fields.
	for field in ('addrAddress', 'addrCity', 'addrState', 'addrZip'):
		value = request.POST.get(field, '').strip()
		if not value:
			raise ValidationError({
				"error": "Please fill out the form completely.",
				"field": field,
			})
		info.extra[field] = value

	# Validate state field.
	if info.extra['addrState'] not in state_abbrs:
		raise ValidationError({
			"error": "That's not a valid USPS state abbreviation.",
			"field": "state",
		})

	# ADDRESS VALIDATION/GEOCODING

	# Validate the user's address and get an Address record that
	# we pass to other VoterVoice calls.
	addressinfo = votervoice("GET", "addresses", {
		"address1": info.extra['addrAddress'],
		"city": info.extra['addrCity'],
		"state": info.extra['addrState'],
		"zipcode": info.extra['addrZip'],
		"country": 'US',
	})
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

	# If this campaign is targetting senators only and the user lives in a district/territory
	# without senators, then we cannot proceed.
	if not campaign.target_representatives and info.extra['addrState'] in state_no_senators:
		return {
			"error": "We're only writing letters to senators, and unfortunately you do not have any senators.",
		}

	# Get the user's congressional district.
	districtinfo = votervoice("GET", "districts", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"address": json.dumps(addressinfo),
	})
	for di in districtinfo:
		if di['electedBody'] == "US House":
			state = di.get('delegateGovernment', {}).get('uri', '...').split('/')[-1]
			if state != info.extra['addrState']: continue # sanity check
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

	# Store VoterVoice API results.
	info.extra['votervoice'] = {
		"querytime": timezone.now().isoformat(),
		"addressinfo": addressinfo,
		"district": districtinfo,
	}

	return info

@json_response
def write_letter(request):
	# BASIC VALIDATION
	if request.method != "POST": raise Http404()
	try:
		# Which campaign is this?
		campaign = LettersCampaign.objects.get(id=request.POST.get('campaign'))
	except:
		raise Http404()

	# FORM VALIDATION

	# Get and validate email address.
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

	# Validate the address and get district information.
	try:
		constit_info = validate_address(request, campaign)
	except ValidationError as e:
		return e.response

	# Validate name/phone string fields.
	for field in ('namePrefix', 'nameFirst', 'nameLast', 'phone'):
		value = request.POST.get(field, '').strip()
		if not value:
			return {
				"error": "Please fill out the form completely.",
				"field": field,
			}
		constit_info.extra[field] = value


	# Who are we sending to?
	groupIds = set()
	if campaign.target_senators: groupIds.add("US Senators")
	if campaign.target_representatives: groupIds.add("US Representative")

	# Get the targets for the letter. Pull out only representatives and senators.
	# I'm not sure if this is needed, but filter out anyone with canSend == False.
	target_groups = votervoice("GET", "advocacy/matchedtargets", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"home": json.dumps(constit_info.extra['votervoice']['addressinfo']),
	})
	targets = []
	for target_group in target_groups:
		if target_group['groupId'] not in groupIds: continue # not sending to this sort of target (representative vs senator)
		for target in target_group['matches']:
			if not target['canSend']:
				# ever False?
				continue

			# remember these? useful?
			target['groupId'] = target_group['groupId']
			target['messageId'] = target_group['messageId']

			# get message delivery options
			key = "votervoice_mdo_" + str(target['id'])
			mdo = cache.get(key)
			if not mdo:
				mdo = votervoice("GET", "advocacy/messagedeliveryoptions", {
					"association": settings.VOTERVOICE_ASSOCIATION,
					"targettype": target["type"],
					"targetid": target["id"],
					})
				cache.set(key, mdo, 60*15) # 15 minutes

			# is there a delivery method? is this ever a problem?
			if len(mdo) == 0:
				continue
			target["mdo"] = mdo[0]

			# keep this target
			targets.append(target)
	

	# Is there anyone to send a letter to?
	if len(targets) == 0:
		# There are several reasons the list of targets might be empty: An error
		# in matching from the address, we're sending to senators only and this
		# person is in a U.S. district/territory, or the offices are all vacant.
		if not campaign.target_senators:
			return {
				"error": "We cannot send your letter at this time. Your congressional office may be vacant, or your address is not be within a United States congressional district.",
			}
		else:
			return {
				"error": "We cannot send your letter at this time. (Error 2.)",
			}

	# Do we need to collect additional information?
	#for target in targets

	return {
		"error": repr(targets)
	}


	return {
		"status": "ok",
	}