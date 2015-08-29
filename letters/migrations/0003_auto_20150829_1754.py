# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('letters', '0002_auto_20150822_2320'),
    ]

    operations = [
        migrations.AddField(
            model_name='letterscampaign',
            name='message_body',
            field=models.TextField(help_text='The body of the message sent to legislators. Rendered as if Markdown when previewing for users.', default='Sample Body'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='letterscampaign',
            name='message_subject',
            field=models.CharField(max_length=100, help_text='The subject of the message. Used in message delivery.', default='Sample Subject'),
            preserve_default=False,
        ),
    ]
