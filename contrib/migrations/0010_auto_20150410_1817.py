# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import contrib.models
import enum3field


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0003_organization'),
        ('contrib', '0009_auto_20150410_1331'),
    ]

    operations = [
        migrations.CreateModel(
            name='TriggerCustomization',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('title', models.CharField(max_length=200, help_text='The customized title for the trigger.')),
                ('slug', models.SlugField(max_length=200, help_text='The customized URL slug for this trigger.')),
                ('visible', models.BooleanField(default=False, help_text='Whether this TriggerCustomization can be seen by non-admins.')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('description', models.TextField(help_text='Description text in the format given by description_format.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, help_text='The format of the description text.', choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')])),
                ('outcome', models.IntegerField(null=True, help_text='Restrict Pledges to this outcome index.', blank=True)),
                ('incumb_challgr', models.FloatField(null=True, help_text='Restrict Pledges to this incumb_challgr value.', blank=True)),
                ('filter_party', enum3field.EnumField(contrib.models.ActorParty, null=True, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], help_text='Restrict Pledges to this party.', blank=True)),
                ('filter_competitive', models.NullBooleanField(default=False, help_text='Restrict Pledges to this filter_competitive value.')),
                ('extra', contrib.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('pledge_count', models.IntegerField(help_text='A cached count of the number of pledges made.', default=0)),
                ('total_pledged', models.DecimalField(db_index=True, max_digits=6, decimal_places=2, help_text='A cached total amount of pledges, i.e. prior to execution.', default=0)),
                ('owner', models.ForeignKey(help_text='The user/organization which created the TriggerCustomization.', to='itfsite.Organization', related_name='triggers')),
            ],
        ),
        migrations.AddField(
            model_name='trigger',
            name='execution_note',
            field=models.TextField(help_text='Explanatory note about how this Trigger will be executed, in the format given by execution_note_format.', default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='trigger',
            name='execution_note_format',
            field=enum3field.EnumField(contrib.models.TextFormat, default=0, help_text='The format of the execution_note text.', choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')]),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='trigger',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, null=True, help_text='The user/organization which created the trigger and can update it. Empty for Triggers created by us.', blank=True, to='itfsite.Organization'),
        ),
        migrations.AddField(
            model_name='triggercustomization',
            name='trigger',
            field=models.ForeignKey(help_text='The Trigger that this TriggerCustomization customizes.', to='contrib.Trigger', related_name='customizations'),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='via',
            field=models.ForeignKey(null=True, help_text='The TriggerCustomization that this Pledge was made via.', blank=True, to='contrib.TriggerCustomization'),
        ),
        migrations.AddField(
            model_name='contributionaggregate',
            name='via',
            field=models.ForeignKey(null=True, help_text='The TriggerCustomization that the Pledges were made via.', blank=True, to='contrib.TriggerCustomization'),
        ),
        migrations.AddField(
            model_name='incompletepledge',
            name='via',
            field=models.ForeignKey(null=True, help_text='The TriggerCustomization that this Pledge was made via.', blank=True, to='contrib.TriggerCustomization'),
        ),
        migrations.AddField(
            model_name='pledge',
            name='via',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, null=True, help_text='The TriggerCustomization that this Pledge was made via.', blank=True, related_name='pledges', to='contrib.TriggerCustomization'),
        ),
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'via', 'outcome', 'action', 'incumbent', 'party', 'district')]),
        ),
    ]
