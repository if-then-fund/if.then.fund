# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trigger',
            name='description',
            field=models.TextField(help_text='Description text in the format given by description_format.'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='triggerstatusupdate',
            name='text',
            field=models.TextField(help_text='Status update text in the format given by text_format.'),
            preserve_default=True,
        ),
    ]
