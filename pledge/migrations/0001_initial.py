# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import enum3field
import django.db.models.deletion
import jsonfield.fields
import pledge.models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('outcome', models.IntegerField(help_text='The outcome index that was taken.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Actor',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('key', models.CharField(unique=True, db_index=True, max_length=64, help_text='An opaque look-up key to quickly locate this object.')),
                ('name_long', models.CharField(max_length=128, help_text="The long form of the person's current name, meant for a page title.")),
                ('name_short', models.CharField(max_length=128, help_text="The short form of the person's current name, usually a last name, meant for in-page second references.")),
                ('name_sort', models.CharField(max_length=128, help_text="The sorted list form of the person's current name.")),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('cycle', models.IntegerField(help_text='The election cycle (year) of the campaign.')),
                ('candidate', models.IntegerField(blank=True, help_text='For candidates that are not also Actors, a unique identifier for the candidate that spans Campaign objects (which are cycle-specific).', db_index=True, null=True)),
                ('name_long', models.CharField(max_length=128, help_text="The long form of the candidates's name during this campaign, meant for a page title.")),
                ('name_short', models.CharField(max_length=128, help_text="The short form of the candidates's name during this campaign, usually a last name, meant for in-page second references.")),
                ('name_sort', models.CharField(max_length=128, help_text="The sorted list form of the candidates's name during this campaign.")),
                ('party', models.CharField(max_length=128, help_text="Candidate's party during this campaign.")),
                ('fec_id', models.CharField(blank=True, help_text='The FEC ID of the campaign.', max_length=64, null=True)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('actor', models.ForeignKey(help_text='If the candidate of this campaign is an Actor, then the Actor.', to='pledge.Actor', blank=True, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('status', enum3field.EnumField(pledge.models.ContributionStatus, choices=[(pledge.models.ContributionStatus(1), 'Pending'), (pledge.models.ContributionStatus(2), 'Executed'), (pledge.models.ContributionStatus(3), 'Vacated'), (pledge.models.ContributionStatus(10), 'AbortedActorQuit'), (pledge.models.ContributionStatus(11), 'AbortedOverLimitTarget'), (pledge.models.ContributionStatus(12), 'AbortedOverLimitAll'), (pledge.models.ContributionStatus(13), 'AbortedUnopposed')], help_text='The status of the contribution: Pending (opponent not known), Executed, Vacated (no opponent exists)')),
                ('execution_time', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('amount', models.FloatField(help_text='The amount of the contribution, in dollars.')),
                ('is_opponent', models.BooleanField(default=False, help_text='Is the target the actor (False) or the general election opponent of the actor (True)?')),
                ('refunded_time', models.DateTimeField(blank=True, help_text='If the contribution was refunded to the user, the time that happened.', null=True)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information about the contribution.')),
                ('action', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pledge.Action', help_text='The Action (including Actor) this contribution was triggered for.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Pledge',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('algorithm', models.IntegerField(default=0, help_text='In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.')),
                ('desired_outcome', models.IntegerField(help_text='The outcome index that the user desires.')),
                ('amount', models.FloatField(help_text='The pledge amount in dollars.')),
                ('incumb_challgr', models.FloatField(help_text='A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)')),
                ('filter_party', models.CharField(blank=True, help_text="Whether to filter contributions to one of the major parties ('D' or 'R'), or null to not filter.", choices=[('D', 'D'), ('R', 'R')], max_length=1, null=True)),
                ('filter_competitive', models.BooleanField(default=False, help_text='Whether to filter contributions to competitive races.')),
                ('cancelled', models.BooleanField(default=False, help_text='True if the user cancels the pledge prior to execution.')),
                ('vacated', models.BooleanField(default=False, help_text='True if the Trigger is vacated.')),
                ('district', models.CharField(blank=True, help_text='The congressional district of the user (at the time of the pledge), if their address is in a congressional district.', db_index=True, max_length=64, null=True)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PledgeExecution',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('charged', models.FloatField(help_text="The amount the user's account was actually charged, in dollars. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates.")),
                ('fees', jsonfield.fields.JSONField(help_text='A dictionary representing all fees on the charge.')),
                ('contributions_executed', models.FloatField(help_text='The total amount of executed camapaign contributions to-date.')),
                ('contributions_pending', models.FloatField(help_text='The current total amount of pending camapaign contributions.')),
                ('pledge', models.OneToOneField(help_text='The Pledge this execution information is about.', to='pledge.Pledge', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Trigger',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('key', models.CharField(unique=True, db_index=True, help_text='An opaque look-up key to quickly locate this object.', blank=True, max_length=64, null=True)),
                ('title', models.CharField(max_length=200, help_text='The title for the trigger.')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('slug', models.SlugField(help_text='The URL slug for this trigger.')),
                ('description', models.TextField(help_text='Description text in Markdown.')),
                ('description_format', enum3field.EnumField(pledge.models.TextFormat, choices=[(pledge.models.TextFormat(0), 'HTML'), (pledge.models.TextFormat(1), 'Markdown')], help_text='The format of the description text.')),
                ('state', enum3field.EnumField(pledge.models.TriggerState, default=pledge.models.TriggerState(0), choices=[(pledge.models.TriggerState(0), 'Draft'), (pledge.models.TriggerState(1), 'Open'), (pledge.models.TriggerState(2), 'Paused'), (pledge.models.TriggerState(3), 'Executed'), (pledge.models.TriggerState(4), 'Vacated')], help_text='The current status of the trigger: Open (accepting pledges), Paused (not accepting pledges), Executed (funds distributed), Vacated (existing pledges invalidated).')),
                ('outcomes', jsonfield.fields.JSONField(default=[], help_text="An array of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].")),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, help_text='The user which created the trigger and can update it.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerExecution',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('cycle', models.IntegerField(help_text='The election cycle (year) that the trigger was executed in.')),
                ('description', models.TextField(help_text='Once a trigger is executed, additional text added to explain how funds were distributed.')),
                ('description_format', enum3field.EnumField(pledge.models.TextFormat, choices=[(pledge.models.TextFormat(0), 'HTML'), (pledge.models.TextFormat(1), 'Markdown')], help_text='The format of the description text.')),
                ('trigger', models.OneToOneField(help_text='The Trigger this execution information is about.', to='pledge.Trigger', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerStatusUpdate',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('text', models.TextField(help_text='Status update text in Markdown.')),
                ('text_format', enum3field.EnumField(pledge.models.TextFormat, choices=[(pledge.models.TextFormat(0), 'HTML'), (pledge.models.TextFormat(1), 'Markdown')], help_text='The format of the text.')),
                ('trigger', models.ForeignKey(to='pledge.Trigger', help_text='The Trigger that this update is about.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='pledge',
            name='trigger',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pledge.Trigger', help_text='The Trigger that this update is about.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, help_text='The user making the pledge.'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='pledge',
            unique_together=set([('trigger', 'user')]),
        ),
        migrations.AddField(
            model_name='contribution',
            name='pledge_execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pledge.PledgeExecution', help_text='The PledgeExecution this execution information is about.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='contribution',
            name='recipient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pledge.Campaign', help_text='The Campaign this contribution was sent to.'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contribution',
            unique_together=set([('pledge_execution', 'action')]),
        ),
        migrations.AddField(
            model_name='action',
            name='actor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pledge.Actor', help_text='The Actor who took this action.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pledge.TriggerExecution', help_text='The TriggerExecution that created this object.'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='action',
            unique_together=set([('execution', 'actor')]),
        ),
    ]
