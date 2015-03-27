from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings

import selenium.webdriver
import re
import time
from decimal import Decimal

class SimulationTest(StaticLiveServerTestCase):
	fixtures = ['fixtures/actor.yaml', 'fixtures/recipient.yaml']

	def setUp(self):
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
		self.browser = selenium.webdriver.Firefox()

	def tearDown(self):
		# Terminate the debug server.
		print("Shutting down debug server.")
		self.browser.quit()

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

	def create_test_trigger(self):
		# Create a Trigger.
		from contrib.models import Trigger, TriggerStatus, Pledge
		from contrib.legislative import create_trigger_from_bill
		t = create_trigger_from_bill("s1-114", "h")
		t.status = TriggerStatus.Open
		t.save()
		return t

	def _test_pledge_simple(self, t,
			with_campaign=False,
			break_after_email=False, return_from_incomplete_pledge=None
			):

		# Open the Trigger page.

		# What URL?
		url = t.get_absolute_url()
		campaign = None
		if with_campaign:
			campaign = "test_campaign_string"
			url += "?utm_campaign=" + campaign

		# When testing an IncompletePledge, grab the return URL that it gives
		# which includes a utm_campaign string.
		if return_from_incomplete_pledge:
			campaign = return_from_incomplete_pledge.get_campaign_string()
			url = return_from_incomplete_pledge.get_return_url()

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
		email = "unittest@if.then.fund"
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
			# The campaign may be different.
			self.assertEqual(ip[0].extra['campaign'], campaign)
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
		self.assertEqual(p.campaign, campaign)

		# An email confirmation was sent.
		self.assertFalse(p.should_retry_email_confirmation())

		# Get the email confirmation URL that we need to hit to confirm the user.
		msg = self.pop_email().body
		m = re.search(r"We need to confirm your email address first. .*(http:\S*/ev/key/\S*/)", msg, re.S)
		self.assertTrue(m)
		conf_url = m.group(1)
		#from email_confirm_la.models import EmailConfirmation
		#conf_url = EmailConfirmation.objects.get(email=email, is_verified=False).get_confirmation_url()
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
			"You have scheduled a campaign contribution of $12.00 for this vote. It will be split among up to 435 representatives, each getting a part of your contribution if they vote Yes on S. 1, but if they vote No on S. 1 their part of your contribution will go to their next general election opponent.")

		return email, pw

	def _test_pledge_simple_execution(self, t):
		# This function always follows _test_pledge_simple.

		# Check the trigger's current state.
		from contrib.models import Trigger
		t = Trigger.objects.get(id=t.id) # refresh
		self.assertEqual(t.pledge_count, 1)
		self.assertEqual(t.total_pledged, Decimal('12'))

		# Execute the trigger.
		from contrib.legislative import execute_trigger_from_vote
		execute_trigger_from_vote(t, "https://www.govtrack.us/congress/votes/114-2015/h14")

		# Send pledge pre-execution emails.
		from contrib.management.commands.send_pledge_emails import Command as send_pledge_emails
		send_pledge_emails().handle()

		# Execute pledges.
		from contrib.models import Pledge
		Pledge.ENFORCE_EXECUTION_EMAIL_DELAY = False
		from contrib.management.commands.execute_pledges import Command as execute_pledges
		execute_pledges().handle()

		# Send pledge post-execution emails.
		send_pledge_emails().handle()

		# Reload the page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		time.sleep(1)

		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You made a campaign contribution of $9.44 for this vote. It was split among 424 representatives, each getting a part of your contribution if they voted Yes on S. 1, but if they voted No on S. 1 their part of your contribution will go to their next general election opponent.")

	def _test_pledge_logged_in(self):
		# Now that we're logged in, try to do another trigger with things pre-filled.

		from contrib.models import Trigger, TriggerStatus
		from contrib.legislative import create_trigger_from_bill
		t = create_trigger_from_bill("s1-114", "s")
		t.status = TriggerStatus.Open
		t.save()

		# Open the Trigger page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		self.assertRegex(self.browser.title, "Keystone XL")

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		time.sleep(1) # Wait for form to fade in.

		# Use default pledge amount, contributor, billing info.
		self.browser.find_element_by_css_selector("#start-next").click()
		time.sleep(.5)
		self.browser.find_element_by_css_selector("#contrib-next").click()
		time.sleep(.5)
		self.browser.find_element_by_css_selector("#billing-next").click()
		time.sleep(1)

		# We're back at the Trigger page, and after the user data is loaded
		# the user sees an explanation of the pledge.
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You have scheduled a campaign contribution of $12.00 for this vote. It will be split among up to 100 senators, each getting a part of your contribution if they vote No on S. 1, but if they vote Yes on S. 1 their part of your contribution will go to their next general election opponent.")

		# Check the trigger.
		t = Trigger.objects.get(id=t.id) # refresh
		self.assertEqual(t.pledge_count, 1)
		self.assertEqual(t.total_pledged, Decimal('12'))

		# Execute the trigger.
		from contrib.legislative import execute_trigger_from_vote
		execute_trigger_from_vote(t, "https://www.govtrack.us/congress/votes/114-2015/h14")

		# Send pledge pre-execution emails.
		from contrib.management.commands.send_pledge_emails import Command as send_pledge_emails
		send_pledge_emails().handle()

		# Execute pledges.
		from contrib.management.commands.execute_pledges import Command as execute_pledges
		execute_pledges().handle()

		# Send pledge post-execution emails.
		send_pledge_emails().handle()

		# Reload the page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		time.sleep(1)
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You made a campaign contribution of $9.44 for this vote. It was split among 424 senators, each getting a part of your contribution if they voted No on S. 1, but if they voted Yes on S. 1 their part of your contribution will go to their next general election opponent.")

	def _test_pledge_returning_user(self, email, pw):
		# User is logged out but has an account.

		from contrib.models import TriggerStatus
		from contrib.legislative import create_trigger_from_bill
		t = create_trigger_from_bill("hr30-114", "s")
		t.status = TriggerStatus.Open
		t.save()

		self.browser.get(self.build_test_url(t.get_absolute_url()))

		# Click one of the outcome buttons.
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		time.sleep(1) # Wait for form to fade in.
		self.browser.find_element_by_css_selector("#start-next").click() # Use default pledge amount
		time.sleep(.5) # faide in

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
			"You have scheduled a campaign contribution of $5.00 for this vote. It will be split among up to 100 senators, each getting a part of your contribution if they vote No on H.R. 30, but if they vote Yes on H.R. 30 their part of your contribution will go to their next general election opponent.")

		# Log out and try again --- this time it should report that a pledge has already been made.

		# Re-start pledge.
		self.browser.get(self.build_test_url("/accounts/logout"))
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		self.browser.execute_script("$('#pledge-outcomes > button[data-index=1]').click()")
		time.sleep(1) # fade in
		self.browser.find_element_by_css_selector("#start-next").click() # Use default pledge amount.
		time.sleep(.5) # faide in

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
		# Create the trigger.
		t = self.create_test_trigger()

		# Test the creation of a Pledge.
		email, pw = self._test_pledge_simple(t)

		# Test its exeuction.
		self._test_pledge_simple_execution(t)

		# Now that the user is logged in, try another pledge with fields pre-filled.
		self._test_pledge_logged_in()

		# Log out and try again with pre-filling fields during the login step.
		self.browser.get(self.build_test_url("/accounts/logout"))
		self._test_pledge_returning_user(email, pw)

	def test_pledge_campaign(self):
		# Test the creation of a Pledge with a campaign string.
		t = self.create_test_trigger()
		email, pw = self._test_pledge_simple(t, with_campaign=True)

	def test_incomplete_pledge(self, with_campaign=False):
		# Create trigger.
		t = self.create_test_trigger()

		# Start a pledge but stop after entering email.
		ip = self._test_pledge_simple(t, with_campaign=with_campaign, break_after_email=True)

		# Send the incomplete pledge reminder email.
		from contrib.management.commands.send_pledge_emails import Command as send_pledge_emails
		send_pledge_emails().handle()

		# Check that the email has the correct URL.
		msg = self.pop_email().body
		self.assertIn(settings.SITE_ROOT_URL + ip.get_return_url(), msg)

		# Start a pledge again
		self._test_pledge_simple(t, return_from_incomplete_pledge=ip)

	def test_incomplete_pledge_with_campaign(self):
		self.test_incomplete_pledge(with_campaign=True)
