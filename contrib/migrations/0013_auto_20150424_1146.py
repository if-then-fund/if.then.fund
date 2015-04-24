# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0012_auto_20150424_1132'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contributionaggregate',
            name='trigger_execution',
            field=models.ForeignKey(blank=True, related_name='contribution_aggregates', null=True, to='contrib.TriggerExecution', help_text='The TriggerExecution that these cached statistics are about.'),
        ),
    ]
