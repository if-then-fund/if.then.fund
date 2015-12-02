# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import itfsite.utils
import enum3field


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0015_auto_20151013_2120'),
    ]

    operations = [
        migrations.AlterField(
            model_name='campaign',
            name='body_format',
            field=enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the body_text field.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')], default=itfsite.utils.TextFormat(1)),
        ),
        migrations.AlterField(
            model_name='campaign',
            name='subhead_format',
            field=enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the subhead and image_credit text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')], default=itfsite.utils.TextFormat(1)),
        ),
    ]
