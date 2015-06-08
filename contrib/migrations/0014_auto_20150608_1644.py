# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import contrib.models
import enum3field


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0013_auto_20150424_1146'),
    ]

    operations = [
        migrations.AddField(
            model_name='trigger',
            name='subhead',
            field=models.TextField(help_text='Short sub-heading text in the format given by description_format.', default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='trigger',
            name='subhead_format',
            field=enum3field.EnumField(contrib.models.TextFormat, help_text='The format of the subhead text.', choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')], default=0),
            preserve_default=False,
        ),
    ]
