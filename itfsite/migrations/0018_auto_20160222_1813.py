# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import enum3field
import itfsite.utils


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0017_auto_20151203_1443'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='user',
            options={'permissions': (('see_user_emails', 'Can see the email addresses of our users'),)},
        ),
    ]
