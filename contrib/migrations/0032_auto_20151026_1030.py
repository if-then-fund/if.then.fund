# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0031_auto_20151025_1441'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cancelledpledge',
            name='_email',
        ),
        migrations.RemoveField(
            model_name='pledge',
            name='_email',
        ),
    ]
