# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0010_anonymoususer'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='brand',
            field=models.IntegerField(choices=[(1, 'if.then.fund')], help_text='Which multi-brand site does this campaign appear on.', default=0),
            preserve_default=False,
        ),
    ]
