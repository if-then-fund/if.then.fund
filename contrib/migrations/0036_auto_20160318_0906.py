# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0035_auto_20151202_1346'),
    ]

    operations = [
        migrations.AlterField(
            model_name='incompletepledge',
            name='email',
            field=models.EmailField(db_index=True, max_length=254, unique=True, help_text='An email address.'),
        ),
    ]
