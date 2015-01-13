from decimal import Decimal

from django.test import TestCase

from itfsite.models import User
from contrib.models import *

class SimpleTestCase(TestCase):
	ACTORS_PER_PARTY = 5

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
			if isinstance(actor_outcomes[action.actor], int):
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
			expected_contrib_amount=Decimal('1.28'))

	def test_pledge_execution_b(self):
		self._pledge_execution(desired_outcome=1, amount=10, incumb_challgr=0, filter_party=None,
			expected_contrib_amount=Decimal('1.28'))

	def test_pledge_execution_c(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=1, filter_party=None,
			expected_contrib_amount=Decimal('2.24'))

	def test_pledge_execution_c(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=-1, filter_party=None,
			expected_contrib_amount=Decimal('2.99'))

	def test_pledge_execution_d(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=0, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('2.24'))

	def test_pledge_execution_e(self):
		self._pledge_execution(desired_outcome=1, amount=10, incumb_challgr=0, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('2.99'))

	def test_pledge_execution_f(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=1, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('4.49'))

	def test_pledge_execution_g(self):
		self._pledge_execution(desired_outcome=0, amount=10, incumb_challgr=-1, filter_party=ActorParty.Democratic,
			expected_contrib_amount=Decimal('4.49'))

	def _pledge_execution(self, desired_outcome, amount, incumb_challgr, filter_party, expected_contrib_amount):
		# Create a user.
		user = User.objects.create(email="test@example.com")

		# Create a pledge.
		p = Pledge.objects.create(
			user=user,
			trigger=Trigger.objects.get(key="test"),
			algorithm=Pledge.current_algorithm()['id'],
			desired_outcome=desired_outcome,
			amount=amount,
			incumb_challgr=incumb_challgr,
			filter_party=filter_party,
			cclastfour='1111',
			extra={
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
			}
		)

		# Set billing info.
		from contrib.bizlogic import run_authorization_test
		run_authorization_test(p, "4111 1111 1111 1111", 9, 2021, '999', { "unittest": True } )
		p.save()

		# Check that the trigger now has a pledge.
		t = Trigger.objects.get(key="test")
		self.assertEqual(t.pledge_count, 1)
		self.assertEqual(t.total_pledged, p.amount)

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
					recipient = action.challenger
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

