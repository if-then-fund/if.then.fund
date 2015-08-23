# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0010_anonymoususer'),
        ('contrib', '0024_auto_20150821_1701'),
    ]

    operations = [
        migrations.AddField(
            model_name='cancelledpledge',
            name='anon_user',
            field=models.ForeignKey(to='itfsite.AnonymousUser', help_text='When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pledge',
            name='anon_user',
            field=models.ForeignKey(to='itfsite.AnonymousUser', help_text='When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.', blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='cancelledpledge',
            name='email',
            field=models.EmailField(blank=True, help_text='to be deleted', null=True, max_length=254),
        ),
        migrations.AlterField(
            model_name='pledge',
            name='email',
            field=models.EmailField(blank=True, help_text='to be removed.', null=True, max_length=254),
        ),
        migrations.AlterField(
            model_name='pledge',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored in an AnonymousUser object referenced in anon_user, and the pledge should be considered unconfirmed/provisional and will not be executed.", blank=True, on_delete=django.db.models.deletion.PROTECT, null=True),
        ),
        migrations.AlterField(
            model_name='triggerexecution',
            name='pledge_count',
            field=models.IntegerField(default=0, help_text='A cached count of the number of pledges executed. This counts pledges from anonymous users that do not result in contributions. Used to check when a Trigger is done executing.'),
        ),
        migrations.AlterUniqueTogether(
            name='pledge',
            unique_together=set([('trigger', 'anon_user'), ('trigger', 'user')]),
        ),
    ]
