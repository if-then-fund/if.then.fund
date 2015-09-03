# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0027_actor_votervoice_id'),
        ('letters', '0003_auto_20150829_1754'),
    ]

    operations = [
        migrations.AddField(
            model_name='letterscampaign',
            name='body_toggles_on',
            field=models.ForeignKey(to='contrib.Trigger', null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, help_text='Use alternate body text if the target has a known position on this issue, based on a TriggerExecution.'),
        ),
        migrations.AddField(
            model_name='letterscampaign',
            name='message_body0',
            field=models.TextField(null=True, blank=True, help_text='The body of the message, as in message_body, for when the target has outcome 0 in the body_toggles_on trigger.'),
        ),
        migrations.AddField(
            model_name='letterscampaign',
            name='message_body1',
            field=models.TextField(null=True, blank=True, help_text='The body of the message, as in message_body, for when the target has outcome 1 in the body_toggles_on trigger.'),
        ),
        migrations.AddField(
            model_name='letterscampaign',
            name='message_subject0',
            field=models.CharField(null=True, blank=True, max_length=100, help_text='The subject of the message, as in message_subject, for when the target has outcome 0 in the body_toggles_on trigger.'),
        ),
        migrations.AddField(
            model_name='letterscampaign',
            name='message_subject1',
            field=models.CharField(null=True, blank=True, max_length=100, help_text='The subject of the message, as in message_subject, for when the target has outcome 1 in the body_toggles_on trigger.'),
        ),
    ]
