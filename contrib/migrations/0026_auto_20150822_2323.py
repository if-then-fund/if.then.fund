# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0025_auto_20150822_2323'),
    ]

    operations = [
        migrations.RenameField(
            model_name='cancelledpledge',
            old_name='email',
            new_name='_email',
        ),
        migrations.RenameField(
            model_name='pledge',
            old_name='email',
            new_name='_email',
        ),
    ]
