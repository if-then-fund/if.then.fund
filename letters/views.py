from django.shortcuts import render
from django.http import Http404, HttpResponse
from django.conf import settings
from django.utils import timezone
from django.core import serializers

from .models import LettersCampaign, ConstituentInfo, UserLetter, VoterRegistrationStatus
from contrib.models import Actor, Action
from contrib.utils import json_response
from votervoice import VoterVoiceAPIClient, VoterVoiceDummyAPIClient

# VoterVoice API client.
if settings.VOTERVOICE_API_KEY:
	votervoice = VoterVoiceAPIClient(settings.VOTERVOICE_API_KEY)
else:
	# When debugging, use our stub library.
	votervoice = VoterVoiceDummyAPIClient()

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

	# Return who we are writing the letter to, plus any
	# questions we have to ask the user.
	ret = constit_info.extra
	ret['my_representatives'] = list(get_extended_target_info(campaign, constit_info).values())
	ret['my_representatives'].sort(key = lambda x : x['sort'])

	# If there are no targets, then the user cannot go on.
	if len(ret["my_representatives"]) == 0:
		if not campaign.target_senators:
			# Just representatives. One office. Singular.
			return {
				"error": "Your congressional office is currently vacant, so we cannot submit a letter on your behalf at this time.",
			}
		else:
			# Senators (or senators and representative). Multiple offices - plural.
			return {
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
	# VALIDATE FIELDS
	#################################################################

	for field in ('addrAddress', 'addrCity', 'addrState', 'addrZip', 'voterRegistration'):
		value = request.POST.get(field, '').strip()
		if not value:
			raise ValidationError({
				"error": "Please fill out the form completely.",
				"field": field,
			})
		if field == 'voterRegistration':
			try:
				value = VoterRegistrationStatus[value].name # string => enum => string
			except ValueError:
				raise ValidationError({
					"error": "That's not a valid voter registration status.",
					"field": "voterRegistration",
				})
			info.extra[field] = value
		else:
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
	# GEOCODE THE ADDRESS
	# Use the VoterVoice API to get an Address record that
	# we pass to other VoterVoice calls. Cache this for a
	# very short time so that if the user gets to the next
	# step quickly, we don't have to re-check this.
	#################################################################

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
	# If this campaign is targetting senators only and the user lives in a district/territory
	# without senators, then we cannot proceed.
	#################################################################
	if not campaign.target_representatives and info.extra["address"]['addrState'] in state_no_senators:
		return {
			"error": "We're only writing letters to senators, and unfortunately you do not have any senators.",
		}

	#################################################################
	# DISTRICT LOOKUP
	# Use the VoterVoice API to get the user's congressional district
	# from their address.
	#################################################################
	districtinfo = votervoice("GET", "districts", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"address": addressinfo,
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
	# GET MESSAGE TARGETS AND THEIR REQUIRED FORM FIELDS
	#################################################################

	# Who are we sending to?
	groupIds = set()
	if campaign.target_senators: groupIds.add("US Senators")
	if campaign.target_representatives: groupIds.add("US Representative")

	# Get the targets for the letter. Pull out only representatives and senators.
	target_groups = votervoice("GET", "advocacy/matchedtargets", {
		"association": settings.VOTERVOICE_ASSOCIATION,
		"home": addressinfo,
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

	# Is there anyone to send a letter to?
	if len(targets) == 0:
		# There are several reasons the list of targets might be empty: An error
		# in matching from the address, we're sending to senators only and this
		# person is in a U.S. district/territory, or the offices are all vacant.
		raise ValidationError({
			"error": "We cannot send your letter at this time. Your congressional office(s) may be vacant.",
		})

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
	# Collapse CommonHonorific and CommunicatingWithCongressHonorific
	#################################################################
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
	#################################################################

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

def get_extended_target_info(campaign, constit_info):
	# Get whether the target is known to support or oppose the issue
	# and customize the letter subject & body depending on this.
	#
	# Also add boilerplate to the top of the letter.

	# for boilerplate, we'll need this:
	my_voter_registration_status = {
		VoterRegistrationStatus.Registered.name: "I am registered to vote.\n\n",
		VoterRegistrationStatus.Registering.name: "I am registering to vote.\n\n",
		VoterRegistrationStatus.NotRegistered.name: "",
		VoterRegistrationStatus.TooYoung.name: "I am currently too young to register to vote but will be sharing your response with my parents and everyone else I know in this district who is of voting age.\n\n",
	}[constit_info.extra['voterRegistration']]

	def toggle_string(outcome, string_default, string_0, string_1):
		if outcome is None:
			return string_default
		elif (outcome == 0) and string_0:
			return string_0
		elif (outcome == 1) and string_1:
			return string_1
		else:
			return string_default

	ret = { }
	for target in constit_info.extra["votervoice"]["targets"]:
		# Basic info for display to the end user.
		inf = {
			# default info on target
			"name": target['name'],
			"position": None,
			"sort": target['name'],

			# default strings
			"message_subject": campaign.message_subject,
			"message_body": campaign.message_body,
		}
		ret[target['id']] = inf
		gender = None

		# Do we have an Actor for this target?
		actor = Actor.objects.filter(votervoice_id=target['id']).first()
		if actor:
			# Update with better name info (our database is better).
			inf.update({
				"name": actor.name_long,
				"sort": actor.name_sort,
			})
			gender = actor.extra.get("legislators-current", {}).get("bio", {}).get("gender")

			# Do we have a recorded position for this person?
			if campaign.body_toggles_on:
				axn = Action.objects.filter(execution__trigger=campaign.body_toggles_on, actor=actor).first()
				if axn:
					inf.update({
						# Record position.
						'position': axn.outcome,

						# Override default message subject/body if outcome corresponds to a non-empty override string.
						'message_subject': toggle_string(axn.outcome, campaign.message_subject, campaign.message_subject0, campaign.message_subject1),
		    			'message_body': toggle_string(axn.outcome, campaign.message_body,campaign.message_body0, campaign.message_body1),
					})

		# Fill-in default string.
		if inf['position'] is None:
			inf['position_text'] = "We don’t yet know where %s stands on this issue." % { "M": "he", "F": "she" }.get(gender, inf['name'])
		else: # beware zero is a possible value
			inf['position_text'] = campaign.body_toggles_on.outcome_strings()[inf['position']]['label']

		# Add boilerplate text to the message body.
		inf['message_body'] = \
			   "I live in your district.\n\n" \
			 + my_voter_registration_status \
			 + inf['message_body'].strip()

		# Add Markdown-rendered body for previewing.
		import markdown2
		inf['message_body_rendered'] = markdown2.markdown(inf['message_body'], safe_mode=True)

	return ret

@json_response
def write_letter(request):
	#################################################################
	# BASIC VALIDATION
	#################################################################
	if request.method != "POST": raise Http404()
	try:
		# Which campaign is this?
		campaign = LettersCampaign.objects.get(id=request.POST.get('campaign'))
	except:
		raise Http404()


	#################################################################
	# EMAIL VALIDATION
	# Get/validate/normalize email address. This is nice to do ahead of
	# validate_address because it is cheaper and will detect when
	# the form hasn't been filled out yet. Set allow_smtputf8=False
	# because we don't know if the VoterVoice stack supports it.
	#################################################################
	from email_validator import validate_email, EmailNotValidError
	try:
		email = request.POST.get('email', '').strip()
		if not email: raise EmailNotValidError("Enter an email address.")
		email = validate_email(email, allow_smtputf8=False)['email']
	except EmailNotValidError as e:
		return {
			"error": str(e),
			"field": "email",
		}


	#################################################################
	# ADDRESS VALIDATION/GET TARGETS
	# Validate the address and get district information, message targets,
	# and required form fields for those targets. The user has already
	# done this part once, so it should go through OK.
	#################################################################
	try:
		constit_info = validate_address(request, campaign, for_ui=False)
	except ValidationError as e:
		return e.response


	#################################################################
	# NAME VALIDATION
	# Validate the name fields that we get from all users.
	#################################################################
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
	# TOGGLE ON KNOWN POSITIONS
	# Toggle the subject/body depending on any known positions of the
	# target politician.
	#################################################################
	target_positions = get_extended_target_info(campaign, constit_info)

	#################################################################
	# BUILD MESSAGES.
	# Build up the messages and validate dynamic fields.
	#################################################################
	messages = []
	for target in constit_info.extra['votervoice']['targets']:
		# Build the response data structure. Since we may have a different
		# message per target, build a complete UserAdvocacyMessage for
		# each TargetDeliveryContract. We've already selected the message
		# text in get_extended_target_info.

		response = {
			"subject": target_positions[target['id']]['message_subject'],
		    "body": target_positions[target['id']]['message_body'],
		    "complimentaryClose": "Sincerely,", # also says this in the preview
		    "modified": False, # did user edit the message?

			"targets": [{
				"type": "H",
				"id": target["id"],
				"deliveryMethod": target["mdo"]["deliveryMethod"],
				"questionnaire": [],
			}]
		}
		messages.append({
			"target_name": target["name"],
			"votervoice_target": target,
			"votervoice_response": response,
		})

		# Validate that we have all of the required user fields.
		for f in target["mdo"].get("requiredUserFields", []):
			if f == "phone":
				# The phone number goes into the user information. We
				# validate it here but don't include it in the message
				# data.
				if not constit_info.extra['name']['phone']:
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
	# GET OR CREATE THE VOTERVOICE USER
	# We've now validated all of the user input so that we're able to
	# submit a message for delivery. But we first have to create a User.
	#################################################################

	# Create the data structure.
	user = {
		"emailAddress": email,
		"honorific": constit_info.extra['name']['namePrefix'],
		"givenNames": constit_info.extra['name']['nameFirst'],
		"surname": constit_info.extra['name']['nameLast'],
		"homeAddress": constit_info.extra['votervoice']['addressinfo'],
		"phoneNumber": constit_info.extra['name']['phone'],
	}

	didVerifyEmail = False
	import requests
	if request.POST.get('vv-email-confirm-email') != email:
		# This is a normal first attempt to submit the form.

		# Create/update the user, getting back { "userId": 1, "userToken": "USER_TOKEN" }.
		try:
			# "You will see a HTTP status code of 200 or 201 depending on if an
			# existing user's information was updated or created respectively."
			user_info = votervoice("POST", "users", {
					"association": settings.VOTERVOICE_ASSOCIATION,
				},
				user)
		except requests.HTTPError as e:
			if e.response.status_code != 409:
				# 4xx (except 409): General validation error.
				return {
					"error": e.response.text,
				}
			else:
				# "The user's information matched to an already existing user on our
				# end and the information sent by your POST was significantly different
				# that what we have in our system. You will see a HTTP status code of
				# 409 when this occurs. In order to proceed in this case, you will
				# have to verify user identify and user data ownership using the
				# following process."

				# VoterVoice will send the user an email. We get back:
				# { "verificationId":"VERIFICATION_ID" }.
				try:
					email_verif_id = votervoice("POST", "emailownershipverifications", {
							"association": settings.VOTERVOICE_ASSOCIATION,
						},
						{
						    "emailAddress": email,
						})
				except requests.HTTPError as e:
					if e.response.status_code == 429:
						# We seem to get this if we try to send too many email verification
						# emails at once? Not exactly sure.
						return { "error": "It looks like you've submitted the form too many times. Wait a minute and then try again." }
					raise

				# Ask the user to wait and enter the verification code.
				return {
					"status": "vv-verify-email",
					"for_email": email,
					"verificationId": email_verif_id['verificationId'],
				}

	else:
		# This is a second attempt with an email verification code.
		# (See below for how we get here.)

		# Pass the email verification code back to VoterVoice.
		if request.POST.get('vv-email-confirm-verif-code', '').strip() == "":
			return {
				"error": "Enter the email verification code we have just emailed you.",
				"field": "vv-email-confirm-verif-code",
			}

		try:
			email_verif_proof = votervoice("POST", "emailownershipverifications/" + request.POST.get('vv-email-confirm-verif-id', '') + "/proof", { },
				{
				    "code": request.POST.get('vv-email-confirm-verif-code', ''),
				})
			didVerifyEmail = True
		except requests.HTTPError as e:
			# Verification code was incorrect.
			return {
				"error": "The email verification code was not correct. Please check that you copied it correct.",
			}

		# Get the existing user info.
		existing_user = votervoice("GET", "users/identities",
			{
				"email": email,
				"ownershipProof": email_verif_proof["proof"]
			}, {})
		if len(existing_user) == 0:
			return {
				"error": "Something went wrong, sorry. Error #5.",
			}

		# Set additional fields on user so we can submit the new fields.
		user['userId'] = existing_user[0]['id']
		user_token = existing_user[0]['token']

		# Update user.
		try:
			votervoice("PUT", "users/" + user_token, {
					"association": settings.VOTERVOICE_ASSOCIATION,
				},
				user)
		except requests.HTTPError as e:
			# Something went wrong updating the user. Maybe a validation error.
			return {
				"error": e.response.text,
			}

		# PUT doesn't give us back anything. Assemble the user_info we need.
		user_info = { "userId": user['userId'], "userToken": user_token }


	# We have user_info now. Put user ID and token into the constit_info structure.
	constit_info.extra['votervoice']['user'] = user_info

	#################################################################
	# SAVE WHAT WE HAVE SO FAR
	#################################################################

	letter = UserLetter()
	letter.letterscampaign = campaign

	# ref_code (i.e. utm_campaign code) and Campaign ('via_campaign')
	from itfsite.models import Campaign, AnonymousUser
	from contrib.views import get_sanitized_ref_code
	letter.ref_code = get_sanitized_ref_code(request)
	letter.via_campaign = Campaign.objects.get(id=request.POST['via_campaign'])

	# Set user from logged in state.
	if request.user.is_authenticated():
		letter.user = request.user
		exists_filters = { 'user': letter.user }
	else:
		# If the user makes multiple actions anonymously, we'll associate
		# a single AnonymousUser instance. Use an AnonymousUser stored in
		# the session (if it's for the same email address as entered on)
		# the form. If none is in the session, create one and add it to
		# the session.
		anon_user = AnonymousUser.objects.filter(id=request.session.get("anonymous-user")).first()
		if anon_user and anon_user.email == email:
			letter.anon_user = anon_user
		else:
			letter.anon_user = AnonymousUser.objects.create(email=email)
			request.session['anonymous-user'] = letter.anon_user.id
		exists_filters = { 'anon_user': letter.anon_user }

	# If the user has already written a letter on this subject, it is probably a
	# synchronization problem. Just redirect to that pledge.
	letter_exists = UserLetter.objects.filter(letterscampaign=campaign, **exists_filters).first()
	if letter_exists is not None:
		return { "status": "already-wrote-a-letter" }

	letter.congressional_district = "%s%02d" % (
		constit_info.extra['address']['addrState'],
		constit_info.extra['congressional_district']['district']
		)

	constit_info.save()
	letter.profile = constit_info
	letter.extra = {
		"messages_queued": messages,
	}
	letter.save()

	#################################################################
	# SEND EMAIL VERIFICATION EMAILS WHERE NECESSARY
	#################################################################

	if letter.anon_user:
		# This was made by an anonymous user.
		if didVerifyEmail:
			# But the user just confirmed their email address via VoterVoice.
			# If we ask them to confirm their email address again, that's
			# going to be weird. We'll confirm their address immediately...
			user = letter.anon_user.email_confirmed(email, request)

			# Then log them in and redirect them to the welcome page to
			# set a password.
			from itfsite.accounts import first_time_confirmed_user
			welcome_url = first_time_confirmed_user(request, user, letter.via_campaign.get_absolute_url(), just_get_url=True)
			if welcome_url is not None:
				return {
					"status": "needs-password",
					"redirect": welcome_url,
				}

		else:
			# Start the usual email verification process.
			letter.anon_user.send_email_confirmation()

	return {
		"status": "ok",
		#"html": render_letter_template(request, letter),
		"sent_to": letter.indented_recipients,
	}

def get_user_letters(user, request):
	# see contrib.get_user_pledges
	from django.db.models import Q
	filters = Q(id=-99999) # dummy, exclude all
	if user and user.is_authenticated():
		filters |= Q(user=user)
	anon_user = request.session.get("anonymous-user")
	if anon_user is not None:
		filters |= Q(anon_user_id=anon_user)
	return UserLetter.objects.filter(filters)

def render_letter_template(request, letter, show_long_title=False):
	# Get the user's pledges, if any, on any trigger tied to this campaign.
	import django.template
	template = django.template.loader.get_template("letters/letter.html")
	return template.render(django.template.RequestContext(request, {
		"show_long_title": show_long_title,
		"letter": letter,
		"share_url": request.build_absolute_uri(letter.via_campaign.get_short_url()),
	}))

def get_recent_letter_defaults(user, request):
	letter = get_user_letters(request.user, request).order_by('-created').first()
	if not letter: return None
	return {
		"email": letter.get_email(),
		"profile": letter.profile.extra,
	}