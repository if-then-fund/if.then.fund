from decimal import Decimal

from django.test import TestCase

from itfsite.models import User
from contrib.models import *

class PledgeTestCase(TestCase):
	def setUp(self):
		self.trigger_type = TriggerType.objects.create(
			key="test",
			strings={
				"actor": "ACTOR",
				"actors": "ACTORS",
				"action_noun": "ACTION",
				"action_vb_inf": "ACT",
				"action_vb_pres_s": "ACTS",
				"action_vb_past": "ACTED",
			})

		from django.template.defaultfilters import slugify
		self.trigger = Trigger.objects.create(
			key="test",
			title="Test Trigger",
			owner=None,
			trigger_type=self.trigger_type,
			slug=slugify("Test Trigger"),
			description="This is a test trigger.",
			description_format=TextFormat.Markdown,
			outcomes=[
				{ "label": "Yes", "tip": "YesTip" },
				{ "label": "No", "tip": "NoTip" },
			],
			extra={
				"max_split": 100,
			}
			)

		# Create a user.
		self.user = User.objects.create(email="test@example.com")

	def _test_pledge(self, desired_outcome, incumb_challgr, filter_party, expected_value):
		ci = ContributorInfo.objects.create()
		p = Pledge.objects.create(
			user=self.user,
			trigger=self.trigger,
			profile=ci,
			algorithm=Pledge.current_algorithm()['id'],
			desired_outcome=desired_outcome,
			amount=1,
			incumb_challgr=incumb_challgr,
			filter_party=filter_party,
		)
		self.assertEqual(p.made_after_trigger_execution, False)
		self.assertEqual(p.targets_summary, expected_value)

	def test_pledge_simple(self):
		self._test_pledge(0, 0, None, "up to 100 ACTORS, each getting a part of your contribution if they ACT Yes, but if they ACT No their part of your contribution will go to their next general election opponent")

	def test_pledge_keepemin(self):
		self._test_pledge(0, 1, None, "ACTORS who ACT Yes")

	def test_pledge_throwemout(self):
		self._test_pledge(0, -1, None, "the opponents in the next general election of ACTORS who ACT No")

	def test_pledge_partyfilter(self):
		self._test_pledge(0, 0, ActorParty.Democratic, "Democratic ACTORS who ACT Yes and the Democratic opponents in the next general election of ACTORS who ACT No")

	def test_pledge_keepemin_partyfilter(self):
		self._test_pledge(0, 1, ActorParty.Democratic, "Democratic ACTORS who ACT Yes")

	def test_pledge_throwemout_partyfilter(self):
		self._test_pledge(0, -1, ActorParty.Democratic, "the Democratic opponents in the next general election of ACTORS who ACT No")


class ExecutionTestCase(TestCase):
	ACTORS_PER_PARTY = 20

	def setUp(self):
		# Replace the Democracy Engine API with our dummy class
		# so we don't make time consuming remote API calls.
		import contrib.bizlogic
		contrib.bizlogic.DemocracyEngineAPI = contrib.bizlogic.DummyDemocracyEngineAPI()

		from django.template.defaultfilters import slugify

		# TriggerType
	
		tt = TriggerType.objects.create(
			key="test",
			strings={
				"actor": "ACTOR",
				"actors": "ACTORS",
				"action_noun": "ACTION",
				"action_vb_inf": "ACT",
				"action_vb_pres_s": "ACTS",
				"action_vb_past": "ACTED",
			})

		# Trigger

		t = Trigger.objects.create(
			key="test",
			title="Test Trigger",
			owner=None,
			trigger_type=tt,
			slug=slugify("Test Trigger"),
			description="This is a test trigger.",
			description_format=TextFormat.Markdown,
			outcomes=[
				{ "label": "Yes", },
				{ "label": "No", },
			],
			extra={
				"max_split": 100,
			}
			)
		t.status = TriggerStatus.Open
		t.save()

		# Actors

		actor_counter = 0
		for party in (ActorParty.Republican, ActorParty.Democratic):
			for i in range(self.ACTORS_PER_PARTY):
				actor_counter += 1

				challenger = Recipient.objects.create(
					de_id="c%d" % actor_counter,
					actor=None,
					office_sought="OFFICE-%d" % actor_counter,
					party=party.opposite())

				actor = Actor.objects.create(
					govtrack_id=actor_counter,
					name_long="Actor %d" % actor_counter,
					name_short="Actor %d" % actor_counter,
					name_sort="Actor %d" % actor_counter,
					party=party,
					title="Test Actor",
					challenger=challenger,
					)

				Recipient.objects.create(
					de_id="p%d" % actor_counter,
					actor=actor,
					)

		# Create one more inactive Actor.
		actor_counter += 1
		actor = Actor.objects.create(
			govtrack_id=actor_counter,
			name_long="Actor %d" % actor_counter,
			name_short="Actor %d" % actor_counter,
			name_sort="Actor %d" % actor_counter,
			party=ActorParty.Republican,
			title="Test Inactive Actor",
			inactive_reason="Inactive for some reason."
			)

	def test_trigger(self):
		"""Tests the trigger"""
		t = Trigger.objects.get(key="test")
		self.assertEqual(t.pledge_count, 0)
		self.assertEqual(t.total_pledged, 0)

	def test_trigger_execution(self):
		"""Tests the execution of the trigger"""

		# Build actor outcomes.
		actor_outcomes = { }
		for i, actor in enumerate(Actor.objects.all()):
			actor_outcomes[actor] = i % 3
			if actor_outcomes[actor] == 2:
				actor_outcomes[actor] = "Reason for not having an outcome."

		# Execute.
		from django.utils.timezone import now
		trigger = Trigger.objects.get(key="test")
		trigger.execute(
			now(),
			actor_outcomes,
			"The trigger has been executed.",
			TextFormat.Markdown,
			{
			})

		# Refresh object because .status is updated on a copy.
		trigger = Trigger.objects.get(key="test")

		# The trigger is now executed.
		self.assertEqual(trigger.status, TriggerStatus.Executed)

		# The execution should be empty.
		self.assertEqual(trigger.execution.pledge_count, 0)
		self.assertEqual(trigger.execution.pledge_count_with_contribs, 0)
		self.assertEqual(trigger.execution.num_contributions, 0)
		self.assertEqual(trigger.execution.total_contributions, 0)

		# There should be the same number of Actions as Actors.
		self.assertEqual(Action.objects.count(), Actor.objects.count())
		for action in Action.objects.all():
			self.assertEqual(action.execution, trigger.execution)
			self.assertEqual(action.action_time, trigger.execution.action_time)
			if action.actor.inactive_reason is not None:
				self.assertEqual(action.outcome, None)
				self.assertEqual(action.reason_for_no_outcome, action.actor.inactive_reason)
			elif isinstance(actor_outcomes[action.actor], int):
				self.assertEqual(action.outcome, actor_outcomes[action.actor])
				self.assertEqual(action.reason_for_no_outcome, None)
			else:
				self.assertEqual(action.outcome, None)
				self.assertEqual(action.reason_for_no_outcome, actor_outcomes[action.actor])
			self.assertEqual(action.name_long, action.actor.name_long)
			self.assertEqual(action.name_short, action.actor.name_short)
			self.assertEqual(action.name_sort, action.actor.name_sort)
			self.assertEqual(action.party, action.actor.party)
			self.assertEqual(action.title, action.actor.title)
			self.assertEqual(action.extra, action.actor.extra)
			self.assertEqual(action.challenger, action.actor.challenger)
			self.assertEqual(action.total_contributions_for, 0)
			self.assertEqual(action.total_contributions_against, 0)

	def test_pledge_execution_a(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=0, filter_party=None,
			expected_contrib_amount=Decimal('0.33'))

	def test_pledge_execution_b(self):
		self._pledge_execution(desired_outcome=1, amount=10, incumb_challgr=0, filter_party=None,
			expected_contrib_amount=Decimal('0.33'))

	def test_pledge_execution_c(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=1, filter_party=None,
			expected_contrib_amount=Decimal('0.69'))

	def test_pledge_execution_c(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=-1, filter_party=None,
			expected_contrib_amount=Decimal('0.69'))

	def test_pledge_execution_d(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=0, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('0.64'))

	def test_pledge_execution_e(self):
		self._pledge_execution(desired_outcome=1, amount=10, incumb_challgr=0, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('0.69'))

	def test_pledge_execution_f(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=1, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('1.28'))

	def test_pledge_execution_g(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=-1, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('1.28'))

	# contrib is too small
	def test_pledge_execution_failure_a(self):
		self._pledge_execution(desired_outcome=0, amount=decimal.Decimal('.1'), incumb_challgr=0, filter_party=None, expected_contrib_amount=None,
			expected_problem=PledgeExecutionProblem.TransactionFailed, expected_problem_string="The amount is less than the minimum fees.")
	def test_pledge_execution_failure_b(self):
		self._pledge_execution(desired_outcome=0, amount=decimal.Decimal('.3'), incumb_challgr=0, filter_party=None, expected_contrib_amount=None,
			expected_problem=PledgeExecutionProblem.TransactionFailed, expected_problem_string="The amount is not enough to divide evenly across 27 recipients.")

	# contrib made after trigger execution
	def test_pledge_made_after_trigger_execution(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=0, filter_party=None,
			expected_contrib_amount=Decimal('0.33'), made_after_trigger_execution=True)

	def _pledge_execution(self, desired_outcome, amount, incumb_challgr, filter_party, expected_contrib_amount,
		expected_problem=None, expected_problem_string=None, made_after_trigger_execution=False):

		# Create a user.
		user = User.objects.create(email="test@example.com")

		# Create a ContributorInfo.
		cc_num = '4111 1111 1111 1111'
		cc_cvc = '1234'
		ci = ContributorInfo()
		ci.set_from({
			'contributor': {
				'contribNameFirst': 'FIRST',
				'contribNameLast': 'LAST',
				'contribAddress': 'ADDRESS',
				'contribCity': 'CITY',
				'contribState': 'NY',
				'contribZip': '00000',
				'contribOccupation': 'OCCUPATION',
				'contribEmployer': 'EMPLOYER',
			},
			'billing': {
				'cc_num': cc_num,
				'cc_exp_month': '01',
				'cc_exp_year': '2020',
			},
		})
		ci.save()

		# Create a pledge.
		p = Pledge.objects.create(
			user=user,
			trigger=Trigger.objects.get(key="test"),
			profile=ci,
			algorithm=Pledge.current_algorithm()['id'],
			made_after_trigger_execution=made_after_trigger_execution,
			desired_outcome=desired_outcome,
			amount=amount,
			incumb_challgr=incumb_challgr,
			filter_party=filter_party,
		)

		# Set billing info.
		from contrib.bizlogic import run_authorization_test
		run_authorization_test(p, cc_num, cc_cvc, { "unittest": True } )
		ci.save(override_immutable_check=True)

		# Check that the trigger now has a pledge.
		t = Trigger.objects.get(key="test")
		if not made_after_trigger_execution:
			self.assertEqual(t.pledge_count, 1)
			self.assertEqual(t.total_pledged, p.amount)
		else:
			# these fields are not incremented when a pledge is made after a trigger is executed
			self.assertEqual(t.pledge_count, 0)
			self.assertEqual(t.total_pledged, 0)

		# Execute the trigger.
		self.test_trigger_execution()

		from django.utils.timezone import now
		p.pre_execution_email_sent_at = now()
		p.save()

		# Execute the pledge.
		Pledge.ENFORCE_EXECUTION_EMAIL_DELAY = False
		p.execute()

		# Test general properties.
		self.assertEqual(p.execution.trigger_execution, t.execution)

		# Testing a case where transaction should fail.
		if expected_problem:
			self.assertEqual(p.execution.problem, expected_problem)
			self.assertEqual(p.execution.extra['exception'], expected_problem_string)
			self.assertEqual(p.execution.fees, 0)
			self.assertEqual(p.execution.charged, 0)
			self.assertEqual(p.execution.contributions.count(), 0)
			self.assertEqual(p.trigger.execution.pledge_count, 1)
			self.assertEqual(p.trigger.execution.pledge_count_with_contribs, 0)
			self.assertEqual(p.trigger.execution.num_contributions, 0)
			self.assertEqual(p.trigger.execution.total_contributions, 0)
			return

		# Test more general properties.
		self.assertEqual(p.execution.problem, PledgeExecutionProblem.NoProblem)

		# Test that every Action lead to a Contribution.
		expected_contrib_count = 0
		expected_charge = 0
		for action in t.execution.actions.all():
			contrib = p.execution.contributions.filter(action=action).first()
			if action.outcome is None:
				self.assertIsNone(contrib)
			else:
				if action.outcome == p.desired_outcome:
					if p.incumb_challgr == -1: continue
					recipient = Recipient.objects.get(actor=action.actor)
					if p.filter_party and action.party != filter_party: continue
				else:
					if p.incumb_challgr == +1: continue
					recipient = action.actor.challenger
					if p.filter_party and recipient.party != filter_party: continue
				self.assertIsNotNone(contrib)
				self.assertEqual(contrib.recipient, recipient)
				self.assertEqual(contrib.amount, expected_contrib_amount)
				expected_contrib_count += 1
				expected_charge += expected_contrib_amount

		# Test fees and no extra contributions.
		expected_fees = (expected_charge * Decimal('.09') + Decimal('.20')).quantize(Decimal('.01'))
		self.assertEqual(p.execution.fees, expected_fees)
		self.assertEqual(p.execution.charged, expected_charge + expected_fees)
		self.assertEqual(p.execution.contributions.count(), expected_contrib_count)
		self.assertTrue(p.execution.charged < p.amount)
		self.assertTrue(p.execution.charged > p.amount - expected_contrib_amount)

		# Test trigger.
		self.assertEqual(p.trigger.execution.pledge_count, 1)
		self.assertEqual(p.trigger.execution.pledge_count_with_contribs, 1)
		self.assertEqual(p.trigger.execution.num_contributions, expected_contrib_count)
		self.assertEqual(p.trigger.execution.total_contributions, p.execution.charged-p.execution.fees)

