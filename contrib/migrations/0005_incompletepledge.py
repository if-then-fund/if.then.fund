# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0004_auto_20150311_1149'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncompletePledge',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('email', models.EmailField(db_index=True, max_length=254, help_text='An email address.')),
                ('extra', contrib.models.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('sent_followup_at', models.DateTimeField(blank=True, db_index=True, help_text="If we've sent a follow-up email, the date and time we sent it.", null=True)),
                ('completed_pledge', models.ForeignKey(null=True, help_text='If the user came back and finished a Pledge, that pledge.', to='contrib.Pledge', blank=True)),
                ('trigger', models.ForeignKey(to='contrib.Trigger', help_text='The Trigger that the pledge was for.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
