# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import enum3field
import itfsite.utils


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0014_auto_20151001_1341'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='image_credit',
            field=models.TextField(blank=True, help_text='Image credit, in the same format as the subhead.', null=True),
        ),
        migrations.AlterField(
            model_name='campaign',
            name='subhead_format',
            field=enum3field.EnumField(itfsite.utils.TextFormat, choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')], help_text='The format of the subhead and image_credit text.'),
        ),
    ]
