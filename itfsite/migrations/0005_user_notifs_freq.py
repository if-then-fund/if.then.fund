# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import enum3field
import itfsite.accounts


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0004_auto_20150612_1643'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='notifs_freq',
            field=enum3field.EnumField(itfsite.accounts.NotificationsFrequency, choices=[(itfsite.accounts.NotificationsFrequency(0), 'NoNotifications'), (itfsite.accounts.NotificationsFrequency(1), 'DailyNotifications'), (itfsite.accounts.NotificationsFrequency(2), 'WeeklyNotifications')], default=itfsite.accounts.NotificationsFrequency(1), help_text='Now often the user wants to get non-obligatory notifications.'),
        ),
    ]
