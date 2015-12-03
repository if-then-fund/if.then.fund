# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0016_auto_20151202_1346'),
    ]

    operations = [
        migrations.AlterField(
            model_name='campaign',
            name='brand',
            field=models.IntegerField(default=1, help_text='Which multi-brand site does this campaign appear on.', choices=[(1, 'if.then.fund'), (2, '279forchange.us')]),
        ),
        migrations.AlterField(
            model_name='campaign',
            name='og_image',
            field=models.ImageField(null=True, help_text="The og:image (for Facebook and Twitter posts) for the campaign. At least 120px x 120px and must be square. If not set and the campaign has an owner, then the owner's og:image is used.", upload_to='campaign-media', blank=True),
        ),
        migrations.AlterField(
            model_name='campaign',
            name='splash_image',
            field=models.ImageField(null=True, help_text='The big image to display behind the main call to action. Should be about 1300px wide and at least 500px tall, but the image will be resized and cropped as necessary.', upload_to='campaign-media', blank=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='banner_image',
            field=models.ImageField(null=True, help_text="This organization's banner image. Should be about 1300px wide and at least 500px tall, but the image will be resized and cropped as necessary.", upload_to='org-banner-image', blank=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='og_image',
            field=models.ImageField(null=True, help_text="The og:image (for Facebook and Twitter posts) for the organization's profile page and the default og:image for the organization's campaigns. At least 120px x 120px and must be square.", upload_to='campaign-media', blank=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='profile_image',
            field=models.ImageField(null=True, help_text="The logo or headshot to display as the profile picture on the organization's page, and the default og:image (for Facebook and Twitter posts) if og_image is not provided. At least 120px x 120px and must be square.", upload_to='campaign-media', blank=True),
        ),
    ]
