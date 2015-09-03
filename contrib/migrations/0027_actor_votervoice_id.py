# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0026_auto_20150822_2323'),
    ]

    operations = [
        migrations.AddField(
            model_name='actor',
            name='votervoice_id',
            field=models.IntegerField(help_text="VoterVoice's target ID for this person.", null=True, blank=True, unique=True),
        ),
    ]
