# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='trigger',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, help_text='The user which created the trigger and can update it.', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='recipient',
            name='actor',
            field=models.ForeignKey(unique=True, to='contrib.Actor', help_text='The Actor that this recipient corresponds to (i.e. this Recipient is an incumbent).', blank=True, null=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='recipient',
            unique_together=set([('office_sought', 'party')]),
        ),
        migrations.AddField(
            model_name='pledgeexecution',
            name='pledge',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, help_text='The Pledge this execution information is about.', to='contrib.Pledge', related_name='execution'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledgeexecution',
            name='trigger_execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The TriggerExecution this execution information is about.', to='contrib.TriggerExecution', related_name='pledges'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='trigger',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Trigger that this Pledge is for.', to='contrib.Trigger', related_name='pledges'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pledge',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored, and the pledge should be considered unconfirmed/provisional and will not be executed.", null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='pledge',
            unique_together=set([('trigger', 'user'), ('trigger', 'email')]),
        ),
        migrations.AddField(
            model_name='contributionaggregate',
            name='trigger_execution',
            field=models.ForeignKey(help_text='The TriggerExecution that these cached statistics are about.', to='contrib.TriggerExecution', related_name='contribution_aggregates'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'outcome', 'district')]),
        ),
        migrations.AddField(
            model_name='contribution',
            name='action',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Action this contribution was made in reaction to.', to='contrib.Action'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='contribution',
            name='pledge_execution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The PledgeExecution this execution information is about.', to='contrib.PledgeExecution', related_name='contributions'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='contribution',
            name='recipient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Recipient this contribution was sent to.', to='contrib.Recipient', related_name='contributions'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='contribution',
            unique_together=set([('pledge_execution', 'action'), ('pledge_execution', 'recipient')]),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='trigger',
            field=models.ForeignKey(help_text='The Trigger that the pledge was for.', to='contrib.Trigger'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, help_text='The user who made the pledge, if not anonymous.', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='actor',
            name='challenger',
            field=models.OneToOneField(related_name='challenger_to', to='contrib.Recipient', help_text="The Recipient that contributions to this Actor's challenger go to. Independents don't have challengers because they have no opposing party.", blank=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='actor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, help_text='The Actor who took this action.', to='contrib.Actor'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='challenger',
            field=models.ForeignKey(to='contrib.Recipient', help_text="The Recipient that contributions to this Actor's challenger go to, at the time of the Action. Independents don't have challengers because they have no opposing party.", null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='action',
            name='execution',
            field=models.ForeignKey(help_text='The TriggerExecution that created this object.', to='contrib.TriggerExecution', related_name='actions'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='action',
            unique_together=set([('execution', 'actor')]),
        ),
    ]
