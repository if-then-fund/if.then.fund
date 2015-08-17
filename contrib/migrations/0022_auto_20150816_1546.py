# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0006_organization_banner_image'),
        ('contrib', '0021_campaign_refcode_20150816_1320'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cancelledpledge',
            name='via',
        ),
        migrations.RemoveField(
            model_name='incompletepledge',
            name='via',
        ),
        migrations.RemoveField(
            model_name='pledge',
            name='via',
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='via_campaign',
            field=models.ForeignKey(null=True, help_text='The Campaign that this Pledge was made via.', to='itfsite.Organization', blank=True),
        ),
    ]
