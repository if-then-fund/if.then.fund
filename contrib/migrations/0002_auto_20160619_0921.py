# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('itfsite', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='triggercustomization',
            name='owner',
            field=models.ForeignKey(to='itfsite.Organization', related_name='triggers', help_text='The user/organization which created the TriggerCustomization.'),
        ),
        migrations.AddField(
            model_name='triggercustomization',
            name='trigger',
            field=models.ForeignKey(to='contrib.Trigger', related_name='customizations', help_text='The Trigger that this TriggerCustomization customizes.'),
        ),
        migrations.AddField(
            model_name='trigger',
            name='owner',
            field=models.ForeignKey(null=True, to='itfsite.Organization', help_text='The user/organization which created the trigger and can update it. Empty for Triggers created by us.', blank=True, on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='trigger',
            name='trigger_type',
            field=models.ForeignKey(to='contrib.TriggerType', help_text='The type of the trigger, which determines how it is described in text.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='tip',
            name='profile',
            field=models.ForeignKey(to='contrib.ContributorInfo', related_name='tips', help_text='The contributor information (name, address, etc.) and billing information used for this Tip.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='tip',
            name='recipient',
            field=models.ForeignKey(to='itfsite.Organization', help_text='The recipient of the tip.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='tip',
            name='user',
            field=models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, help_text='The user making the Tip.', blank=True, on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='tip',
            name='via_campaign',
            field=models.ForeignKey(null=True, to='itfsite.Campaign', related_name='tips', help_text='The Campaign that this Tip was made via.', blank=True, on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='tip',
            name='via_pledge',
            field=models.OneToOneField(null=True, to='contrib.Pledge', related_name='tip', on_delete=django.db.models.deletion.PROTECT, blank=True, help_text='The executed Pledge that this Tip was made via.'),
        ),
        migrations.AddField(
            model_name='recipient',
            name='actor',
            field=models.OneToOneField(null=True, to='contrib.Actor', blank=True, help_text='The Actor that this recipient corresponds to (i.e. this Recipient is an incumbent).'),
        ),
        migrations.AddField(
            model_name='pledgeexecution',
            name='pledge',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='contrib.Pledge', related_name='execution', help_text='The Pledge this execution information is about.'),
        ),
        migrations.AddField(
            model_name='pledgeexecution',
            name='trigger_execution',
            field=models.ForeignKey(to='contrib.TriggerExecution', related_name='pledges', help_text='The TriggerExecution this execution information is about.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='pledge',
            name='anon_user',
            field=models.ForeignKey(null=True, to='itfsite.AnonymousUser', help_text='When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.', blank=True),
        ),
        migrations.AddField(
            model_name='pledge',
            name='profile',
            field=models.ForeignKey(to='contrib.ContributorInfo', related_name='pledges', help_text='The contributor information (name, address, etc.) and billing information used for this Pledge. Immutable and cannot be changed after execution.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='pledge',
            name='trigger',
            field=models.ForeignKey(to='contrib.Trigger', related_name='pledges', help_text='The Trigger that this Pledge is for.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='pledge',
            name='user',
            field=models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, help_text="The user making the pledge. When an anonymous user makes a pledge, this is null, the user's email address is stored in an AnonymousUser object referenced in anon_user, and the pledge should be considered unconfirmed/provisional and will not be executed.", blank=True, on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='pledge',
            name='via_campaign',
            field=models.ForeignKey(null=True, to='itfsite.Campaign', related_name='pledges', help_text='The Campaign that this Pledge was made via.', blank=True, on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='incompletepledge',
            name='completed_pledge',
            field=models.ForeignKey(null=True, to='contrib.Pledge', help_text='If the user came back and finished a Pledge, that pledge.', blank=True),
        ),
        migrations.AddField(
            model_name='incompletepledge',
            name='trigger',
            field=models.ForeignKey(help_text='The Trigger that the pledge was for.', to='contrib.Trigger'),
        ),
        migrations.AddField(
            model_name='incompletepledge',
            name='via_campaign',
            field=models.ForeignKey(null=True, to='itfsite.Campaign', help_text='The Campaign that this Pledge was made via.', blank=True),
        ),
        migrations.AddField(
            model_name='contribution',
            name='action',
            field=models.ForeignKey(to='contrib.Action', help_text='The Action this contribution was made in reaction to.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='contribution',
            name='pledge_execution',
            field=models.ForeignKey(to='contrib.PledgeExecution', related_name='contributions', help_text='The PledgeExecution this execution information is about.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='contribution',
            name='recipient',
            field=models.ForeignKey(to='contrib.Recipient', related_name='contributions', help_text='The Recipient this contribution was sent to.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='anon_user',
            field=models.ForeignKey(null=True, to='itfsite.AnonymousUser', help_text='When an anonymous user makes a pledge, a one-off object is stored here and we send a confirmation email.', blank=True),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='trigger',
            field=models.ForeignKey(help_text='The Trigger that the pledge was for.', to='contrib.Trigger'),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='user',
            field=models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, help_text='The user who made the pledge, if not anonymous.', blank=True),
        ),
        migrations.AddField(
            model_name='cancelledpledge',
            name='via_campaign',
            field=models.ForeignKey(null=True, to='itfsite.Campaign', help_text='The Campaign that this Pledge was made via.', blank=True),
        ),
        migrations.AddField(
            model_name='actor',
            name='challenger',
            field=models.OneToOneField(null=True, to='contrib.Recipient', related_name='challenger_to', blank=True, help_text="The *current* Recipient that contributions to this Actor's challenger go to. Independents don't have challengers because they have no opposing party."),
        ),
        migrations.AddField(
            model_name='action',
            name='actor',
            field=models.ForeignKey(to='contrib.Actor', help_text='The Actor who took this action.', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='action',
            name='challenger',
            field=models.ForeignKey(null=True, to='contrib.Recipient', help_text="The Recipient that contributions to this Actor's challenger go to, at the time of the Action. Independents don't have challengers because they have no opposing party.", blank=True),
        ),
        migrations.AddField(
            model_name='action',
            name='execution',
            field=models.ForeignKey(to='contrib.TriggerExecution', related_name='actions', help_text='The TriggerExecution that created this object.'),
        ),
        migrations.AlterUniqueTogether(
            name='triggercustomization',
            unique_together=set([('trigger', 'owner')]),
        ),
        migrations.AlterUniqueTogether(
            name='recipient',
            unique_together=set([('office_sought', 'party')]),
        ),
        migrations.AlterUniqueTogether(
            name='pledge',
            unique_together=set([('trigger', 'user'), ('trigger', 'anon_user')]),
        ),
        migrations.AlterIndexTogether(
            name='pledge',
            index_together=set([('trigger', 'via_campaign')]),
        ),
        migrations.AlterUniqueTogether(
            name='contribution',
            unique_together=set([('pledge_execution', 'action'), ('pledge_execution', 'recipient')]),
        ),
        migrations.AlterUniqueTogether(
            name='action',
            unique_together=set([('execution', 'actor')]),
        ),
    ]
