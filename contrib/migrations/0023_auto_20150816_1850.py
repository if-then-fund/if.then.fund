# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0007_campaign'),
        ('contrib', '0022_auto_20150816_1546'),
    ]

    operations = [
        migrations.AddField(
            model_name='contributionaggregate',
            name='via_campaign',
            field=models.ForeignKey(help_text='The Campaign that the Pledges were made via.', to='itfsite.Campaign', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='incompletepledge',
            name='via_campaign',
            field=models.ForeignKey(help_text='The Campaign that this Pledge was made via.', to='itfsite.Campaign', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pledge',
            name='via_campaign',
            field=models.ForeignKey(related_name='pledges', help_text='The Campaign that this Pledge was made via.', to='itfsite.Campaign', on_delete=django.db.models.deletion.PROTECT, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='cancelledpledge',
            name='via_campaign',
            field=models.ForeignKey(help_text='The Campaign that this Pledge was made via.', to='itfsite.Campaign', blank=True, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='contributionaggregate',
            unique_together=set([('trigger_execution', 'via_campaign', 'outcome', 'actor', 'incumbent', 'party', 'district')]),
        ),
        migrations.AlterUniqueTogether(
            name='triggercustomization',
            unique_together=set([('trigger', 'owner')]),
        ),
        migrations.AlterIndexTogether(
            name='pledge',
            index_together=set([('trigger', 'via_campaign')]),
        ),
        migrations.RemoveField(
            model_name='contributionaggregate',
            name='via',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='description',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='description_format',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='pledge_count',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='slug',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='subhead',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='subhead_format',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='title',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='total_pledged',
        ),
        migrations.RemoveField(
            model_name='triggercustomization',
            name='visible',
        ),
    ]
