# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import itfsite.models
import itfsite.utils
import enum3field


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0022_auto_20150816_1546'),
        ('itfsite', '0006_organization_banner_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=200, help_text='The title for the campaign.')),
                ('slug', models.SlugField(max_length=200, help_text='The URL slug for this campaign.')),
                ('subhead', models.TextField(help_text='Short sub-heading text for use in list pages and the meta description tag, in the format given by subhead_format.')),
                ('subhead_format', enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the subhead text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('status', enum3field.EnumField(itfsite.models.CampaignStatus, default=itfsite.models.CampaignStatus(0), help_text='The current status of the campaign.', choices=[(itfsite.models.CampaignStatus(0), 'Draft'), (itfsite.models.CampaignStatus(1), 'Open'), (itfsite.models.CampaignStatus(2), 'Paused'), (itfsite.models.CampaignStatus(3), 'Closed')])),
                ('headline', models.CharField(max_length=256, help_text='Headline text for the page.')),
                ('og_image', models.ImageField(upload_to='campaign-media', help_text='The og:image to display for the site.', null=True, blank=True)),
                ('splash_image', models.ImageField(upload_to='campaign-media', help_text='The big image to display behind the main call to action.', null=True, blank=True)),
                ('body_text', models.TextField(help_text='Body text, in the format given by body_format.')),
                ('body_format', enum3field.EnumField(itfsite.utils.TextFormat, help_text='The format of the body_text field.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('contrib_triggers', models.ManyToManyField(to='contrib.Trigger', help_text='Triggers to offer the user to take action on (or to show past actions).', related_name='campaigns', blank=True)),
                ('owner', models.ForeignKey(related_name='campaigns', help_text='The user/organization which owns the campaign. Null if the campaign is created by us.', to='itfsite.Organization', on_delete=django.db.models.deletion.PROTECT, blank=True, null=True)),
            ],
        ),
    ]
