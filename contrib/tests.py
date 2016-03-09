from decimal import Decimal
from itertools import product

from django.test import TestCase

from itfsite.models import User, Campaign
from contrib.models import *
from contrib.de import DemocracyEngineAPIClient

class DEAPITestCase(TestCase):
	def test_format_decimal(self):
		from decimal import Decimal
		f = DemocracyEngineAPIClient.format_decimal
		self.assertEqual(f(Decimal('0')), '$0.00')
		self.assertEqual(f(Decimal('.1')), '$0.10')
		self.assertEqual(f(Decimal('.01')), '$0.01')
		self.assertEqual(f(Decimal('.001')), '$0.00') # rounds
		self.assertEqual(f(Decimal('.006')), '$0.01') # rounds
		self.assertEqual(f(Decimal('123')), '$123.00')
		self.assertEqual(f(Decimal('1234')), '$1234.00')

def create_trigger(trigger_type, key, title):
	trigger = Trigger.objects.create(
		key=key,
		title=title,
		owner=None,
		trigger_type=trigger_type,
		description="This is a test trigger.",
		description_format=TextFormat.Markdown,
		outcomes=[
			{ "label": "Yes", "tip": "YesTip" },
			{ "label": "No", "tip": "NoTip" },
		],
		extra={ }
		)
	campaign = Campaign.objects.create(
		brand=0,
		subhead="This is a test campaign.",
		subhead_format=TextFormat.Markdown,
		body_text="This is a test campaign.",
		body_format=TextFormat.Markdown,
		)
	campaign.contrib_triggers.add(trigger)
	return campaign, trigger

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
			},
			extra={
				"max_split": 100,
			})

		self.campaign, self.trigger = create_trigger(self.trigger_type, 'test', 'Test Trigger')

		# Create a user.
		self.user = User.objects.create(email="test@example.com")

	def _test_pledge(self, desired_outcome, incumb_challgr, filter_party, expected_value):
		ci = ContributorInfo.objects.create()
		p = Pledge.objects.create(
			user=self.user,
			trigger=self.trigger,
			via_campaign=self.campaign,
			profile=ci,
			algorithm=Pledge.current_algorithm()['id'],
			desired_outcome=desired_outcome,
			amount=1,
			incumb_challgr=incumb_challgr,
			filter_party=filter_party,
		)
		p.run_post_confirm_steps()
		self.assertEqual(p.made_after_trigger_execution, False)
		self.assertEqual(p.targets_summary, expected_value)

	def test_pledge_simple(self):
		self._test_pledge(0, 0, None, "up to 100 ACTORS, each getting a part of your contribution if they ACT Yes, but if they ACT No their part of your contribution will go to their next general election opponent")

	def test_pledge_keepemin(self):
		self._test_pledge(0, 1, None, "ACTORS who ACT Yes")

	def test_pledge_throwemout(self):
		self._test_pledge(0, -1, None, "the opponents in the next general election of ACTORS who ACT No")

	def test_pledge_partyfilter(self):
		self._test_pledge(0, 0, ActorParty.Democratic, "Democratic ACTORS who ACT Yes and the opponents in the next general election of ACTORS who ACT No if the opponent is in the Democratic party")

	def test_pledge_keepemin_partyfilter(self):
		self._test_pledge(0, 1, ActorParty.Democratic, "Democratic ACTORS who ACT Yes")

	def test_pledge_throwemout_partyfilter(self):
		self._test_pledge(0, -1, ActorParty.Democratic, "the opponents in the next general election of ACTORS who ACT No if the opponent is in the Democratic party")

	def test_recommendation(self):
		# Set up a recommendation.
		t1 = self.trigger
		c, t2 = create_trigger(self.trigger_type, 'test2', 'Another Trigger')
		TriggerRecommendation.objects.create(trigger1=t1, trigger2=t2)

		# Create a pledge.
		self.test_pledge_simple()

		# Was a notification created?
		from itfsite.models import Notification, NotificationType
		def notifs(): return Notification.objects.filter(user=self.user, notif_type=NotificationType.TriggerRecommendation)
		self.assertEqual(notifs().count(), 1)

		# Create another notification on the trigger the user already took action on.
		c, t3 = create_trigger(self.trigger_type, 'test3', 'Yet Another Trigger')
		TriggerRecommendation.objects.create(trigger1=t1, trigger2=t3).create_initial_notifications()
		self.assertEqual(notifs().count(), 2)


class ExecutionTestCase(TestCase):
	ACTORS_PER_PARTY = 20

	def setUp(self):
		# Replace the Democracy Engine API with our dummy class
		# so we don't make time consuming remote API calls.
		import contrib.bizlogic, contrib.de
		contrib.bizlogic.DemocracyEngineAPI = contrib.de.DummyDemocracyEngineAPIClient()

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

		# Campaign

		self.campaign = Campaign.objects.create(
			brand=0,
			subhead="This is a test campaign.",
			subhead_format=TextFormat.Markdown,
			body_text="This is a test campaign.",
			body_format=TextFormat.Markdown,
			)
		self.campaign.contrib_triggers.add(t)

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
		actor_outcomes = []
		for i, actor in enumerate(Actor.objects.all()):
			actor_outcomes.append({
				"actor": actor,
				"outcome": (i % 3) if (i % 3 < 2) else "Reason for not having an outcome.",
			})
		actor_outcomes_map = { item["actor"]: item["outcome"] for item in actor_outcomes }

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
			elif isinstance(actor_outcomes_map[action.actor], int):
				self.assertEqual(action.outcome, actor_outcomes_map[action.actor])
				self.assertEqual(action.reason_for_no_outcome, None)
			else:
				self.assertEqual(action.outcome, None)
				self.assertEqual(action.reason_for_no_outcome, actor_outcomes_map[action.actor])
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
			via_campaign=self.campaign,
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
			self.assertEqual(Contribution.aggregate(pledge_execution__trigger_execution=p.trigger.execution)[0], 0)
			return

		# Test more general properties.
		self.assertEqual(p.execution.problem, PledgeExecutionProblem.NoProblem)

		# Test that every Action lead to a Contribution.
		expected_contrib_count = 0
		expected_charge = 0
		expected_aggregates = dict()
		for action in t.execution.actions.all():
			contrib = p.execution.contributions.filter(action=action).first()
			if action.outcome is None:
				# We expect no contribution in this case.
				self.assertIsNone(contrib)
			else:
				# What Contribution should we expect?
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

				# What Contribution.aggregates should we check later?
				def mkfields(**fields):
					return tuple(sorted(fields.items()))
				for fields in [
						mkfields(trigger=p.trigger),
						mkfields(trigger=p.trigger, desired_outcome=desired_outcome),
						mkfields(trigger=p.trigger, action__actor=action.actor, incumbent=(action.outcome == p.desired_outcome))]:
					c = expected_aggregates.setdefault(fields, [0,0])
					c[0] += 1
					c[1] += expected_contrib_amount

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

		# Test contribution aggregates.

		for (fields, (count, amount)) in expected_aggregates.items():
			count_, amount_ = Contribution.aggregate(**dict(fields))
			self.assertEqual(count_, count)
			self.assertEqual(amount_, amount)
		self.assertEqual(Contribution.aggregate(trigger=p.trigger)[1], p.trigger.execution.total_contributions)
		self.assertEqual(Contribution.aggregate(trigger=p.trigger)[0], p.trigger.execution.num_contributions)
		def agg(a, incumbent):
			return Contribution.aggregate(trigger=p.trigger, action=a, incumbent=incumbent)
		totals_by_action = { }
		totals_by_actor = { }
		for a in p.trigger.execution.actions.all():
			aa = (agg(a, True), agg(a, False))
			self.assertEqual(aa[0][1], a.total_contributions_for)
			self.assertEqual(aa[1][1], a.total_contributions_against)
			totals_by_action[a] = aa
			totals_by_actor[a.actor] = aa
		for a in Contribution.aggregate("action", trigger=p.trigger):
			self.assertEqual(a[1][1], totals_by_action[a[0][0]][0][1] + totals_by_action[a[0][0]][1][1])
		for a in Contribution.aggregate("action", "incumbent", trigger=p.trigger):
			self.assertEqual(a[1][1], totals_by_action[a[0][0]][0 if a[0][1] else 1][1])
		for a in Contribution.aggregate("actor", "incumbent", trigger=p.trigger):
			self.assertEqual(a[1][1], totals_by_actor[a[0][0]][0 if a[0][1] else 1][1])
