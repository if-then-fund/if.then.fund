# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import enum3field
import contrib.models
import itfsite.utils


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0033_auto_20151128_0015'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trigger',
            name='description_format',
            field=enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the description text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')], default=itfsite.utils.TextFormat(1)),
        ),
        migrations.AlterField(
            model_name='trigger',
            name='execution_note',
            field=models.TextField(help_text='Explanatory note about how this Trigger will be executed, in the format given by execution_note_format.', default='n/a'),
        ),
        migrations.AlterField(
            model_name='trigger',
            name='execution_note_format',
            field=enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the execution_note text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')], default=itfsite.utils.TextFormat(1)),
        ),
        migrations.AlterField(
            model_name='trigger',
            name='outcomes',
            field=itfsite.utils.JSONField(help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].", default='[{"vote_key": "+", "label": "Yes on This Vote", "object": "in favor of the bill"}, {"vote_key": "-", "label": "No on This Vote", "object": "against passage of the bill"}]'),
        ),
        migrations.AlterField(
            model_name='trigger',
            name='title',
            field=models.CharField(max_length=200, help_text='The legislative action that this trigger is about, in wonky language.'),
        ),
        migrations.AlterField(
            model_name='triggercustomization',
            name='filter_competitive',
            field=models.NullBooleanField(help_text='Restrict Pledges to this filter_competitive value.', default=False, verbose_name='Restrict Competitive Filter'),
        ),
        migrations.AlterField(
            model_name='triggercustomization',
            name='filter_party',
            field=enum3field.EnumField(contrib.models.ActorParty, blank=True, null=True, choices=[(contrib.models.ActorParty(1), 'Democratic'), (contrib.models.ActorParty(2), 'Republican'), (contrib.models.ActorParty(3), 'Independent')], help_text='Restrict Pledges to be to candidates of this party.', verbose_name='Restrict Party'),
        ),
        migrations.AlterField(
            model_name='triggercustomization',
            name='incumb_challgr',
            field=models.FloatField(blank=True, null=True, verbose_name='Restrict Incumbent-Challenger Choice', help_text="Restrict Pledges to be for just incumbents, just challengers, both incumbents and challengers (where user can't pick), or don't restrict the user's choice."),
        ),
        migrations.AlterField(
            model_name='triggercustomization',
            name='outcome',
            field=models.IntegerField(blank=True, null=True, verbose_name='Restrict Outcome', help_text='Restrict Pledges to this outcome.'),
        ),
    ]
