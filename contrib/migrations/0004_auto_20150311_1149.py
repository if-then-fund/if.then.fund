# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0003_pledge_email_confirmed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='actor',
            name='inactive_reason',
            field=models.CharField(help_text="If the Actor is still a public official (i.e. generates Actions) but should not get contributions, the reason why. If not None, serves as a flag. E.g. 'Not running for reelection.'.", null=True, blank=True, max_length=200),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='actor',
            name='challenger',
            field=models.OneToOneField(help_text="The *current* Recipient that contributions to this Actor's challenger go to. Independents don't have challengers because they have no opposing party.", null=True, related_name='challenger_to', to='contrib.Recipient', blank=True),
            preserve_default=True,
        ),
    ]
