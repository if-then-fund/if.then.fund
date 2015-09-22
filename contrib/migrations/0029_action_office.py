# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0028_auto_20150907_1821'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='office',
            field=models.CharField(max_length=7, null=True, help_text='A code specifying the office held by the Actor at the time the Action was created, in the same format as Recipient.office_sought.', blank=True, unique=True),
        ),
    ]
