# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0029_action_office'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='office',
            field=models.CharField(help_text='A code specifying the office held by the Actor at the time the Action was created, in the same format as Recipient.office_sought.', max_length=7, null=True, blank=True),
        ),
    ]
