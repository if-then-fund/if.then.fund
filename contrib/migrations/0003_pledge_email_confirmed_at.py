# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0002_auto_20150119_1852'),
    ]

    operations = [
        migrations.AddField(
            model_name='pledge',
            name='email_confirmed_at',
            field=models.DateTimeField(help_text='The date and time that the email address of the pledge became confirmed, if the pledge was originally based on an unconfirmed email address.', null=True, blank=True),
            preserve_default=True,
        ),
    ]
