# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import itfsite.utils
from django.conf import settings
import letters.models
import enum3field
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0007_campaign'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConstituentInfo',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('is_geocoded', models.BooleanField(help_text='Whether this record has been geocoded.', db_index=True, default=False)),
                ('extra', itfsite.utils.JSONField(blank=True, help_text='Schemaless data stored with this object.')),
            ],
        ),
        migrations.CreateModel(
            name='LettersCampaign',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=200, help_text='The title for the campaign.')),
                ('status', enum3field.EnumField(letters.models.CampaignStatus, choices=[(letters.models.CampaignStatus(0), 'Draft'), (letters.models.CampaignStatus(1), 'Open'), (letters.models.CampaignStatus(2), 'Paused'), (letters.models.CampaignStatus(3), 'Closed')], help_text='The current status of the campaign.', default=letters.models.CampaignStatus(0))),
                ('target_senators', models.BooleanField(help_text='Target letters to senators.', default=True)),
                ('target_representatives', models.BooleanField(help_text='Target letters to representatives.', default=True)),
                ('extra', itfsite.utils.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='letters_campaigns', blank=True, help_text='The user/organization which owns the campaign. Null if the campaign is created by us.', to='itfsite.Organization', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserLetter',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('email', models.EmailField(help_text='When an anonymous user writes a letter, their email address is stored here.', max_length=254, blank=True, null=True)),
                ('ref_code', models.CharField(help_text='An optional referral code that lead the user to take this action.', max_length=24, db_index=True, blank=True, null=True)),
                ('congressional_district', models.CharField(max_length=4, help_text="The user's congressional district in the form of XX##, e.g. AK00, at the time of submitting the letter, which determines who should receive the letter.")),
                ('submitted', models.BooleanField(help_text='Whether this letter was submitted to our delivery vendor.', default=False)),
                ('extra', itfsite.utils.JSONField(blank=True, help_text='Additional information stored with this object.')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('letterscampaign', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='letters', help_text='The LettersCampaign that this UserLetter was written for.', to='letters.LettersCampaign')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='letters', help_text="The user's information (name, address, etc.).", to='letters.ConstituentInfo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, blank=True, help_text="The user writing the letter. When an anonymous user writes a letter, this is null, the user's email address is stored instead.", to=settings.AUTH_USER_MODEL, null=True)),
                ('via_campaign', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='userletters', blank=True, help_text='The Campaign that this UserLetter was made via.', to='itfsite.Campaign', null=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='userletter',
            unique_together=set([('letterscampaign', 'email'), ('letterscampaign', 'user')]),
        ),
    ]
