# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0010_anonymoususer'),
        ('letters', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userletter',
            name='anon_user',
            field=models.ForeignKey(help_text='When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.', blank=True, to='itfsite.AnonymousUser', null=True),
        ),
        migrations.AlterUniqueTogether(
            name='userletter',
            unique_together=set([('letterscampaign', 'user'), ('letterscampaign', 'anon_user')]),
        ),
        migrations.RemoveField(
            model_name='userletter',
            name='email',
        ),
    ]
