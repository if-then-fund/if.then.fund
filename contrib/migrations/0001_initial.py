# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion
import contrib.models
import jsonfield.fields
import enum3field


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('outcome', models.IntegerField(help_text='The outcome index that was taken.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Actor',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('key', models.CharField(db_index=True, unique=True, help_text='An opaque look-up key to quickly locate this object.', max_length=64)),
                ('name_long', models.CharField(help_text="The long form of the person's current name, meant for a page title.", max_length=128)),
                ('name_short', models.CharField(help_text="The short form of the person's current name, usually a last name, meant for in-page second references.", max_length=128)),
                ('name_sort', models.CharField(help_text="The sorted list form of the person's current name.", max_length=128)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('cycle', models.IntegerField(help_text='The election cycle (year) of the campaign.')),
                ('candidate', models.IntegerField(db_index=True, null=True, blank=True, help_text='For candidates that are not also Actors, a unique identifier for the candidate that spans Campaign objects (which are cycle-specific).')),
                ('name_long', models.CharField(help_text="The long form of the candidates's name during this campaign, meant for a page title.", max_length=128)),
                ('name_short', models.CharField(help_text="The short form of the candidates's name during this campaign, usually a last name, meant for in-page second references.", max_length=128)),
                ('name_sort', models.CharField(help_text="The sorted list form of the candidates's name during this campaign.", max_length=128)),
                ('party', models.CharField(help_text="Candidate's party during this campaign.", max_length=128)),
                ('fec_id', models.CharField(null=True, blank=True, help_text='The FEC ID of the campaign.', max_length=64)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('actor', models.ForeignKey(help_text='If the candidate of this campaign is an Actor, then the Actor.', blank=True, to='contrib.Actor', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('status', enum3field.EnumField(contrib.models.ContributionStatus, choices=[(contrib.models.ContributionStatus(1), 'Pending'), (contrib.models.ContributionStatus(2), 'Executed'), (contrib.models.ContributionStatus(3), 'Vacated'), (contrib.models.ContributionStatus(10), 'AbortedActorQuit'), (contrib.models.ContributionStatus(11), 'AbortedOverLimitTarget'), (contrib.models.ContributionStatus(12), 'AbortedOverLimitAll'), (contrib.models.ContributionStatus(13), 'AbortedUnopposed')], help_text='The status of the contribution: Pending (opponent not known), Executed, Vacated (no opponent exists)')),
                ('execution_time', models.DateTimeField(db_index=True, null=True, blank=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=6, help_text='The amount of the contribution, in dollars.')),
                ('is_opponent', models.BooleanField(default=False, help_text='Is the target the actor (False) or the general election opponent of the actor (True)?')),
                ('refunded_time', models.DateTimeField(null=True, blank=True, help_text='If the contribution was refunded to the user, the time that happened.')),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information about the contribution.')),
                ('action', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Action (including Actor) this contribution was triggered for.', to='contrib.Action')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Pledge',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('algorithm', models.IntegerField(default=0, help_text='In case we change our terms & conditions, or our explanation of how things work, an integer indicating the terms and expectations at the time the user made the pledge.')),
                ('desired_outcome', models.IntegerField(help_text='The outcome index that the user desires.')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=6, help_text='The pledge amount in dollars, not including fees.')),
                ('incumb_challgr', models.FloatField(help_text='A float indicating how to split the pledge: -1 (to challenger only) <=> 0 (evenly split between incumbends and challengers) <=> +1 (to incumbents only)')),
                ('filter_party', models.CharField(blank=True, help_text="A string containing one or more of the characters 'D' 'R' and 'I' that filters contributions to only candidates whose party matches on of the included characters.", max_length=3)),
                ('filter_competitive', models.BooleanField(default=False, help_text='Whether to filter contributions to competitive races.')),
                ('cancelled', models.BooleanField(default=False, help_text='True if the user cancels the pledge prior to execution.')),
                ('vacated', models.BooleanField(default=False, help_text='True if the Trigger is vacated.')),
                ('district', models.CharField(db_index=True, null=True, blank=True, help_text='The congressional district of the user (at the time of the pledge), if their address is in a congressional district.', max_length=64)),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PledgeExecution',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('charged', models.DecimalField(decimal_places=2, max_digits=6, help_text="The amount the user's account was actually charged, in dollars. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates, and it will include fees.")),
                ('fees', jsonfield.fields.JSONField(help_text='A dictionary representing all fees on the charge.')),
                ('contributions_executed', models.DecimalField(decimal_places=2, max_digits=6, help_text='The total amount of executed camapaign contributions to-date.')),
                ('contributions_pending', models.DecimalField(decimal_places=2, max_digits=6, help_text='The current total amount of pending camapaign contributions.')),
                ('pledge', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, help_text='The Pledge this execution information is about.', to='contrib.Pledge')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Trigger',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('key', models.CharField(db_index=True, unique=True, help_text='An opaque look-up key to quickly locate this object.', blank=True, null=True, max_length=64)),
                ('title', models.CharField(help_text='The title for the trigger.', max_length=200)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('slug', models.SlugField(help_text='The URL slug for this trigger.', max_length=200)),
                ('description', models.TextField(help_text='Description text in Markdown.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')], help_text='The format of the description text.')),
                ('state', enum3field.EnumField(contrib.models.TriggerState, choices=[(contrib.models.TriggerState(0), 'Draft'), (contrib.models.TriggerState(1), 'Open'), (contrib.models.TriggerState(2), 'Paused'), (contrib.models.TriggerState(3), 'Executed'), (contrib.models.TriggerState(4), 'Vacated')], default=contrib.models.TriggerState(0), help_text='The current status of the trigger: Open (accepting pledges), Paused (not accepting pledges), Executed (funds distributed), Vacated (existing pledges invalidated).')),
                ('outcomes', jsonfield.fields.JSONField(default=[], help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].")),
                ('strings', jsonfield.fields.JSONField(default={}, help_text='Display strings.')),
                ('extra', jsonfield.fields.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('total_pledged', models.DecimalField(decimal_places=2, max_digits=6, default=0, help_text='A cached total amount of pledges, i.e. prior to execution.')),
                ('total_contributions', models.DecimalField(decimal_places=2, max_digits=6, default=0, help_text='A cached total amount of campaign contributions executed (including pending contributions, but not vacated or aborted contributions).')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The user which created the trigger and can update it.', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerExecution',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('cycle', models.IntegerField(help_text='The election cycle (year) that the trigger was executed in.')),
                ('description', models.TextField(help_text='Once a trigger is executed, additional text added to explain how funds were distributed.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')], help_text='The format of the description text.')),
                ('trigger', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, help_text='The Trigger this execution information is about.', to='contrib.Trigger')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TriggerStatusUpdate',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
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
        migrations.AddField(
            model_name='pledge',
            name='trigger',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Trigger that this update is about.', to='contrib.Trigger'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The user making the pledge.', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='pledge',
            unique_together=set([('trigger', 'user')]),
        ),
        migrations.AddField(
            model_name='contribution',
            name='pledge_execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The PledgeExecution this execution information is about.', to='contrib.PledgeExecution'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='contribution',
            name='recipient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Campaign this contribution was sent to.', to='contrib.Campaign'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contribution',
            unique_together=set([('pledge_execution', 'action')]),
        ),
        migrations.AddField(
            model_name='action',
            name='actor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Actor who took this action.', to='contrib.Actor'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The TriggerExecution that created this object.', to='contrib.TriggerExecution'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='action',
            unique_together=set([('execution', 'actor')]),
        ),
    ]
