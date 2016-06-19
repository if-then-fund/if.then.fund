# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import itfsite.utils
from decimal import Decimal
import enum3field
import contrib.models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('action_time', models.DateTimeField(help_text='The date & time the action actually ocurred in the real world.', db_index=True)),
                ('outcome', models.IntegerField(blank=True, help_text="The outcome index that was taken. May be null if the Actor should have participated but didn't (we want to record to avoid counterintuitive missing data).", null=True)),
                ('name_long', models.CharField(help_text="The long form of the person's name at the time of the action, meant for a page title.", max_length=128)),
                ('name_short', models.CharField(help_text="The short form of the person's name at the time of the action, usually a last name, meant for in-page second references.", max_length=128)),
                ('name_sort', models.CharField(help_text="The sorted list form of the person's name at the time of the action.", max_length=128)),
                ('party', enum3field.EnumField(contrib.models.ActorParty, help_text='The party of the Actor at the time of the action.', choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')])),
                ('title', models.CharField(help_text='Descriptive text for the office held by this actor at the time of the action.', max_length=200)),
                ('office', models.CharField(max_length=7, blank=True, help_text='A code specifying the office held by the Actor at the time the Action was created, in the same format as Recipient.office_sought.', null=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('total_contributions_for', models.DecimalField(decimal_places=2, max_digits=6, default=0, help_text='A cached total amount of campaign contributions executed with the actor as the recipient (excluding fees).')),
                ('total_contributions_against', models.DecimalField(decimal_places=2, max_digits=6, default=0, help_text='A cached total amount of campaign contributions executed with an opponent of the actor as the recipient (excluding fees).')),
                ('reason_for_no_outcome', models.CharField(max_length=200, blank=True, help_text="If outcome is null, why. E.g. 'Did not vote.'.", null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Actor',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('govtrack_id', models.IntegerField(unique=True, help_text="GovTrack's ID for this person.")),
                ('votervoice_id', models.IntegerField(blank=True, unique=True, null=True, help_text="VoterVoice's target ID for this person.")),
                ('office', models.CharField(max_length=7, blank=True, unique=True, null=True, help_text='A code specifying the office currently held by the Actor, in the same format as Recipient.office_sought.')),
                ('name_long', models.CharField(help_text="The long form of the person's current name, meant for a page title.", max_length=128)),
                ('name_short', models.CharField(help_text="The short form of the person's current name, usually a last name, meant for in-page second references.", max_length=128)),
                ('name_sort', models.CharField(help_text="The sorted list form of the person's current name.", max_length=128)),
                ('party', enum3field.EnumField(contrib.models.ActorParty, help_text='The current party of the Actor. For Members of Congress, this is based on how the Member caucuses to avoid Independent as much as possible.', choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')])),
                ('title', models.CharField(help_text='Descriptive text for the office held by this actor.', max_length=200)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('inactive_reason', models.CharField(max_length=200, blank=True, help_text="If the Actor is still a public official (i.e. generates Actions) but should not get contributions, the reason why. If not None, serves as a flag. E.g. 'Not running for reelection.'.", null=True)),
            ],
        ),
        migrations.CreateModel(
            name='CancelledPledge',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('pledge', itfsite.utils.JSONField(help_text='The original Pledge information.', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=6, help_text='The amount of the contribution, in dollars.')),
                ('refunded_time', models.DateTimeField(blank=True, help_text='If the contribution was refunded to the user, the time that happened.', null=True)),
                ('de_id', models.CharField(help_text='The Democracy Engine ID that the contribution was assigned to.', max_length=64)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information about the contribution.', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='ContributorInfo',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('cclastfour', models.CharField(max_length=4, db_index=True, blank=True, help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a pledge from a credit card number.", null=True)),
                ('is_geocoded', models.BooleanField(default=False, db_index=True, help_text='Whether this record has been geocoded.')),
                ('extra', itfsite.utils.JSONField(help_text='Schemaless data stored with this object.', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='IncompletePledge',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('email', models.EmailField(max_length=254, unique=True, db_index=True, help_text='An email address.')),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('sent_followup_at', models.DateTimeField(db_index=True, blank=True, help_text="If we've sent a follow-up email, the date and time we sent it.", null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Pledge',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('ref_code', models.CharField(max_length=24, db_index=True, blank=True, help_text='An optional referral code that lead the user to take this action.', null=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('algorithm', models.IntegerField(default=0, help_text='In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.')),
                ('status', enum3field.EnumField(contrib.models.PledgeStatus, default=contrib.models.PledgeStatus(1), help_text='The current status of the pledge.', choices=[(contrib.models.PledgeStatus(1), 'Open'), (contrib.models.PledgeStatus(2), 'Executed'), (contrib.models.PledgeStatus(10), 'Vacated')])),
                ('made_after_trigger_execution', models.BooleanField(default=False, help_text='Whether this Pledge was created after the Trigger was executed (i.e. outcomes known).')),
                ('desired_outcome', models.IntegerField(help_text='The outcome index that the user desires.')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=6, help_text='The pledge amount in dollars (including fees). The credit card charge may be less in the event that we have to round to the nearest penny-donation.')),
                ('incumb_challgr', models.FloatField(help_text='A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)')),
                ('filter_party', enum3field.EnumField(contrib.models.ActorParty, blank=True, help_text='Contributions only go to candidates whose party matches this party. Independent is not an allowed value here.', null=True, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')])),
                ('filter_competitive', models.BooleanField(default=False, help_text='Whether to filter contributions to competitive races.')),
                ('tip_to_campaign_owner', models.DecimalField(decimal_places=2, max_digits=6, default=Decimal('0'), help_text='The amount in dollars that the user desires to send to the owner of via_campaign, zero if there is no one to tip or the user desires not to tip.')),
                ('cclastfour', models.CharField(max_length=4, db_index=True, blank=True, help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a pledge from a credit card number.", null=True)),
                ('email_confirmed_at', models.DateTimeField(blank=True, help_text='The date and time that the email address of the pledge became confirmed, if the pledge was originally based on an unconfirmed email address.', null=True)),
                ('pre_execution_email_sent_at', models.DateTimeField(blank=True, help_text='The date and time when the user was sent an email letting them know that their pledge is about to be executed.', null=True)),
                ('post_execution_email_sent_at', models.DateTimeField(blank=True, help_text='The date and time when the user was sent an email letting them know that their pledge was executed.', null=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='PledgeExecution',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('problem', enum3field.EnumField(contrib.models.PledgeExecutionProblem, default=contrib.models.PledgeExecutionProblem(0), help_text='A problem code associated with a failure to make any contributions for the pledge.', choices=[(contrib.models.PledgeExecutionProblem(0), 'NoProblem'), (contrib.models.PledgeExecutionProblem(1), 'EmailUnconfirmed'), (contrib.models.PledgeExecutionProblem(2), 'FiltersExcludedAll'), (contrib.models.PledgeExecutionProblem(3), 'TransactionFailed'), (contrib.models.PledgeExecutionProblem(4), 'Voided')])),
                ('charged', models.DecimalField(decimal_places=2, max_digits=6, help_text="The amount the user's account was actually charged, in dollars and including fees. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates.")),
                ('fees', models.DecimalField(decimal_places=2, max_digits=6, help_text='The fees the user was charged, in dollars.')),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('district', models.CharField(max_length=4, db_index=True, blank=True, help_text='The congressional district of the user (at the time of the pledge), in the form of XX00.', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Recipient',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('de_id', models.CharField(unique=True, max_length=64, help_text='The Democracy Engine ID that we have assigned to this recipient.')),
                ('active', models.BooleanField(default=True, help_text='Whether this Recipient can currently receive funds.')),
                ('office_sought', models.CharField(max_length=7, db_index=True, blank=True, help_text="For challengers, a code specifying the office sought in the form of 'S-NY-I' (New York class 1 senate seat) or 'H-TX-30' (Texas 30th congressional district). Unique with party.", null=True)),
                ('party', enum3field.EnumField(contrib.models.ActorParty, blank=True, help_text='The party of the challenger, or null if this Recipient is for an incumbent. Unique with office_sought.', null=True, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')])),
            ],
        ),
        migrations.CreateModel(
            name='Tip',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=6, help_text='The amount of the tip, in dollars.')),
                ('de_recip_id', models.CharField(max_length=64, db_index=True, blank=True, help_text='The recipient ID on Democracy Engine that received the tip.', null=True)),
                ('ref_code', models.CharField(max_length=24, db_index=True, blank=True, help_text='An optional referral code that lead the user to take this action.', null=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Trigger',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('key', models.CharField(null=True, db_index=True, max_length=64, unique=True, blank=True, help_text='An opaque look-up key to quickly locate this object.')),
                ('title', models.CharField(help_text='The legislative action that this trigger is about, in wonky language.', max_length=200)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('description', models.TextField(help_text='Describe what event will cause contributions to be made. Use the second person and future tense, e.g. by starting with "Your contribution will...". The text is in the format given by description_format.')),
                ('description_format', enum3field.EnumField(itfsite.utils.TextFormat, default=itfsite.utils.TextFormat(1), help_text='The format of the description text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('status', enum3field.EnumField(contrib.models.TriggerStatus, default=contrib.models.TriggerStatus(0), help_text='The current status of the trigger: Open (accepting pledges), Paused (not accepting pledges), Executed (funds distributed), Vacated (existing pledges invalidated).', choices=[(contrib.models.TriggerStatus(0), 'Draft'), (contrib.models.TriggerStatus(1), 'Open'), (contrib.models.TriggerStatus(2), 'Paused'), (contrib.models.TriggerStatus(3), 'Executed'), (contrib.models.TriggerStatus(4), 'Vacated')])),
                ('outcomes', itfsite.utils.JSONField(default='[{"object": "in favor of the bill", "vote_key": "+", "label": "Yes on This Vote"}, {"object": "against passage of the bill", "vote_key": "-", "label": "No on This Vote"}]', help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].")),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('pledge_count', models.IntegerField(default=0, help_text='A cached count of the number of pledges made *prior* to trigger execution (excludes Pledges with made_after_trigger_execution).')),
                ('total_pledged', models.DecimalField(decimal_places=2, max_digits=6, default=0, help_text='A cached total amount of pledges made *prior* to trigger execution (excludes Pledges with made_after_trigger_execution).', db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='TriggerCustomization',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('outcome', models.IntegerField(verbose_name='Restrict Outcome', blank=True, help_text='Restrict Pledges to this outcome.', null=True)),
                ('incumb_challgr', models.FloatField(verbose_name='Restrict Incumbent-Challenger Choice', blank=True, help_text="Restrict Pledges to be for just incumbents, just challengers, both incumbents and challengers (where user can't pick), or don't restrict the user's choice.", null=True)),
                ('filter_party', enum3field.EnumField(contrib.models.ActorParty, verbose_name='Restrict Party', blank=True, help_text='Restrict Pledges to be to candidates of this party.', null=True, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')])),
                ('filter_competitive', models.NullBooleanField(verbose_name='Restrict Competitive Filter', default=False, help_text='Restrict Pledges to this filter_competitive value.')),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='TriggerExecution',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('action_time', models.DateTimeField(help_text='The date & time the action actually ocurred in the real world.')),
                ('cycle', models.IntegerField(help_text='The election cycle (year) that the trigger was executed in.')),
                ('description', models.TextField(help_text='Describe how contriutions are being distributed. Use the passive voice and present progressive tense, e.g. by starting with "Contributions are being distributed...".')),
                ('description_format', enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the description text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('pledge_count', models.IntegerField(default=0, help_text='A cached count of the number of pledges executed. This counts pledges from anonymous users that do not result in contributions. Used to check when a Trigger is done executing.')),
                ('pledge_count_with_contribs', models.IntegerField(default=0, help_text='A cached count of the number of pledges executed with actual contributions made.')),
                ('num_contributions', models.IntegerField(default=0, help_text='A cached total number of campaign contributions executed.', db_index=True)),
                ('total_contributions', models.DecimalField(decimal_places=2, max_digits=6, default=0, help_text='A cached total amount of campaign contributions executed, excluding fees.', db_index=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('trigger', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='contrib.Trigger', related_name='execution', help_text='The Trigger this execution information is about.')),
            ],
        ),
        migrations.CreateModel(
            name='TriggerRecommendation',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('symmetric', models.BooleanField(default=False, help_text='If true, the recommendation goes both ways.')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('notifications_created', models.BooleanField(default=False, db_index=True, help_text='Set to true once notifications have been generated for users for any past actions the users took before this recommendation was added.')),
                ('trigger1', models.ForeignKey(to='contrib.Trigger', related_name='recommends', help_text='If a user has taken action on this Trigger, then we send them a notification.')),
                ('trigger2', models.ForeignKey(to='contrib.Trigger', related_name='recommended_by', help_text='This is the trigger that we recommend the user take action on.')),
            ],
        ),
        migrations.CreateModel(
            name='TriggerStatusUpdate',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('text', models.TextField(help_text='Status update text in the format given by text_format.')),
                ('text_format', enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('trigger', models.ForeignKey(help_text='The Trigger that this update is about.', to='contrib.Trigger')),
            ],
        ),
        migrations.CreateModel(
            name='TriggerType',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('key', models.CharField(null=True, db_index=True, max_length=64, unique=True, blank=True, help_text='An opaque look-up key to quickly locate this object.')),
                ('title', models.CharField(help_text='The title for the trigger.', max_length=200)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('strings', itfsite.utils.JSONField(default={}, help_text='A dictionary of displayable text.')),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
        ),
    ]
