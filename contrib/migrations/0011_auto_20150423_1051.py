# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0010_auto_20150410_1817'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recipient',
            name='actor',
            field=models.OneToOneField(null=True, to='contrib.Actor', help_text='The Actor that this recipient corresponds to (i.e. this Recipient is an incumbent).', blank=True),
        ),
    ]
