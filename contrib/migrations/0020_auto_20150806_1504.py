# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0019_triggerrecommendation'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'via', 'outcome', 'actor', 'incumbent', 'party', 'district')]),
        ),
        migrations.RemoveField(
            model_name='contributionaggregate',
            name='action',
        ),
    ]
