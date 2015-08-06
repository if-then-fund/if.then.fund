# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0005_user_notifs_freq'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='banner_image',
            field=models.ImageField(null=True, blank=True, help_text="A raw image to display for this organization's banner image.", upload_to='org-banner-image'),
        ),
    ]
