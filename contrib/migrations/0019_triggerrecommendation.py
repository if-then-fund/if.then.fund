# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0018_contributorinfo_is_geocoded'),
    ]

    operations = [
        migrations.CreateModel(
            name='TriggerRecommendation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('symmetric', models.BooleanField(default=False, help_text='If true, the recommendation goes both ways.')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('notifications_created', models.BooleanField(db_index=True, default=False, help_text='Set to true once notifications have been generated for users for any past actions the users took before this recommendation was added.')),
                ('trigger1', models.ForeignKey(related_name='recommends', to='contrib.Trigger', help_text='If a user has taken action on this Trigger, then we send them a notification.')),
                ('trigger2', models.ForeignKey(related_name='recommended_by', to='contrib.Trigger', help_text='This is the trigger that we recommend the user take action on.')),
            ],
        ),
    ]
