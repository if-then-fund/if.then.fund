# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0032_auto_20151026_1030'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='contributionaggregate',
            name='actor',
        ),
        migrations.RemoveField(
            model_name='contributionaggregate',
            name='trigger_execution',
        ),
        migrations.RemoveField(
            model_name='contributionaggregate',
            name='via_campaign',
        ),
        migrations.DeleteModel(
            name='ContributionAggregate',
        ),
    ]
