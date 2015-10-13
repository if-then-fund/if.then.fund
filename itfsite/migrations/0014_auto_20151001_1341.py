# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0013_auto_20150922_1954'),
    ]

    operations = [
        migrations.AlterField(
            model_name='campaign',
            name='brand',
            field=models.IntegerField(help_text='Which multi-brand site does this campaign appear on.', choices=[(1, 'if.then.fund'), (2, '279forchange.us')]),
        ),
    ]
