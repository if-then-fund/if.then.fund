# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0007_auto_20150329_1535'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContributorInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('cclastfour', models.CharField(help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a pledge from a credit card number.", max_length=4, null=True, db_index=True, blank=True)),
                ('extra', contrib.models.JSONField(help_text='Schemaless data stored with this object.', blank=True)),
            ],
        ),
        migrations.AddField(
            model_name='pledge',
            name='profile',
            field=models.ForeignKey(help_text='The contributor information (name, address, etc.) and billing information used for this Pledge. Immutable and cannot be changed after execution.', default=-1, on_delete=django.db.models.deletion.PROTECT, related_name='pledges', to='contrib.ContributorInfo'),
            preserve_default=False,
        ),
    ]
