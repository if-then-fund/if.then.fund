# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0006_pledge_campaign'),
    ]

    operations = [
        migrations.AddField(
            model_name='pledge',
            name='made_after_trigger_execution',
            field=models.BooleanField(default=False, help_text='Whether this Pledge was created after the Trigger was executed (i.e. outcomes known).'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='trigger',
            name='pledge_count',
            field=models.IntegerField(help_text='A cached count of the number of pledges made *prior* to trigger execution (excludes Pledges with made_after_trigger_execution).', default=0),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='trigger',
            name='total_pledged',
            field=models.DecimalField(max_digits=6, decimal_places=2, db_index=True, help_text='A cached total amount of pledges made *prior* to trigger execution (excludes Pledges with made_after_trigger_execution).', default=0),
            preserve_default=True,
        ),
    ]
