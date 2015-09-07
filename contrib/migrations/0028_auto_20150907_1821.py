# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from decimal import Decimal
import itfsite.utils
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0012_organization_de_recip_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contrib', '0027_actor_votervoice_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tip',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(max_digits=6, help_text='The amount of the tip, in dollars.', decimal_places=2)),
                ('de_recip_id', models.CharField(db_index=True, null=True, help_text='The recipient ID on Democracy Engine that received the tip.', max_length=64, blank=True)),
                ('ref_code', models.CharField(db_index=True, null=True, help_text='An optional referral code that lead the user to take this action.', max_length=24, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('extra', itfsite.utils.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('profile', models.ForeignKey(related_name='tips', help_text='The contributor information (name, address, etc.) and billing information used for this Tip.', to='contrib.ContributorInfo', on_delete=django.db.models.deletion.PROTECT)),
                ('recipient', models.ForeignKey(help_text='The recipient of the tip.', to='itfsite.Organization', on_delete=django.db.models.deletion.PROTECT)),
                ('user', models.ForeignKey(blank=True, help_text='The user making the Tip.', to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.PROTECT)),
                ('via_campaign', models.ForeignKey(blank=True, related_name='tips', help_text='The Campaign that this Tip was made via.', to='itfsite.Campaign', null=True, on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.AddField(
            model_name='pledge',
            name='tip_to_campaign_owner',
            field=models.DecimalField(default=Decimal('0'), max_digits=6, help_text='The amount in dollars that the user desires to send to the owner of via_campaign, zero if there is no one to tip or the user desires not to tip.', decimal_places=2),
        ),
        migrations.AddField(
            model_name='tip',
            name='via_pledge',
            field=models.OneToOneField(blank=True, related_name='tip', help_text='The executed Pledge that this Tip was made via.', to='contrib.Pledge', null=True, on_delete=django.db.models.deletion.PROTECT),
        ),
    ]
