from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings

import selenium.webdriver
from selenium.webdriver.support.ui import Select
import re
import time
import random
from datetime import timedelta
from decimal import Decimal

class SeleniumTest(StaticLiveServerTestCase):
	@classmethod
	def setUpClass(cls):
		super(SeleniumTest, cls).setUpClass()

		# Override the email backend so that we can capture it.
		from django.conf import settings
		settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

		# Replace the Democracy Engine API with our dummy class
		# so we don't make time consuming remote API calls.
		import contrib.bizlogic
		contrib.bizlogic.DemocracyEngineAPI = contrib.bizlogic.DummyDemocracyEngineAPI()

		# Likewise VoterVoice, and expecially since we don't have
		# a staging server to test against.
		import letters.views, votervoice
		letters.views.votervoice = votervoice.VoterVoiceDummyAPIClient()

		# Make sure we're looking at the right branded site.
		settings.DEFAULT_BRAND = "if.then.fund"

		# Start a headless browser.
		cls.browser = selenium.webdriver.Firefox()

		# We have a lot of AJAX that dynamically shows elements. Rather than
		# hard-coding time.sleep()'s, let Selenium poll for the element's
		# visibility up to this amount of time.
		cls.browser.implicitly_wait(6) # seconds

	@classmethod
	def tearDownClass(cls):
		super(SeleniumTest, cls).tearDownClass()

		# Terminate the debug server.
		cls.browser.quit()

	def setUp(self):
		# make it easier to access the browser instance by aliasing to self.browser
		self.browser = type(self).browser

		# clear the browser's cookies before each test
		self.browser.delete_all_cookies()

	def build_test_url(self, path):
		from urllib.parse import urljoin
		return urljoin(self.live_server_url, path)

	def follow_email_confirmation_link(self, test_string, already_has_account=False):
		# Get the email confirmation URL that we need to hit to confirm the user.
		msg = pop_email().body
		m = re.search(r"(http:\S*/ev/key/\S*/)", msg, re.S)
		self.assertTrue(m)
		conf_url = m.group(1)
		self.assertTrue(conf_url.startswith(settings.SITE_ROOT_URL))
		conf_url = conf_url.replace(settings.SITE_ROOT_URL + "/", "/")
		self.browser.get(self.build_test_url(conf_url))

		# Now we're at the "give a password" page.
		# It starts with a message that the pledge is confirmed.
		self.assertIn(test_string, self.browser.find_element_by_css_selector("#global_modal .modal-body").text)
		self.browser.find_element_by_css_selector("#global_modal .btn-default").click()

		# When the user already has an account, we're on an unspecified page
		# after seeing the message.
		if already_has_account: return None

		pw = '12345'
		self.browser.find_element_by_css_selector("#inputPassword").send_keys(pw)
		self.browser.find_element_by_css_selector("#inputPassword2").send_keys(pw)
		self.browser.find_element_by_css_selector("#welcome-form").submit()

		return pw

#####################################################################

class ContribTest(SeleniumTest):
	fixtures = ['fixtures/actor.yaml', 'fixtures/recipient.yaml']

	@classmethod
	def setUpClass(cls):
		super(ContribTest, cls).setUpClass()

		# Override the suggested pledge amount so we have a known value
		# to test against.
		import contrib.views
		contrib.views.SUGGESTED_PLEDGE_AMOUNT = 5

		# Override the test that bills we use are not dead.
		import contrib.legislative
		contrib.legislative.ALLOW_DEAD_BILL = True

	#########################################

	def create_test_campaign(self, bill_num, chamber, with_customization=False):
		# Create a Trigger.
		from contrib.models import Trigger, TriggerStatus, Pledge
		from contrib.legislative import create_trigger_from_bill
		t = create_trigger_from_bill(bill_num, chamber)
		t.status = TriggerStatus.Open
		t.save()

		# Create an organization and customization?
		org = None
		if with_customization:
			from itfsite.models import Organization, OrganizationType
			org = Organization.objects.create(
				name="Test Organization",
				slug="test-organization",
				orgtype=OrganizationType.C4,
				description="This is a test organization.",
				description_format=0,
				)

			from contrib.models import TriggerCustomization
			tcust = TriggerCustomization.objects.create(
				owner=org,
				trigger=t,
				incumb_challgr=-1,
				)

		from itfsite.models import Campaign, CampaignStatus, TextFormat
		campaign = Campaign.objects.create(
			brand=1,
			owner=org,
			title=t.title,
			slug=t.slug,
			subhead="This is a test campaign.",
			subhead_format=TextFormat.Markdown,
			headline="Do More Tests",
			body_text="This is a test campaign.",
			body_format=TextFormat.Markdown,
			status=CampaignStatus.Open,
			)
		campaign.contrib_triggers.add(t)

		return t, campaign


	def _test_pledge_simple(self, campaign,
			verb="vote",
			pledge_summary="You have scheduled a campaign contribution of $12.00 for this vote. It will be split among up to 435 representatives, each getting a part of your contribution if they VERB in favor of S. 1, but if they VERB against S. 1 their part of your contribution will go to their next general election opponent.",
			with_utm_campaign=False,
			break_after_email=False, return_from_incomplete_pledge=None,
			break_before_confirmation=False,
			use_email=None,
			):

		# what trigger is this associated with?
		trigger = campaign.contrib_triggers.first()

		# Open the Campaign page.

		# What URL?
		url = campaign.get_absolute_url()
		utm_campaign = None
		if with_utm_campaign:
			utm_campaign = "test_campaign_string"
			url += "?utm_campaign=" + utm_campaign

		# When testing an IncompletePledge, grab the return URL that it gives
		# which includes a utm_campaign string.
		if return_from_incomplete_pledge:
			utm_campaign = return_from_incomplete_pledge.get_utm_campaign_string()
			url = return_from_incomplete_pledge.get_return_url()

		# Load in browser. Check title.
		self.browser.get(self.build_test_url(url))
		self.assertRegex(self.browser.title, "Keystone XL")

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=0]').click()")
		#self.browser.find_element_by_css_selector("#pledge-outcomes > button").click() # first button?

		# Enter pledge amount.
		self.browser.execute_script("$('#pledge-amount input').val('12')")
		self.browser.find_element_by_css_selector("#contribution-start-next").click()

		# Enter email address.
		if not use_email:
			email = "unittest+%d@if.then.fund" % (random.randint(10000, 99999))
		else:
			email = use_email
		self.browser.execute_script("$('#emailEmail').val('%s').blur()" % email)
		time.sleep(.5)

		# Did we record it?
		from itfsite.models import User
		from contrib.models import IncompletePledge
		ip = IncompletePledge.objects.filter(email=email, trigger=trigger)
		if User.objects.filter(email=email).exists():
			self.assertEqual(ip.count(), 0) # we never create an IncompletePledge if email already exists as user
		else:
			self.assertEqual(ip.count(), 1) # email/trigger is a unique pair
		if not return_from_incomplete_pledge and len(ip) > 0:
			# Don't check the IncompletePledge details when returning from an
			# IncompletePledge  because the object will hold the information
			# from the original request  that generated the IncompletePledge.
			# The ref_code may be different.
			self.assertEqual(ip[0].extra['ref_code'], utm_campaign)
		if break_after_email:
			return ip[0]

		# Enter contributor information.
		self.browser.find_element_by_css_selector("#contribNameFirst").send_keys("John")
		self.browser.find_element_by_css_selector("#contribNameLast").send_keys("Doe")
		self.browser.find_element_by_css_selector("#contribAddress").send_keys("1010 Main St.")
		self.browser.find_element_by_css_selector("#contribCity").send_keys("Nowhere")
		self.browser.find_element_by_css_selector("#contribState").send_keys("XX") # using a fake state requires not using the DE API
		self.browser.find_element_by_css_selector("#contribZip").send_keys("90000")
		self.browser.find_element_by_css_selector("#contribOccupation").send_keys("quality assurance engineer")
		self.browser.find_element_by_css_selector("#contribEmployer").send_keys("unemployed")
		self.browser.find_element_by_css_selector("#contribution-contributorinfo-next").click()

		# Enter billing information.
		# send_keys has some problem with the stripe JS library overriding <input> behavior,
		# so use Javascript to set values instead.
		self.browser.execute_script("$('#billingCCNum').val('4111 1111 1111 1111')")
		self.browser.execute_script("$('#billingCCExp').val('9/2025')")
		self.browser.execute_script("$('#billingCCCVC').val('123')")
		self.browser.find_element_by_css_selector("#billing-next").click()
		time.sleep(.5)

		# The IncompletePledge should now be gone.
		self.assertFalse(IncompletePledge.objects.filter(email=email, trigger=trigger).exists())

		# Get the pledge and check its fields.
		p = trigger.pledges.get(anon_user__email=email)
		self.assertEqual(p.ref_code, utm_campaign)
		self.assertEqual(p.via_campaign, campaign)

		# An email confirmation was sent.
		self.assertFalse(p.anon_user.should_retry_email_confirmation())

		# Some tests don't click the confirmation link.
		if break_before_confirmation:
			return

		pw = self.follow_email_confirmation_link("has been confirmed")

		# We're back at the Trigger page, and after the user data is loaded
		# the user sees an explanation of the pledge.
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			pledge_summary.replace("VERB", verb))

		return email, pw

	def _test_trigger_execution(self, t, pledge_count, total_pledged, vote_url):
		# Check the trigger's current state.
		from contrib.models import Trigger, TriggerStatus
		t.refresh_from_db()
		self.assertEqual(t.pledge_count, pledge_count)
		self.assertEqual(t.total_pledged, total_pledged)

		# Execute the trigger.
		from contrib.legislative import execute_trigger_from_vote
		execute_trigger_from_vote(t, vote_url)
		t.refresh_from_db()
		self.assertEqual(t.status, TriggerStatus.Executed)

		# Send pledge pre-execution emails.
		from contrib.management.commands.send_pledge_emails import Command as send_pledge_emails
		send_pledge_emails().handle()

		# Execute pledges.
		from contrib.models import Pledge
		Pledge.ENFORCE_EXECUTION_EMAIL_DELAY = False
		from contrib.management.commands.execute_pledges import Command as execute_pledges
		execute_pledges().do_execute_pledges()

		# Send pledge post-execution emails.
		send_pledge_emails().handle()

	def _test_pledge_simple_execution(self, campaign,
		pledge_summary="You made a campaign contribution of $9.44 for this vote. It was split among 424 representatives, each getting a part of your contribution if they voted in favor of S. 1, but if they voted against S. 1 their part of your contribution will go to their next general election opponent."):
		# Reload the page.
		self.browser.get(self.build_test_url(campaign.get_absolute_url()))
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			pledge_summary)

	def _test_pledge_with_defaults(self, campaign, title, bill, logged_in=None, change_profile=False):
		# Now that we're logged in, try to do another trigger with things pre-filled.

		# Open the Trigger page.
		self.browser.get(self.build_test_url(campaign.get_absolute_url()))
		self.assertRegex(self.browser.title, title)

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")

		# Use default pledge amount.
		self.browser.find_element_by_css_selector("#contribution-start-next").click()

		if not change_profile:
			# Use default contributor, billing info
			self.browser.find_element_by_css_selector("#contribution-contributorinfo-next").click()
		else:
			# Click 'Update'.
			self.browser.find_element_by_css_selector("#pledge-contributor-old-update").click()

			# Enter contributor information.
			self.browser.find_element_by_css_selector("#contribNameFirst").send_keys("James")
			self.browser.find_element_by_css_selector("#contribNameLast").send_keys("Jones")
			self.browser.find_element_by_css_selector("#contribAddress").send_keys("2020 West St.")
			self.browser.find_element_by_css_selector("#contribCity").send_keys("Somewhere")
			self.browser.find_element_by_css_selector("#contribState").send_keys("XX") # using a fake state requires not using the DE API
			self.browser.find_element_by_css_selector("#contribZip").send_keys("90000")
			self.browser.find_element_by_css_selector("#contribOccupation").send_keys("quality assurance engineer")
			self.browser.find_element_by_css_selector("#contribEmployer").send_keys("unemployed")
			self.browser.find_element_by_css_selector("#contribution-contributorinfo-next").click()

			# Enter billing information.
			# send_keys has some problem with the stripe JS library overriding <input> behavior,
			# so use Javascript to set values instead.
			self.browser.execute_script("$('#billingCCNum').val('4111 1111 1111 1111')")
			self.browser.execute_script("$('#billingCCExp').val('9/2025')")
			self.browser.execute_script("$('#billingCCCVC').val('123')")

		self.browser.find_element_by_css_selector("#billing-next").click()

		# We're back at the Trigger page, and after the user data is loaded
		# the user sees an explanation of the pledge.
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You have scheduled a campaign contribution of $12.00 for this vote. It will be split among up to 100 senators, each getting a part of your contribution if they vote against BILL, but if they vote in favor of BILL their part of your contribution will go to their next general election opponent.".replace("BILL", bill))

		if not logged_in:
			# If the user wasn't logged in, and since we didn't log them in here,
			# the pledge was unconfirmed and we can't test trigger execution.
			return

		# Check the trigger and then execute the trigger & pledges.
		self._test_trigger_execution(campaign.contrib_triggers.first(),
			1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/s14")

		# Reload the page.
		self.browser.get(self.build_test_url(campaign.get_absolute_url()))
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You made a campaign contribution of $10.99 for this vote. It was split among 99 senators, each getting a part of your contribution if they voted against BILL, but if they voted in favor of BILL their part of your contribution will go to their next general election opponent.".replace("BILL", bill))

	def _test_pledge_returning_user(self, campaign, email, pw):
		# User is logged out but has an account.

		self.browser.get(self.build_test_url(campaign.get_absolute_url()))

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		self.browser.find_element_by_css_selector("#contribution-start-next").click() # Use default pledge amount

		# Try to log in.
		self.browser.execute_script("$('#emailEmail').val('%s')" % email)
		self.browser.find_element_by_css_selector("#emailEmailYesPassword").click()
		self.browser.find_element_by_css_selector("#emailPassword").send_keys(pw)
		self.browser.find_element_by_css_selector("#login-next").click()
		
		# Use pre-filled contributor/billing info.
		self.browser.find_element_by_css_selector("#contribution-contributorinfo-next").click()
		self.browser.find_element_by_css_selector("#billing-next").click()

		# We're back at the Trigger page, and after the user data is loaded
		# the user sees an explanation of the pledge.
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You have scheduled a campaign contribution of $5.00 for this vote. It will be split among up to 100 senators, each getting a part of your contribution if they vote against H.R. 30, but if they vote in favor of H.R. 30 their part of your contribution will go to their next general election opponent.")

	def _test_pledge_returning_user_logs_in_already_has_pledge(self, campaign, email, pw):
		# Re-start pledge.
		self.browser.get(self.build_test_url(campaign.get_absolute_url()))
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		self.browser.find_element_by_css_selector("#contribution-start-next").click() # Use default pledge amount.

		# Try to log in.
		self.browser.execute_script("$('#emailEmail').val('%s')" % email)
		self.browser.find_element_by_css_selector("#emailEmailYesPassword").click()
		self.browser.find_element_by_css_selector("#emailPassword").send_keys(pw)
		self.browser.find_element_by_css_selector("#login-next").click()
		self.assertEqual(
			self.browser.find_element_by_css_selector("#login-error").text,
			"You have already scheduled a contribution for this vote. Please log in to see details.")

	def test_maintest(self):
		from contrib.models import ContributorInfo, TriggerRecommendation
		from itfsite.models import Notification, NotificationType

		# Create the triggers and a TriggerRecommendation.
		t1, c1 = self.create_test_campaign("s1-114", "h")
		t2, c2 = self.create_test_campaign("s1-114", "s")
		TriggerRecommendation.objects.create(trigger1=t1, trigger2=t2)\
			.create_initial_notifications()

		# Test the creation of a Pledge. (Does not execute the pledge.)
		email, pw = self._test_pledge_simple(c1)
		self.assertEqual(ContributorInfo.objects.count(), 1)

		# The user should now have a Notification.
		self.assertEqual(Notification.objects.filter(notif_type=NotificationType.TriggerRecommendation).count(), 1)

		# Now that the user is logged in, try another pledge with fields pre-filled.
		# Also tests the execution of that Pledge.
		self._test_pledge_with_defaults(c2, "Keystone XL", "S. 1", logged_in=True)
		self.assertEqual(ContributorInfo.objects.count(), 1) # should not create 2nd profile
		self.assertEqual(Notification.objects.filter(notif_type=NotificationType.TriggerRecommendation).count(), 0) # since the Notification was not seen, it should now be deleted now that the user took action

		# Finally make a pledge but change the user's profile. Since we've executed
		# a pledge already, we should get two ContributorInfos out of this.
		# The first Pledge's ContributorInfo should be updated.
		t3, c3 = self.create_test_campaign("s50-114", "s")
		self._test_pledge_with_defaults(c3, "Abortion Non-Discrimination Act", "S. 50", logged_in=True, change_profile=True)
		self.assertEqual(ContributorInfo.objects.count(), 2)

		# Test the exeuction of the first trigger/pledge. We do this last so
		# we can check that its ContributorInfo object was updated by the later
		# pledge that entered new contributor information (that check was above).
		self._test_trigger_execution(t1, 1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/h14")
		self._test_pledge_simple_execution(c1)

	def test_returninguser(self):
		# Create a pledge so the user has an account.
		t1, c1 = self.create_test_campaign("s1-114", "h")
		email, pw = self._test_pledge_simple(c1)

		# Log out and try to make a new pledge by logging in,
		self.browser.get(self.build_test_url("/accounts/logout"))
		t2, c2 = self.create_test_campaign("hr30-114", "s")
		self._test_pledge_returning_user(c2, email, pw)

		# Log out and make a second pledge on the same trigger by doing it again.
		# It will say the user already made a pledge.
		self.browser.get(self.build_test_url("/accounts/logout"))
		self._test_pledge_returning_user_logs_in_already_has_pledge(c2, email, pw)

		# Do the same, but anonymously so that the clash is only detected after
		# the user confirms their address. Since the user already has an account,
		# we have to end follow_email_confirmation_link early.
		self.browser.get(self.build_test_url("/accounts/logout"))
		self._test_pledge_simple(c1, use_email=email, break_before_confirmation=True)
		self.follow_email_confirmation_link("You had a previous contribution already scheduled", already_has_account=True)

		# We have to delete the latest Pledge, otherwise we keep trying to get
		# the user to confirm it, even though the user has already clicked the
		# confirmation link.
		from contrib.models import Pledge
		self.assertFalse(Pledge.objects.filter(trigger=t1, user=None).exists())

	def test_returning_without_confirmation_and_utm_campaign(self):
		from contrib.models import ContributorInfo

		# Create the trigger.
		t1, c1 = self.create_test_campaign("s1-114", "h")

		# Test the creation of a Pledge but don't do email verification.
		# And tests a utm_campaign query string argument.
		self._test_pledge_simple(c1, break_before_confirmation=True, with_utm_campaign=True)
		self.assertEqual(ContributorInfo.objects.count(), 1)

		# Try another pledge with fields pre-filled from the last pledge that is
		# still stored in the user's session object.
		t2, c2 = self.create_test_campaign("s1-114", "s")
		self._test_pledge_with_defaults(c2, "Keystone XL", "S. 1", logged_in=False)
		self.assertEqual(ContributorInfo.objects.count(), 1) # should not create 2nd profile

	def test_incomplete_pledge(self, with_utm_campaign=False):
		# Create trigger.
		t, campaign = self.create_test_campaign("s1-114", "h")

		# Start a pledge but stop after entering email.
		ip = self._test_pledge_simple(campaign, with_utm_campaign=with_utm_campaign, break_after_email=True)

		# Fake the passage of time so the reminder email gets sent.
		ip.created -= timedelta(days=2)
		ip.save()

		# Send the incomplete pledge reminder email.
		from contrib.management.commands.send_pledge_emails import Command as send_pledge_emails
		send_pledge_emails().handle()

		# Check that the email has the correct URL.
		msg = pop_email().body
		self.assertIn(settings.SITE_ROOT_URL + ip.get_return_url(), msg)

		# Start a pledge again
		self._test_pledge_simple(campaign, return_from_incomplete_pledge=ip)

	def test_incomplete_pledge_with_utm_campaign(self):
		self.test_incomplete_pledge(with_utm_campaign=True)

	def test_post_execution_pledge(self):
		# Create the trigger, add a plege we don't care about, and execute it.
		# We include a pledge here because a trigger with no pledges used to
		# display differently.
		t, campaign = self.create_test_campaign("s1-114", "h")
		self._test_pledge_simple(campaign)
		self._test_trigger_execution(t, 1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/h14")

		# Test the creation of a Pledge.
		self.browser.get(self.build_test_url("/accounts/logout"))
		email, pw = self._test_pledge_simple(campaign, verb="voted")

		# Execute it.
		from contrib.management.commands.execute_pledges import Command as execute_pledges
		execute_pledges().do_execute_pledges()

		# Test that it appears executed on the site.
		self._test_pledge_simple_execution(campaign)

	def test_triggercustomization_pledge(self):
		# Create a customized trigger.
		t, campaign = self.create_test_campaign("s1-114", "h", with_customization=True)
		self._test_pledge_simple(campaign, pledge_summary="You have scheduled a campaign contribution of $12.00 for this vote. It will be split among the opponents in the next general election of representatives who vote against S. 1.")

		# Execute it.
		self._test_trigger_execution(t, 1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/h14")
		from contrib.management.commands.execute_pledges import Command as execute_pledges
		execute_pledges().do_execute_pledges()

		# Test that it appears executed on the site.
		self._test_pledge_simple_execution(campaign, pledge_summary="You made a campaign contribution of $11.45 for this vote. It was split among the opponents in the next general election of representatives who voted against S. 1.")

class LettersTest(SeleniumTest):
	fixtures = ['fixtures/actor.yaml', 'fixtures/recipient.yaml']

	@classmethod
	def setUpClass(cls):
		super(LettersTest, cls).setUpClass()

	#########################################

	def create_test_campaign(self):
		# Create an organization.
		from itfsite.models import Organization, OrganizationType
		org = Organization.objects.create(
			name="Test Organization",
			slug="test-organization",
			orgtype=OrganizationType.C4,
			description="This is a test organization.",
			description_format=0,
			)

		# Create a campaign.
		from itfsite.models import Campaign, CampaignStatus, TextFormat
		campaign = Campaign.objects.create(
			brand=1,
			owner=org,
			title="Test Campaign",
			slug="test-campaign",
			subhead="This is a test campaign.",
			subhead_format=TextFormat.Markdown,
			headline="Do More Tests",
			body_text="This is a test campaign.",
			body_format=TextFormat.Markdown,
			status=CampaignStatus.Open,
			)

		# Create a LettersCampaign.
		from letters.models import LettersCampaign, CampaignStatus as LettersCampaignStatus
		lc = LettersCampaign.objects.create(
			title="Do More Unit Tests",
			status=LettersCampaignStatus.Open,
			owner=org,
			message_subject="Do more unit tests",
			message_body="Unit tests are really important.\n\nDo more of them.",
			target_representatives=True,
			target_senators=False,
			)
		campaign.letters.add(lc)

		return campaign


	def _test_letter(self, campaign, is_logged_in=False, with_new_surname=False, with_existing_email=None, with_utm_campaign=False):
		# What URL?
		url = campaign.get_absolute_url()
		utm_campaign = None
		if with_utm_campaign:
			utm_campaign = "test_campaign_string"
			url += "?utm_campaign=" + utm_campaign

		# Load in browser. Check title.
		self.browser.get(self.build_test_url(url))
		self.assertRegex(self.browser.title, "Test Campaign")

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=0]').click()")

		if not is_logged_in:
			# Fill out address field.
			self.browser.find_element_by_css_selector("#lettersAddrAddress").send_keys("123 Main Street")
			self.browser.find_element_by_css_selector("#lettersAddrCity").send_keys("Everywhere")
			self.browser.find_element_by_css_selector("#lettersAddrState").send_keys("NY") # has to be a real state
			self.browser.find_element_by_css_selector("#lettersAddrZip").send_keys("12345")
			Select(self.browser.find_element_by_css_selector("#lettersVoterRegistration")).select_by_index(1)

		self.browser.find_element_by_css_selector("#write-letter-find-reps").click()

		email = with_existing_email
		if not is_logged_in:
			if not email:
				email = "unittest+%d@if.then.fund" % (random.randint(10000, 99999))
			self.browser.find_element_by_css_selector("#lettersEmail").send_keys(email)
			Select(self.browser.find_element_by_css_selector("#lettersNamePrefix")).select_by_index(1)
			self.browser.find_element_by_css_selector("#lettersNameFirst").send_keys("John")
			self.browser.find_element_by_css_selector("#lettersNameLast").send_keys("Doe" if not with_new_surname else "Franklin")

		Select(self.browser.find_element_by_css_selector("#letters-additional-field-0")).select_by_index(1)
		Select(self.browser.find_element_by_css_selector("#letters-additional-field-1")).select_by_index(1)
		self.browser.find_element_by_css_selector("#write-letter-submit").click()

		flow_one = True
		if with_new_surname:
			# Must enter code and submit again.
			from letters.views import votervoice
			self.browser.find_element_by_css_selector("#lettersVvEmailConfirmCode").send_keys(votervoice.LAST_EMAIL_VERIF_CODE)
			self.browser.find_element_by_css_selector("#write-letter-submit").click()

			if not with_existing_email:
				# When it's a new account, we're immediately redirected to the new account page.
				# It starts with a message that the letter is confirmed. If it's not a new
				# account, the VoterVoice email verification lets us immediately proceed.
				self.browser.find_element_by_css_selector("#global_modal .btn-default").click()
				pw = '12345'
				self.browser.find_element_by_css_selector("#inputPassword").send_keys(pw)
				self.browser.find_element_by_css_selector("#inputPassword2").send_keys(pw)
				self.browser.find_element_by_css_selector("#welcome-form").submit()
				flow_one = False

		pw = None
		if flow_one:
			# Submitted?
			time.sleep(.5)
			self.assertIn("Thanks! Your letter to", self.browser.find_element_by_css_selector("#write-a-letter").text)
			
			if not is_logged_in and not (with_existing_email and with_new_surname):
				# Letter is written. Follow email confirmation. There is no email
				# confirmation if we did a VoterVoice email confirmation.
				pw = self.follow_email_confirmation_link("will be sent")

			# Head back to/reload campaign page and test that the user's letter appears.
			self.browser.get(self.build_test_url(url))

			if with_new_surname and with_existing_email:
				# There was no email confirmation, but it was an anonymous user that
				# got confirmed, so there's a modal.
				self.browser.find_element_by_css_selector("#global_modal .btn-default").click()

		time.sleep(1) # wait for ajax to load user's actions
		self.assertIn("You wrote a letter to", self.browser.find_element_by_css_selector("#my-actions .letter-action-summary").text)

		return (email, pw)

	def test_letter(self):
		# Write a letter on a campaign.
		campaign = self.create_test_campaign()
		(email, pw) = self._test_letter(campaign)

		# The user is logged in now. Write a second letter while logged in.
		campaign = self.create_test_campaign()
		self._test_letter(campaign, is_logged_in=True)

		# Log out and submit new user details that cause a VoterVoice user 'conflict'.
		self.browser.get(self.build_test_url("/accounts/logout"))
		campaign = self.create_test_campaign()
		self._test_letter(campaign, with_existing_email=email, with_new_surname=True)


def pop_email():
	import django.core.mail
	try:
		msg = django.core.mail.outbox.pop()
	except:
		raise ValueError("No email was sent.")
	return msg

