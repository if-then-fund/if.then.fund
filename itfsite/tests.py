from django.contrib.staticfiles.testing import StaticLiveServerTestCase
import selenium.webdriver
import time
from decimal import Decimal

class SimulationTest(StaticLiveServerTestCase):
	fixtures = ['fixtures/actor.yaml', 'fixtures/recipient.yaml']

	def setUp(self):
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

	def test_test(self):
		# Create a Trigger.
		from contrib.models import Trigger, TriggerStatus, Pledge
		from contrib.legislative import create_trigger_from_bill
		t = create_trigger_from_bill("s1-114", "h")
		t.status = TriggerStatus.Open
		t.save()

		# Open the Trigger page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
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

		# Confirm the user.
		from email_confirm_la.models import EmailConfirmation
		conf_url = EmailConfirmation.objects.get(email=email, is_verified=False).get_confirmation_url()
		self.assertTrue(conf_url.startswith("http://127.0.0.1/"))
		conf_url = conf_url.replace("http://127.0.0.1/", "/")
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
			"You have scheduled a campaign contribution of $12.00 for this vote. It will be split among all 435 representatives, each getting a part of your contribution if they vote Yes on S. 1, but if they vote No on S. 1 their part of your contribution will go to their next general election opponent.")

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

		#############################################################################

		# Now that we're logged in, try to do another trigger with things pre-filled.

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
			"You have scheduled a campaign contribution of $12.00 for this vote. It will be split among all 100 senators, each getting a part of your contribution if they vote No on S. 1, but if they vote Yes on S. 1 their part of your contribution will go to their next general election opponent.")

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
		execute_pledges().handle()

		# Send pledge post-execution emails.
		send_pledge_emails().handle()

		# Reload the page.
		self.browser.get(self.build_test_url(t.get_absolute_url()))
		time.sleep(1)
		self.assertEqual(
			self.browser.find_element_by_css_selector("#pledge-explanation").text,
			"You made a campaign contribution of $9.44 for this vote. It was split among 424 senators, each getting a part of your contribution if they voted No on S. 1, but if they voted Yes on S. 1 their part of your contribution will go to their next general election opponent.")

		#############################################################################

		# Log out and try again with pre-filling fields during the login step.

		self.browser.get(self.build_test_url("/accounts/logout"))

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
			"You have scheduled a campaign contribution of $5.00 for this vote. It will be split among all 100 senators, each getting a part of your contribution if they vote No on H.R. 30, but if they vote Yes on H.R. 30 their part of your contribution will go to their next general election opponent.")

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
