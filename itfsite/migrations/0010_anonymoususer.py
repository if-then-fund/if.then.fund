# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import itfsite.utils
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0009_auto_20150822_2147'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnonymousUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('email', models.EmailField(db_index=True, null=True, max_length=254, blank=True)),
                ('sentConfirmationEmail', models.BooleanField(default=False, help_text='Have we sent this user an email to confirm their address and activate their account/actions?')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('confirmed_user', models.ForeignKey(help_text='The user that this record became confirmed as.', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
    ]
