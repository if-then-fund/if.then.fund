# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('letters', '0001_initial'),
        ('itfsite', '0007_campaign'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='letters',
            field=models.ManyToManyField(blank=True, related_name='campaigns', to='letters.LettersCampaign', help_text='LettersCampaigns to offer the user to take action on (or to show past actions).'),
        ),
    ]
