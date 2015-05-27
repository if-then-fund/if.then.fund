# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import itfsite.models
import contrib.models
import enum3field


class Migration(migrations.Migration):

    dependencies = [
        ('itfsite', '0002_auto_20150407_2343'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('name', models.CharField(max_length=200, help_text='The name of the Organization.')),
                ('slug', models.SlugField(max_length=200, help_text='The unique URL slug for this Organization.')),
                ('orgtype', enum3field.EnumField(itfsite.models.OrganizationType, help_text='The type of the organization.', choices=[(itfsite.models.OrganizationType(1), 'User'), (itfsite.models.OrganizationType(2), 'C4'), (itfsite.models.OrganizationType(3), 'Company')])),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('description', models.TextField(help_text='Description text in the format given by description_format.')),
                ('description_format', enum3field.EnumField(contrib.models.TextFormat, help_text='The format of the description text.', choices=[(contrib.models.TextFormat(0), 'HTML'), (contrib.models.TextFormat(1), 'Markdown')])),
                ('website_url', models.URLField(null=True, max_length=256, help_text="The URL to this organization's website.", blank=True)),
                ('facebook_url', models.URLField(null=True, max_length=256, help_text="The URL to this organization's Facebook Page.", blank=True)),
                ('twitter_handle', models.CharField(null=True, max_length=64, help_text="The organization's Twitter handle (omit the @-sign).", blank=True)),
                ('extra', itfsite.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
        ),
    ]
