# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import itfsite.utils


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0036_auto_20160318_0906'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trigger',
            name='description',
            field=models.TextField(help_text='Describe what event will cause contributions to be made. Use the second person, future tense, and a conditional if appropriate, e.g. by starting with "Your donation will be made if...". Once a trigger is executed, this text is not used and the TriggerExecution description is used instead. The text is in the format given by description_format.'),
        ),
        migrations.AlterField(
            model_name='triggerexecution',
            name='description',
            field=models.TextField(help_text='Describe how contributions are being distributed. Use the passive voice and present progressive tense, e.g. by starting with "Donations are being distributed...".'),
        ),
    ]
