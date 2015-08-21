# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0023_auto_20150816_1850'),
    ]

    operations = [
        migrations.AddField(
            model_name='actor',
            name='office',
            field=models.CharField(null=True, help_text='A code specifying the office currently held by the Actor, in the same format as Recipient.office_sought.', blank=True, max_length=7, unique=True),
        ),
        migrations.AlterField(
            model_name='recipient',
            name='office_sought',
            field=models.CharField(null=True, db_index=True, help_text="For challengers, a code specifying the office sought in the form of 'S-NY-I' (New York class 1 senate seat) or 'H-TX-30' (Texas 30th congressional district). Unique with party.", blank=True, max_length=7),
        ),
    ]
