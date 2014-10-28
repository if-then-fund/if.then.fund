# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('pledge', '0002_auto_20141028_1508'),
    ]

    operations = [
        migrations.AddField(
            model_name='trigger',
            name='strings',
            field=jsonfield.fields.JSONField(help_text='Display strings.', default={}),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='trigger',
            name='outcomes',
            field=jsonfield.fields.JSONField(help_text="An array (order matters!) of information for each possible outcome of the trigger, e.g. ['Voted Yes', 'Voted No'].", default=[]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='trigger',
            name='slug',
            field=models.SlugField(help_text='The URL slug for this trigger.', max_length=200),
            preserve_default=True,
        ),
    ]
