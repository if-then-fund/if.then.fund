# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0011_auto_20150423_1051'),
    ]

    operations = [
        migrations.AddField(
            model_name='contributionaggregate',
            name='actor',
            field=models.ForeignKey(to='contrib.Actor', null=True, help_text='The Actor who caused the Action that the contribution was made about. The contribution may have gone to an opponent.', blank=True),
        ),
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'via', 'outcome', 'action', 'actor', 'incumbent', 'party', 'district')]),
        ),
    ]
