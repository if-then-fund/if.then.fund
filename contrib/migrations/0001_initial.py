# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import contrib.models
from django.conf import settings
import enum3field
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('action_time', models.DateTimeField(help_text='The date & time the action actually ocurred in the real world.', db_index=True)),
                ('outcome', models.IntegerField(help_text="The outcome index that was taken. May be null if the Actor should have participated but didn't (we want to record to avoid counterintuitive missing data).", blank=True, null=True)),
                ('name_long', models.CharField(help_text="The long form of the person's name at the time of the action, meant for a page title.", max_length=128)),
                ('name_short', models.CharField(help_text="The short form of the person's name at the time of the action, usually a last name, meant for in-page second references.", max_length=128)),
                ('name_sort', models.CharField(help_text="The sorted list form of the person's name at the time of the action.", max_length=128)),
                ('party', enum3field.EnumField(contrib.models.ActorParty, help_text='The party of the Actor at the time of the action.', choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')])),
                ('title', models.CharField(help_text='Descriptive text for the office held by this actor at the time of the action.', max_length=200)),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('total_contributions_for', models.DecimalField(help_text='A cached total amount of campaign contributions executed with the actor as the recipient (excluding fees).', decimal_places=2, default=0, max_digits=6)),
                ('total_contributions_against', models.DecimalField(help_text='A cached total amount of campaign contributions executed with an opponent of the actor as the recipient (excluding fees).', decimal_places=2, default=0, max_digits=6)),
                ('reason_for_no_outcome', models.CharField(help_text="If outcome is null, why. E.g. 'Did not vote.'.", blank=True, null=True, max_length=200)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Actor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('govtrack_id', models.IntegerField(help_text="GovTrack's ID for this person.", unique=True)),
                ('name_long', models.CharField(help_text="The long form of the person's current name, meant for a page title.", max_length=128)),
                ('name_short', models.CharField(help_text="The short form of the person's current name, usually a last name, meant for in-page second references.", max_length=128)),
                ('name_sort', models.CharField(help_text="The sorted list form of the person's current name.", max_length=128)),
                ('party', enum3field.EnumField(contrib.models.ActorParty, help_text='The current party of the Actor. For Members of Congress, this is based on how the Member caucuses to avoid Independent as much as possible.', choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')])),
                ('title', models.CharField(help_text='Descriptive text for the office held by this actor.', max_length=200)),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CancelledPledge',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('email', models.EmailField(help_text='The email address of an unconfirmed pledge.', blank=True, null=True, max_length=254)),
                ('pledge', contrib.models.JSONField(help_text='The original Pledge information.', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('amount', models.DecimalField(help_text='The amount of the contribution, in dollars.', decimal_places=2, max_digits=6)),
                ('refunded_time', models.DateTimeField(help_text='If the contribution was refunded to the user, the time that happened.', blank=True, null=True)),
                ('de_id', models.CharField(help_text='The Democracy Engine ID that the contribution was assigned to.', max_length=64)),
                ('extra', contrib.models.JSONField(help_text='Additional information about the contribution.', blank=True)),
                ('action', models.ForeignKey(help_text='The Action this contribution was made in reaction to.', to='contrib.Action', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContributionAggregate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('outcome', models.IntegerField(help_text='The outcome index that was taken. Null if the slice encompasses all outcomes.', blank=True, null=True)),
                ('district', models.CharField(help_text='The congressional district of the user (at the time of the pledge), in the form of XX00. Null if the slice encompasses all district.', blank=True, null=True, max_length=4)),
                ('total', models.DecimalField(help_text='A cached total amount of campaign contributions executed, excluding fees.', db_index=True, decimal_places=2, default=0, max_digits=6)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Pledge',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('email', models.EmailField(help_text='When an anonymous user makes a pledge, their email address is stored here and we send a confirmation email.', blank=True, null=True, max_length=254)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('algorithm', models.IntegerField(help_text='In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.', default=0)),
                ('status', enum3field.EnumField(contrib.models.PledgeStatus, help_text='The current status of the pledge.', choices=[(contrib.models.PledgeStatus(1), 'Open'), (contrib.models.PledgeStatus(2), 'Executed'), (contrib.models.PledgeStatus(10), 'Vacated')], default=contrib.models.PledgeStatus(1))),
                ('desired_outcome', models.IntegerField(help_text='The outcome index that the user desires.')),
                ('amount', models.DecimalField(help_text='The pledge amount in dollars (including fees). The credit card charge may be less in the event that we have to round to the nearest penny-donation.', decimal_places=2, max_digits=6)),
                ('incumb_challgr', models.FloatField(help_text='A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)')),
                ('filter_party', enum3field.EnumField(contrib.models.ActorParty, help_text='Contributions only go to candidates whose party matches this party. Independent is not an allowed value here.', blank=True, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], null=True)),
                ('filter_competitive', models.BooleanField(help_text='Whether to filter contributions to competitive races.', default=False)),
                ('cclastfour', models.CharField(help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a pledge from a credit card number.", blank=True, db_index=True, null=True, max_length=4)),
                ('pre_execution_email_sent_at', models.DateTimeField(help_text='The date and time when the user was sent an email letting them know that their pledge is about to be executed.', blank=True, null=True)),
                ('post_execution_email_sent_at', models.DateTimeField(help_text='The date and time when the user was sent an email letting them know that their pledge was executed.', blank=True, null=True)),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PledgeExecution',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('problem', enum3field.EnumField(contrib.models.PledgeExecutionProblem, help_text='A problem code associated with a failure to make any contributions for the pledge.', choices=[(contrib.models.PledgeExecutionProblem(0), 'NoProblem'), (contrib.models.PledgeExecutionProblem(1), 'EmailUnconfirmed'), (contrib.models.PledgeExecutionProblem(2), 'FiltersExcludedAll'), (contrib.models.PledgeExecutionProblem(3), 'TransactionFailed')], default=contrib.models.PledgeExecutionProblem(0))),
                ('charged', models.DecimalField(help_text="The amount the user's account was actually charged, in dollars and including fees. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates.", decimal_places=2, max_digits=6)),
                ('fees', models.DecimalField(help_text='The fees the user was charged, in dollars.', decimal_places=2, max_digits=6)),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('district', models.CharField(help_text='The congressional district of the user (at the time of the pledge), in the form of XX00.', blank=True, db_index=True, null=True, max_length=4)),
                ('pledge', models.OneToOneField(help_text='The Pledge this execution information is about.', to='contrib.Pledge', on_delete=django.db.models.deletion.PROTECT, related_name='execution')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Recipient',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('de_id', models.CharField(help_text='The Democracy Engine ID that we have assigned to this recipient.', max_length=64, unique=True)),
                ('active', models.BooleanField(help_text='Whether this Recipient can currently receive funds.', default=True)),
                ('office_sought', models.CharField(help_text="For challengers, a code specifying the office sought in the form of 'S-NY-I' (New York class 1 senate seat) or 'H-TX-30' (Texas 30th congressional district). Unique with party.", blank=True, null=True, max_length=7)),
                ('party', enum3field.EnumField(contrib.models.ActorParty, help_text='The party of the challenger, or null if this Recipient is for an incumbent. Unique with office_sought.', blank=True, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], null=True)),
                ('actor', models.ForeignKey(help_text='The Actor that this recipient corresponds to (i.e. this Recipient is an incumbent).', blank=True, to='contrib.Actor', null=True, unique=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Trigger',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('key', models.CharField(help_text='An opaque look-up key to quickly locate this object.', blank=True, unique=True, max_length=64, db_index=True, null=True)),
                ('title', models.CharField(help_text='The title for the trigger.', max_length=200)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('slug', models.SlugField(help_text='The URL slug for this trigger.', max_length=200)),
                ('description', models.TextField(help_text='Description text in Markdown.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, help_text='The format of the description text.', choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')])),
                ('status', enum3field.EnumField(contrib.models.TriggerStatus, help_text='The current status of the trigger: Open (accepting pledges), Paused (not accepting pledges), Executed (funds distributed), Vacated (existing pledges invalidated).', choices=[(contrib.models.TriggerStatus(0), 'Draft'), (contrib.models.TriggerStatus(1), 'Open'), (contrib.models.TriggerStatus(2), 'Paused'), (contrib.models.TriggerStatus(3), 'Executed'), (contrib.models.TriggerStatus(4), 'Vacated')], default=contrib.models.TriggerStatus(0))),
                ('outcomes', contrib.models.JSONField(help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].", default=[])),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('pledge_count', models.IntegerField(help_text='A cached count of the number of pledges made.', default=0)),
                ('total_pledged', models.DecimalField(help_text='A cached total amount of pledges, i.e. prior to execution.', db_index=True, decimal_places=2, default=0, max_digits=6)),
                ('owner', models.ForeignKey(help_text='The user which created the trigger and can update it.', blank=True, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerExecution',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('action_time', models.DateTimeField(help_text='The date & time the action actually ocurred in the real world.')),
                ('cycle', models.IntegerField(help_text='The election cycle (year) that the trigger was executed in.')),
                ('description', models.TextField(help_text='Once a trigger is executed, additional text added to explain how funds were distributed.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, help_text='The format of the description text.', choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')])),
                ('pledge_count', models.IntegerField(help_text='A cached count of the number of pledges executed. This counts pledges from unconfirmed email addresses that do not result in contributions. Used to check when a Trigger is done executing.', default=0)),
                ('pledge_count_with_contribs', models.IntegerField(help_text='A cached count of the number of pledges executed with actual contributions made.', default=0)),
                ('num_contributions', models.IntegerField(help_text='A cached total number of campaign contributions executed.', db_index=True, default=0)),
                ('total_contributions', models.DecimalField(help_text='A cached total amount of campaign contributions executed, excluding fees.', db_index=True, decimal_places=2, default=0, max_digits=6)),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('trigger', models.OneToOneField(help_text='The Trigger this execution information is about.', to='contrib.Trigger', on_delete=django.db.models.deletion.PROTECT, related_name='execution')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerStatusUpdate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('text', models.TextField(help_text='Status update text in Markdown.')),
                ('text_format', enum3field.EnumField(contrib.models.TextFormat, help_text='The format of the text.', choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')])),
                ('trigger', models.ForeignKey(help_text='The Trigger that this update is about.', to='contrib.Trigger')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('key', models.CharField(help_text='An opaque look-up key to quickly locate this object.', blank=True, unique=True, max_length=64, db_index=True, null=True)),
                ('title', models.CharField(help_text='The title for the trigger.', max_length=200)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('strings', contrib.models.JSONField(help_text='A dictionary of displayable text.', default={})),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='trigger',
            name='trigger_type',
            field=models.ForeignKey(help_text='The type of the trigger, which determines how it is described in text.', to='contrib.TriggerType', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='recipient',
            unique_together=set([('office_sought', 'party')]),
        ),
        migrations.AddField(
            model_name='pledgeexecution',
            name='trigger_execution',
            field=models.ForeignKey(help_text='The TriggerExecution this execution information is about.', to='contrib.TriggerExecution', on_delete=django.db.models.deletion.PROTECT, related_name='pledges'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='trigger',
            field=models.ForeignKey(help_text='The Trigger that this Pledge is for.', to='contrib.Trigger', on_delete=django.db.models.deletion.PROTECT, related_name='pledges'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='user',
            field=models.ForeignKey(help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored, and the pledge should be considered unconfirmed/provisional and will not be executed.", blank=True, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='pledge',
            unique_together=set([('trigger', 'user'), ('trigger', 'email')]),
        ),
        migrations.AddField(
            model_name='contributionaggregate',
            name='trigger_execution',
            field=models.ForeignKey(help_text='The TriggerExecution that these cached statistics are about.', to='contrib.TriggerExecution', related_name='contribution_aggregates'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'outcome', 'district')]),
        ),
        migrations.AddField(
            model_name='contribution',
            name='pledge_execution',
            field=models.ForeignKey(help_text='The PledgeExecution this execution information is about.', to='contrib.PledgeExecution', on_delete=django.db.models.deletion.PROTECT, related_name='contributions'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='contribution',
            name='recipient',
            field=models.ForeignKey(help_text='The Recipient this contribution was sent to.', to='contrib.Recipient', on_delete=django.db.models.deletion.PROTECT, related_name='contributions'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contribution',
            unique_together=set([('pledge_execution', 'action'), ('pledge_execution', 'recipient')]),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='trigger',
            field=models.ForeignKey(help_text='The Trigger that the pledge was for.', to='contrib.Trigger'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='user',
            field=models.ForeignKey(help_text='The user who made the pledge, if not anonymous.', blank=True, to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='actor',
            name='challenger',
            field=models.OneToOneField(help_text="The Recipient that contributions to this Actor's challenger go to. Independents don't have challengers because they have no opposing party.", blank=True, to='contrib.Recipient', null=True, related_name='challenger_to'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='actor',
            field=models.ForeignKey(help_text='The Actor who took this action.', to='contrib.Actor', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='challenger',
            field=models.ForeignKey(help_text="The Recipient that contributions to this Actor's challenger go to, at the time of the Action. Independents don't have challengers because they have no opposing party.", blank=True, to='contrib.Recipient', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='execution',
            field=models.ForeignKey(help_text='The TriggerExecution that created this object.', to='contrib.TriggerExecution', related_name='actions'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='action',
            unique_together=set([('execution', 'actor')]),
        ),
    ]
