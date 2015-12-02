# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0034_auto_20151128_1747'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='trigger',
            name='execution_note',
        ),
        migrations.RemoveField(
            model_name='trigger',
            name='execution_note_format',
        ),
        migrations.AlterField(
            model_name='trigger',
            name='description',
            field=models.TextField(help_text='Describe what event will cause (or caused) contributions to be made. The text in the format given by description_format.'),
        ),
    ]
