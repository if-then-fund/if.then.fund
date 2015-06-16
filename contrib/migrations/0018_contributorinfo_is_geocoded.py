# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0015_auto_20150608_1725'),
    ]

    operations = [
        migrations.AddField(
            model_name='contributorinfo',
            name='is_geocoded',
            field=models.BooleanField(default=False, help_text='Whether this record has been geocoded.', db_index=True),
        ),
    ]
