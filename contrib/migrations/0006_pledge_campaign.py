# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0005_incompletepledge'),
    ]

    operations = [
        migrations.AddField(
            model_name='pledge',
            name='campaign',
            field=models.CharField(null=True, max_length=24, blank=True, help_text='An optional string indicating a referral campaign that lead the user to take this action.', db_index=True),
            preserve_default=True,
        ),
    ]
