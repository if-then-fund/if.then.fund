# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0012_organization_de_recip_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='campaign',
            name='brand',
            field=models.IntegerField(choices=[(1, 'if.then.fund'), (2, '279project.xyz')], help_text='Which multi-brand site does this campaign appear on.'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='de_recip_id',
            field=models.CharField(null=True, blank=True, max_length=64, help_text='The recipient ID on Democracy Engine for taking tips.'),
        ),
    ]
