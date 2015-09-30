# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('letters', '0004_auto_20150903_1813'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userletter',
            name='submitted',
        ),
        migrations.AddField(
            model_name='userletter',
            name='delivered',
            field=models.IntegerField(default=0, help_text='The number of messages that have been submitted for delivery.'),
        ),
        migrations.AddField(
            model_name='userletter',
            name='pending',
            field=models.IntegerField(default=0, help_text='The number of messages pending submission.'),
        ),
    ]
