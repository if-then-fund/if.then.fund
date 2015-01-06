# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion
import enum3field
import jsonfield.fields
import contrib.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('action_time', models.DateTimeField(db_index=True, help_text='The date & time the action actually ocurred in the real world.')),
                ('outcome', models.IntegerField(help_text="The outcome index that was taken. May be null if the Actor should have participated but didn't (we want to record to avoid counterintuitive missing data).", null=True, blank=True)),
                ('name_long', models.CharField(max_length=128, help_text="The long form of the person's name at the time of the action, meant for a page title.")),
                ('name_short', models.CharField(max_length=128, help_text="The short form of the person's name at the time of the action, usually a last name, meant for in-page second references.")),
                ('name_sort', models.CharField(max_length=128, help_text="The sorted list form of the person's name at the time of the action.")),
                ('party', enum3field.EnumField(contrib.models.ActorParty, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], help_text='The party of the Actor at the time of the action.')),
                ('title', models.CharField(max_length=200, help_text='Descriptive text for the office held by this actor at the time of the action.')),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('total_contributions_for', models.DecimalField(default=0, max_digits=6, help_text='A cached total amount of campaign contributions executed with the actor as the recipient (excluding fees).', decimal_places=2)),
                ('total_contributions_against', models.DecimalField(default=0, max_digits=6, help_text='A cached total amount of campaign contributions executed with an opponent of the actor as the recipient (excluding fees).', decimal_places=2)),
                ('reason_for_no_outcome', models.CharField(help_text="If outcome is null, why. E.g. 'Did not vote.'.", max_length=200, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Actor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('govtrack_id', models.IntegerField(help_text="GovTrack's ID for this person.", unique=True)),
                ('name_long', models.CharField(max_length=128, help_text="The long form of the person's current name, meant for a page title.")),
                ('name_short', models.CharField(max_length=128, help_text="The short form of the person's current name, usually a last name, meant for in-page second references.")),
                ('name_sort', models.CharField(max_length=128, help_text="The sorted list form of the person's current name.")),
                ('party', enum3field.EnumField(contrib.models.ActorParty, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], help_text='The current party of the Actor. For Members of Congress, this is based on how the Member caucuses to avoid Independent as much as possible.')),
                ('title', models.CharField(max_length=200, help_text='Descriptive text for the office held by this actor.')),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CancelledPledge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('email', models.EmailField(help_text='The email address of an unconfirmed pledge.', max_length=254, null=True, blank=True)),
                ('pledge', jsonfield.fields.JSONField(blank=True, help_text='The original Pledge information.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('amount', models.DecimalField(max_digits=6, help_text='The amount of the contribution, in dollars.', decimal_places=2)),
                ('refunded_time', models.DateTimeField(help_text='If the contribution was refunded to the user, the time that happened.', null=True, blank=True)),
                ('de_id', models.CharField(max_length=64, help_text='The Democracy Engine ID that the contribution was assigned to.')),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information about the contribution.')),
                ('action', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='contrib.Action', help_text='The Action this contribution was made in reaction to.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContributionAggregate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('outcome', models.IntegerField(help_text='The outcome index that was taken. Null if the slice encompasses all outcomes.', null=True, blank=True)),
                ('district', models.CharField(help_text='The congressional district of the user (at the time of the pledge), in the form of XX00. Null if the slice encompasses all district.', max_length=4, null=True, blank=True)),
                ('total', models.DecimalField(default=0, db_index=True, max_digits=6, help_text='A cached total amount of campaign contributions executed, excluding fees.', decimal_places=2)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Pledge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('email', models.EmailField(help_text='When an anonymous user makes a pledge, their email address is stored here and we send a confirmation email.', max_length=254, null=True, blank=True)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('algorithm', models.IntegerField(default=0, help_text='In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.')),
                ('status', enum3field.EnumField(contrib.models.PledgeStatus, default=contrib.models.PledgeStatus(1), choices=[(contrib.models.PledgeStatus(1), 'Open'), (contrib.models.PledgeStatus(2), 'Executed'), (contrib.models.PledgeStatus(10), 'Vacated')], help_text='The current status of the pledge.')),
                ('desired_outcome', models.IntegerField(help_text='The outcome index that the user desires.')),
                ('amount', models.DecimalField(max_digits=6, help_text='The pledge amount in dollars (including fees). The credit card charge may be less in the event that we have to round to the nearest penny-donation.', decimal_places=2)),
                ('incumb_challgr', models.FloatField(help_text='A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)')),
                ('filter_party', enum3field.EnumField(contrib.models.ActorParty, help_text='Contributions only go to candidates whose party matches this party. Independent is not an allowed value here.', choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], null=True, blank=True)),
                ('filter_competitive', models.BooleanField(default=False, help_text='Whether to filter contributions to competitive races.')),
                ('cclastfour', models.CharField(help_text="The last four digits of the user's credit card number, stored for fast look-up in case we need to find a pledge from a credit card number.", max_length=4, null=True, blank=True, db_index=True)),
                ('pre_execution_email_sent_at', models.DateTimeField(help_text='The date and time when the user was sent an email letting them know that their pledge is about to be executed.', null=True, blank=True)),
                ('post_execution_email_sent_at', models.DateTimeField(help_text='The date and time when the user was sent an email letting them know that their pledge was executed.', null=True, blank=True)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PledgeExecution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('problem', enum3field.EnumField(contrib.models.PledgeExecutionProblem, default=contrib.models.PledgeExecutionProblem(0), choices=[(contrib.models.PledgeExecutionProblem(0), 'NoProblem'), (contrib.models.PledgeExecutionProblem(1), 'EmailUnconfirmed'), (contrib.models.PledgeExecutionProblem(2), 'FiltersExcludedAll'), (contrib.models.PledgeExecutionProblem(3), 'TransactionFailed')], help_text='A problem code associated with a failure to make any contributions for the pledge.')),
                ('charged', models.DecimalField(max_digits=6, help_text="The amount the user's account was actually charged, in dollars and including fees. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates.", decimal_places=2)),
                ('fees', models.DecimalField(max_digits=6, help_text='The fees the user was charged, in dollars.', decimal_places=2)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('district', models.CharField(help_text='The congressional district of the user (at the time of the pledge), in the form of XX00.', max_length=4, null=True, blank=True, db_index=True)),
                ('pledge', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='contrib.Pledge', help_text='The Pledge this execution information is about.', related_name='execution')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Recipient',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('de_id', models.CharField(max_length=64, help_text='The Democracy Engine ID that we have assigned to this recipient.', unique=True)),
                ('active', models.BooleanField(default=True, help_text='Whether this Recipient can currently receive funds.')),
                ('office_sought', models.CharField(help_text="For challengers, a code specifying the office sought in the form of 'S-NY-I' (New York class 1 senate seat) or 'H-TX-30' (Texas 30th congressional district). Unique with party.", max_length=7, null=True, blank=True)),
                ('party', enum3field.EnumField(contrib.models.ActorParty, help_text='The party of the challenger, or null if this Recipient is for an incumbent. Unique with office_sought.', choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], null=True, blank=True)),
                ('actor', models.ForeignKey(null=True, unique=True, to='contrib.Actor', blank=True, help_text='The Actor that this recipient corresponds to (i.e. this Recipient is an incumbent).')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Trigger',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('key', models.CharField(db_index=True, null=True, unique=True, blank=True, max_length=64, help_text='An opaque look-up key to quickly locate this object.')),
                ('title', models.CharField(max_length=200, help_text='The title for the trigger.')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('slug', models.SlugField(max_length=200, help_text='The URL slug for this trigger.')),
                ('description', models.TextField(help_text='Description text in Markdown.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')], help_text='The format of the description text.')),
                ('status', enum3field.EnumField(contrib.models.TriggerStatus, default=contrib.models.TriggerStatus(0), choices=[(contrib.models.TriggerStatus(0), 'Draft'), (contrib.models.TriggerStatus(1), 'Open'), (contrib.models.TriggerStatus(2), 'Paused'), (contrib.models.TriggerStatus(3), 'Executed'), (contrib.models.TriggerStatus(4), 'Vacated')], help_text='The current status of the trigger: Open (accepting pledges), Paused (not accepting pledges), Executed (funds distributed), Vacated (existing pledges invalidated).')),
                ('outcomes', jsonfield.fields.JSONField(default=[], help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].")),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('pledge_count', models.IntegerField(default=0, help_text='A cached count of the number of pledges made.')),
                ('total_pledged', models.DecimalField(default=0, db_index=True, max_digits=6, help_text='A cached total amount of pledges, i.e. prior to execution.', decimal_places=2)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, null=True, to=settings.AUTH_USER_MODEL, blank=True, help_text='The user which created the trigger and can update it.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerExecution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('action_time', models.DateTimeField(help_text='The date & time the action actually ocurred in the real world.')),
                ('cycle', models.IntegerField(help_text='The election cycle (year) that the trigger was executed in.')),
                ('description', models.TextField(help_text='Once a trigger is executed, additional text added to explain how funds were distributed.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')], help_text='The format of the description text.')),
                ('pledge_count', models.IntegerField(default=0, help_text='A cached count of the number of pledges executed. This counts pledges from unconfirmed email addresses that do not result in contributions. Used to check when a Trigger is done executing.')),
                ('pledge_count_with_contribs', models.IntegerField(default=0, help_text='A cached count of the number of pledges executed with actual contributions made.')),
                ('num_contributions', models.IntegerField(default=0, db_index=True, help_text='A cached total number of campaign contributions executed.')),
                ('total_contributions', models.DecimalField(default=0, db_index=True, max_digits=6, help_text='A cached total amount of campaign contributions executed, excluding fees.', decimal_places=2)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('trigger', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='contrib.Trigger', help_text='The Trigger this execution information is about.', related_name='execution')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerStatusUpdate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('text', models.TextField(help_text='Status update text in Markdown.')),
                ('text_format', enum3field.EnumField(contrib.models.TextFormat, choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')], help_text='The format of the text.')),
                ('trigger', models.ForeignKey(to='contrib.Trigger', help_text='The Trigger that this update is about.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('key', models.CharField(db_index=True, null=True, unique=True, blank=True, max_length=64, help_text='An opaque look-up key to quickly locate this object.')),
                ('title', models.CharField(max_length=200, help_text='The title for the trigger.')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('strings', jsonfield.fields.JSONField(default={}, help_text='A dictionary of displayable text.')),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='trigger',
            name='trigger_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='contrib.TriggerType', help_text='The type of the trigger, which determines how it is described in text.'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='recipient',
            unique_together=set([('office_sought', 'party')]),
        ),
        migrations.AddField(
            model_name='pledgeexecution',
            name='trigger_execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pledges', to='contrib.TriggerExecution', help_text='The TriggerExecution this execution information is about.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='trigger',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pledges', to='contrib.Trigger', help_text='The Trigger that this Pledge is for.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, null=True, to=settings.AUTH_USER_MODEL, blank=True, help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored, and the pledge should be considered unconfirmed/provisional and will not be executed."),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='pledge',
            unique_together=set([('trigger', 'email'), ('trigger', 'user')]),
        ),
        migrations.AddField(
            model_name='contributionaggregate',
            name='trigger_execution',
            field=models.ForeignKey(related_name='contribution_aggregates', to='contrib.TriggerExecution', help_text='The TriggerExecution that these cached statistics are about.'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'outcome', 'district')]),
        ),
        migrations.AddField(
            model_name='contribution',
            name='pledge_execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contributions', to='contrib.PledgeExecution', help_text='The PledgeExecution this execution information is about.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='contribution',
            name='recipient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contributions', to='contrib.Recipient', help_text='The Recipient this contribution was sent to.'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contribution',
            unique_together=set([('pledge_execution', 'recipient'), ('pledge_execution', 'action')]),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='trigger',
            field=models.ForeignKey(to='contrib.Trigger', help_text='The Trigger that the pledge was for.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='user',
            field=models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, blank=True, help_text='The user who made the pledge, if not anonymous.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='actor',
            name='challenger',
            field=models.OneToOneField(null=True, to='contrib.Recipient', blank=True, help_text="The Recipient that contributions to this Actor's challenger go to. Independents don't have challengers because they have no opposing party.", related_name='challenger_to'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='actor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='contrib.Actor', help_text='The Actor who took this action.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='challenger',
            field=models.ForeignKey(null=True, to='contrib.Recipient', blank=True, help_text="The Recipient that contributions to this Actor's challenger go to, at the time of the Action. Independents don't have challengers because they have no opposing party."),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='execution',
            field=models.ForeignKey(related_name='actions', to='contrib.TriggerExecution', help_text='The TriggerExecution that created this object.'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='action',
            unique_together=set([('execution', 'actor')]),
        ),
    ]
