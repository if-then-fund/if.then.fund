from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings

import selenium.webdriver
import re
import time
import random
from datetime import timedelta
from decimal import Decimal

class SimulationTest(StaticLiveServerTestCase):
	fixtures = ['fixtures/actor.yaml', 'fixtures/recipient.yaml']

	@classmethod
	def setUpClass(cls):
		super(cls, SimulationTest).setUpClass()

		# Override the suggested pledge amount so we have a known value
		# to test against.
		import contrib.views
		contrib.views.SUGGESTED_PLEDGE_AMOUNT = 5

		# Override the test that bills we use are not dead.
		import contrib.legislative
		contrib.legislative.ALLOW_DEAD_BILL = True

		# Override the email backend so that we can capture it.
		from django.conf import settings
		settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

		# Replace the Democracy Engine API with our dummy class
		# so we don't make time consuming remote API calls.
		import contrib.bizlogic
		contrib.bizlogic.DemocracyEngineAPI = contrib.bizlogic.DummyDemocracyEngineAPI()

		# Start a headless browser.
		cls.browser = selenium.webdriver.Firefox()

	@classmethod
	def tearDownClass(cls):
		super(cls, SimulationTest).tearDownClass()

		# Terminate the debug server.
		cls.browser.quit()

	def setUp(self):
		# make it easier to access the browser instance by aliasing to self.browser
		self.browser = SimulationTest.browser

		# clear the browser's cookies before each test
		self.browser.delete_all_cookies()

	def build_test_url(self, path):
		from urllib.parse import urljoin
		return urljoin(self.live_server_url, path)

	def pop_email(self):
		import django.core.mail
		try:
			msg = django.core.mail.outbox.pop()
		except:
			raise ValueError("No email was sent.")
		return msg

	def create_test_trigger(self, bill_num, chamber):
		# Create a Trigger.
		from contrib.models import Trigger, TriggerStatus, Pledge
		from contrib.legislative import create_trigger_from_bill
		t = create_trigger_from_bill(bill_num, chamber)
		t.status = TriggerStatus.Open
		t.save()
		return t

	def create_test_triggercustomization(self, trigger):
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
			trigger=trigger,
			title="Customized-" + trigger.title,
			slug="customized-" + trigger.slug,
			visible=True,
			subhead="We think this bill should pass.",
			subhead_format=0,
			description="We think this bill should pass.",
			description_format=0,
			incumb_challgr=-1,
			)

		return tcust

	def _test_pledge_simple(self, t,
			verb="vote",
			pledge_summary="You have scheduled a campaign contribution of $12.00 for this vote. It will be split among up to 435 representatives, each getting a part of your contribution if they VERB in favor of S. 1, but if they VERB against S. 1 their part of your contribution will go to their next general election opponent.",
			with_utm_campaign=False,
			break_after_email=False, return_from_incomplete_pledge=None,
			break_before_confirmation=False,
			via=None,
			):

		# Open the Trigger page.

		# What URL?
		url = t.get_absolute_url()
		if via:
			url = via.get_absolute_url()
		utm_campaign = None
		if with_utm_campaign:
			utm_campaign = "test_campaign_string"
			url += "?utm_campaign=" + utm_campaign

		# When testing an IncompletePledge, grab the return URL that it gives
		# which includes a utm_campaign string.
		if return_from_incomplete_pledge:
			utm_campaign = return_from_incomplete_pledge.get_utm_campaign_string()
			url = return_from_incomplete_pledge.get_return_url()
			if via: raise ValueError()

		# Load in browser. Check title.
		self.browser.get(self.build_test_url(url))
		self.assertRegex(self.browser.title, "Keystone XL")

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=0]').click()")
		#self.browser.find_element_by_css_selector("#pledge-outcomes > button").click() # first button?

		# Wait for form to fade in.
		time.sleep(1)

		# Enter pledge amount.
		self.browser.execute_script("$('#pledge-amount input').val('12')")
		self.browser.find_element_by_css_selector("#start-next").click()
		time.sleep(1)

		# Enter email address.
		email = "unittest+%d@if.then.fund" % (random.randint(10000, 99999))
		self.browser.execute_script("$('#emailEmail').val('%s')" % email)
		self.browser.find_element_by_css_selector("#login-next").click()
		time.sleep(1)

		# Did we record it?
		from contrib.models import IncompletePledge
		ip = IncompletePledge.objects.filter(email=email, trigger=t)
		self.assertEqual(ip.count(), 1) # email/trigger is a unique pair
		if not return_from_incomplete_pledge:
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
		self.browser.find_element_by_css_selector("#contrib-next").click()
		time.sleep(1)

		# Enter billing information.
		# send_keys has some problem with the stripe JS library overriding <input> behavior,
		# so use Javascript to set values instead.
		self.browser.execute_script("$('#billingCCNum').val('4111 1111 1111 1111')")
		self.browser.execute_script("$('#billingCCExp').val('9/2025')")
		self.browser.execute_script("$('#billingCCCVC').val('123')")
		self.browser.find_element_by_css_selector("#billing-next").click()
		time.sleep(1)

		# The IncompletePledge should now be gone.
		self.assertFalse(IncompletePledge.objects.filter(email=email, trigger=t).exists())

		# Get the pledge and check its fields.
		p = t.pledges.get(email=email)
		self.assertEqual(p.ref_code, utm_campaign)
		self.assertEqual(p.via, via)

		# An email confirmation was sent.
		self.assertFalse(p.should_retry_email_confirmation())

		if break_before_confirmation:
			return

		# Get the email confirmation URL that we need to hit to confirm the user.
		msg = self.pop_email().body
		m = re.search(r"We need to confirm your email address first. .*(http:\S*/ev/key/\S*/)", msg, re.S)
		self.assertTrue(m)
		conf_url = m.group(1)
		self.assertTrue(conf_url.startswith(settings.SITE_ROOT_URL))
		conf_url = conf_url.replace(settings.SITE_ROOT_URL + "/", "/")
		self.browser.get(self.build_test_url(conf_url))
		time.sleep(1)

		# Now we're at the "give a password" page.
		# It starts with a message that the pledge is confirmed.
		self.browser.find_element_by_css_selector("#global_modal .btn-default").click()
		time.sleep(1) # fadeOut
		pw = '12345'
		self.browser.find_element_by_css_selector("#inputPassword").send_keys(pw)
		self.browser.find_element_by_css_selector("#inputPassword2").send_keys(pw)
		self.browser.find_element_by_css_selector("#welcome-form").submit()
		time.sleep(1)

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

	def _test_pledge_simple_execution(self, t,
		pledge_summary="You made a campaign contribution of $9.44 for this vote. It was split among 424 representatives, each getting a part of your contribution if they voted in favor of S. 1, but if they voted against S. 1 their part of your contribution will go to their next general election opponent."):
		# Reload the page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		time.sleep(1)
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			pledge_summary)

	def _test_pledge_with_defaults(self, t, title, bill, logged_in=None, change_profile=False):
		# Now that we're logged in, try to do another trigger with things pre-filled.

		from contrib.models import Trigger

		# Open the Trigger page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		self.assertRegex(self.browser.title, title)

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		time.sleep(1) # Wait for form to fade in.

		# Use default pledge amount.
		self.browser.find_element_by_css_selector("#start-next").click()
		time.sleep(.5)

		# If the user is logged in, the login form is hidden. Otherwise enter
		# an email address.
		if not logged_in:
			email = "unittest+%d@if.then.fund" % (random.randint(10000, 99999))
			self.browser.execute_script("$('#emailEmail').val('%s')" % email)
			self.browser.find_element_by_css_selector("#login-next").click()
			time.sleep(1)

		if not change_profile:
			# Use default contributor, billing info
			self.browser.find_element_by_css_selector("#contrib-next").click()
			time.sleep(.5)
			self.browser.find_element_by_css_selector("#billing-next").click()
			time.sleep(1)
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
			self.browser.find_element_by_css_selector("#contrib-next").click()
			time.sleep(1)

			# Enter billing information.
			# send_keys has some problem with the stripe JS library overriding <input> behavior,
			# so use Javascript to set values instead.
			self.browser.execute_script("$('#billingCCNum').val('4111 1111 1111 1111')")
			self.browser.execute_script("$('#billingCCExp').val('9/2025')")
			self.browser.execute_script("$('#billingCCCVC').val('123')")
			self.browser.find_element_by_css_selector("#billing-next").click()
			time.sleep(1)

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
		self._test_trigger_execution(t, 1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/s14")

		# Reload the page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		time.sleep(1)
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You made a campaign contribution of $10.99 for this vote. It was split among 99 senators, each getting a part of your contribution if they voted against BILL, but if they voted in favor of BILL their part of your contribution will go to their next general election opponent.".replace("BILL", bill))

	def _test_pledge_returning_user(self, t, email, pw):
		# User is logged out but has an account.

		self.browser.get(self.build_test_url(t.get_absolute_url()))

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		time.sleep(1) # Wait for form to fade in.
		self.browser.find_element_by_css_selector("#start-next").click() # Use default pledge amount
		time.sleep(.5) # fade in

		# Try to log in.
		self.browser.execute_script("$('#emailEmail').val('%s')" % email)
		self.browser.find_element_by_css_selector("#emailEmailYesPassword").click()
		self.browser.find_element_by_css_selector("#emailPassword").send_keys(pw)
		self.browser.find_element_by_css_selector("#login-next").click()
		time.sleep(1)

		# Use pre-filled contributor/billing info.
		self.browser.find_element_by_css_selector("#contrib-next").click()
		time.sleep(.5)
		self.browser.find_element_by_css_selector("#billing-next").click()
		time.sleep(1)

		# We're back at the Trigger page, and after the user data is loaded
		# the user sees an explanation of the pledge.
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You have scheduled a campaign contribution of $5.00 for this vote. It will be split among up to 100 senators, each getting a part of your contribution if they vote against H.R. 30, but if they vote in favor of H.R. 30 their part of your contribution will go to their next general election opponent.")

		# Log out and try again --- this time it should report that a pledge has already been made.

		# Re-start pledge.
		self.browser.get(self.build_test_url("/accounts/logout"))
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		time.sleep(1) # page loading...?
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		time.sleep(1) # fade in
		self.browser.find_element_by_css_selector("#start-next").click() # Use default pledge amount.
		time.sleep(.5) # fade in

		# Try to log in.
		self.browser.execute_script("$('#emailEmail').val('%s')" % email)
		self.browser.find_element_by_css_selector("#emailEmailYesPassword").click()
		self.browser.find_element_by_css_selector("#emailPassword").send_keys(pw)
		self.browser.find_element_by_css_selector("#login-next").click()
		time.sleep(1)
		self.assertEqual(
			self.browser.find_element_by_css_selector("#login-error").text,
			"You have already scheduled a contribution for this vote. Please log in to see details.")

	def test_maintest(self):
		from contrib.models import ContributorInfo, TriggerRecommendation
		from itfsite.models import Notification, NotificationType

		# Create the triggers and a TriggerRecommendation.
		t1 = self.create_test_trigger("s1-114", "h")
		t2 = self.create_test_trigger("s1-114", "s")
		TriggerRecommendation.objects.create(trigger1=t1, trigger2=t2)\
			.create_initial_notifications()

		# Test the creation of a Pledge. (Does not execute the pledge.)
		email, pw = self._test_pledge_simple(t1)
		self.assertEqual(ContributorInfo.objects.count(), 1)

		# The user should now have a Notification.
		self.assertEqual(Notification.objects.filter(notif_type=NotificationType.TriggerRecommendation).count(), 1)

		# Now that the user is logged in, try another pledge with fields pre-filled.
		# Also tests the execution of that Pledge.
		self._test_pledge_with_defaults(t2, "Keystone XL", "S. 1", logged_in=True)
		self.assertEqual(ContributorInfo.objects.count(), 1) # should not create 2nd profile
		self.assertEqual(Notification.objects.filter(notif_type=NotificationType.TriggerRecommendation).count(), 0) # since the Notification was not seen, it should now be deleted now that the user took action

		# Finally make a pledge but change the user's profile. Since we've executed
		# a pledge already, we should get two ContributorInfos out of this.
		# The first Pledge's ContributorInfo should be updated.
		t3 = self.create_test_trigger("s50-114", "s")
		self._test_pledge_with_defaults(t3, "Abortion Non-Discrimination Act", "S. 50", logged_in=True, change_profile=True)
		self.assertEqual(ContributorInfo.objects.count(), 2)

		# Test the exeuction of the first trigger/pledge. We do this last so
		# we can check that its ContributorInfo object is updated.
		self._test_trigger_execution(t1, 1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/h14")
		self._test_pledge_simple_execution(t1)

		# Log out and try again with pre-filling fields during the login step.
		# This also does it yet another time testing that the user can't make
		# a second pledge on the same trigger.
		self.browser.get(self.build_test_url("/accounts/logout"))
		t4 = self.create_test_trigger("hr30-114", "s")
		self._test_pledge_returning_user(t4, email, pw)

	def test_returning_without_confirmation(self):
		from contrib.models import ContributorInfo

		# Create the trigger.
		t1 = self.create_test_trigger("s1-114", "h")

		# Test the creation of a Pledge but don't do email verification.
		self._test_pledge_simple(t1, break_before_confirmation=True)
		self.assertEqual(ContributorInfo.objects.count(), 1)

		# Try another pledge with fields pre-filled from the last pledge that is
		# still stored in the user's session object.
		t2 = self.create_test_trigger("s1-114", "s")
		self._test_pledge_with_defaults(t2, "Keystone XL", "S. 1", logged_in=False)
		self.assertEqual(ContributorInfo.objects.count(), 1) # should not create 2nd profile

	def test_pledge_with_utm_campaign(self):
		# Test the creation of a Pledge with a utm_campaign string.
		t = self.create_test_trigger("s1-114", "h")
		email, pw = self._test_pledge_simple(t, with_utm_campaign=True)

	def test_incomplete_pledge(self, with_utm_campaign=False):
		# Create trigger.
		t = self.create_test_trigger("s1-114", "h")

		# Start a pledge but stop after entering email.
		ip = self._test_pledge_simple(t, with_utm_campaign=with_utm_campaign, break_after_email=True)

		# Fake the passage of time so the reminder email gets sent.
		ip.created -= timedelta(days=2)
		ip.save()

		# Send the incomplete pledge reminder email.
		from contrib.management.commands.send_pledge_emails import Command as send_pledge_emails
		send_pledge_emails().handle()

		# Check that the email has the correct URL.
		msg = self.pop_email().body
		self.assertIn(settings.SITE_ROOT_URL + ip.get_return_url(), msg)

		# Start a pledge again
		self._test_pledge_simple(t, return_from_incomplete_pledge=ip)

	def test_incomplete_pledge_with_utm_campaign(self):
		self.test_incomplete_pledge(with_utm_campaign=True)

	def test_post_execution_pledge(self):
		# Create the trigger, add a plege we don't care about, and execute it.
		# We include a pledge here because a trigger with no pledges displays
		# differently.
		t = self.create_test_trigger("s1-114", "h")
		self._test_pledge_simple(t)
		self._test_trigger_execution(t, 1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/h14")

		# Test the creation of a Pledge.
		self.browser.get(self.build_test_url("/accounts/logout"))
		email, pw = self._test_pledge_simple(t, verb="voted")

		# Execute it.
		from contrib.management.commands.execute_pledges import Command as execute_pledges
		execute_pledges().do_execute_pledges()

		# Test that it appears executed on the site.
		self._test_pledge_simple_execution(t)

	def test_triggercustomization_pledge(self):
		# Create a customized trigger.
		t = self.create_test_trigger("s1-114", "h")
		tcust = self.create_test_triggercustomization(t)
		self._test_pledge_simple(t, via=tcust, pledge_summary="You have scheduled a campaign contribution of $12.00 for this vote. It will be split among the opponents in the next general election of representatives who vote against S. 1.")

		# Execute it.
		self._test_trigger_execution(t, 1, Decimal('12'), "https://www.govtrack.us/congress/votes/114-2015/h14")
		from contrib.management.commands.execute_pledges import Command as execute_pledges
		execute_pledges().do_execute_pledges()

		# Test that it appears executed on the site.
		self._test_pledge_simple_execution(tcust, pledge_summary="You made a campaign contribution of $11.45 for this vote. It was split among the opponents in the next general election of representatives who voted against S. 1.")
