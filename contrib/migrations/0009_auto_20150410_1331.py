# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import enum3field
import contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0008_contributorinfo'),
    ]

    operations = [
        migrations.AddField(
            model_name='contributionaggregate',
            name='action',
            field=models.ForeignKey(help_text='The Action that the contribution was made about.', blank=True, null=True, to='contrib.Action'),
        ),
        migrations.AddField(
            model_name='contributionaggregate',
            name='count',
            field=models.IntegerField(help_text='A cached total count of campaign contributions executed in this slice.', default=0),
        ),
        migrations.AddField(
            model_name='contributionaggregate',
            name='incumbent',
            field=models.NullBooleanField(help_text="Whether the contribution was to the Actor (True) or the Actor's challenger (False)."),
        ),
        migrations.AddField(
            model_name='contributionaggregate',
            name='party',
            field=enum3field.EnumField(contrib.models.ActorParty, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], help_text='The party of the Recipient.', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='contributionaggregate',
            name='total',
            field=models.DecimalField(max_digits=6, help_text='A cached total dollar amount of campaign contributions executed in this slice, excluding fees.', default=0, decimal_places=2),
        ),
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'outcome', 'action', 'incumbent', 'party', 'district')]),
        ),
    ]
