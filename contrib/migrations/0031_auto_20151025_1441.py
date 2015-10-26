# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0030_auto_20150922_1541'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='trigger',
            name='slug',
        ),
        migrations.RemoveField(
            model_name='trigger',
            name='subhead',
        ),
        migrations.RemoveField(
            model_name='trigger',
            name='subhead_format',
        ),
    ]
