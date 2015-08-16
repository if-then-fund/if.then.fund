# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0020_auto_20150806_1504'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pledge',
            old_name='campaign',
            new_name='ref_code'),
        migrations.AlterField(
            model_name='pledge',
            name='ref_code',
            field=models.CharField(blank=True, help_text='An optional referral code that lead the user to take this action.', max_length=24, null=True, db_index=True),
        ),
    ]
