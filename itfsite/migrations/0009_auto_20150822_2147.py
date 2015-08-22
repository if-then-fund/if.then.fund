# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0008_campaign_letters'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='og_image',
            field=models.ImageField(upload_to='campaign-media', null=True, blank=True, help_text="The og:image to display for the organization's page and the default og:image for the organization's campaigns."),
        ),
        migrations.AddField(
            model_name='organization',
            name='profile_image',
            field=models.ImageField(upload_to='campaign-media', null=True, blank=True, help_text="The square 'profile image' to display on the organization's page, and the default image for og_image."),
        ),
    ]
