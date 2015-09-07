# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0011_campaign_brand'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='de_recip_id',
            field=models.CharField(blank=True, help_text='The recipient ID on Democracy Engine for taking tips.', max_length=64, unique=True, null=True),
        ),
    ]
